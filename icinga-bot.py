#!/usr/bin/env python3

self_description = """This is an Icinga2 Slack bot.

It can be used to interact with Icinga2 from your Slack client. It uses the
Icinga2 API to get Host/Service status details. Simple status filters can be
used to narrow down the returned status list.
"""

# import  modules

import asyncio
import re
import ssl as ssl_lib

import certifi
import slack

from i2_slack_modules import SlackResponse
from i2_slack_modules.slack_commands import *


__version__ = "0.1.0"
__version_date__ = "2019-07-03"
__author__ = "Ricardo Bartels <ricardo@bitchbrothers.com>"
__description__ = "Icinga2 Slack bot"
__license__ = "MIT"
__url__ = "https://github.com/bb-Ricardo/icinga-slack-bot"


#################
#
#   default vars
#

default_log_level = "INFO"
default_config_file_path = "./icinga-bot.ini"

user_data_cache_timeout = 1800

#################
#
#   internal vars
#

mention_regex = "^<@(|[WU].+?)>(.*)"

args = None
config = None
conversations = dict()
user_info = dict()


#################
#
#   functions
#


async def handle_command(slack_message, slack_user_id=None):
    """parse a Slack message and try to interpret commands

    Currently implemented commands:
        ping: return a simple "pong"
        help: print a help description
        host status (hs): request a host status
        service status (ss): request a service status
        status overview (so): display status summary

    Returns "default_response_text" var if parsing failed

    Parameters
    ----------
    slack_message : str
        Slack message to parse

    slack_user_id : str
        Slack user id who sent the message

    Returns
    -------
    SlackResponse: with response for Slack command
    """

    response = None

    default_response_text = "I didn't understand the command. Please use `help` for more details."

    matches = re.search(mention_regex, slack_message)
    if matches:
        slack_message = matches.group(2).strip()

    # lowercase makes parsing easier
    slack_message = slack_message.lower()

    if slack_message == "reset" and conversations.get(slack_user_id) is not None:
        del conversations[slack_user_id]
        return SlackResponse(text="Your conversation has been reset.")

    if conversations.get(slack_user_id) or \
            slack_message.startswith("ack") or \
            slack_message.startswith("dt") or \
            slack_message.startswith("downtime"):

        # try to chat with user
        response = chat_with_user(config, conversations, slack_message, slack_user_id, user_info)

    elif slack_message.startswith("ping"):

        logging.debug("Found 'ping' command")

        response = SlackResponse(
            text="pong :table_tennis_paddle_and_ball:"
        )

    elif slack_message.startswith("help"):

        logging.debug("Found 'help' command")

        response = slack_command_help(__url__)

    elif slack_message.startswith("icinga status") or slack_message.startswith("is"):

        logging.debug("Found 'is' command")

        response = get_icinga_daemon_status(config)

    elif slack_message.startswith("service status") or slack_message.startswith("ss"):

        logging.debug("Found 'service status' command")

        status_type = "Service"

        if slack_message.startswith("ss"):
            slack_message = slack_message[len("ss"):].strip()
        else:
            slack_message = slack_message[len("service status"):].strip()

        response = run_icinga_status_query(config, status_type, slack_message)

    elif slack_message.startswith("host status") or slack_message.startswith("hs"):

        logging.debug("Found 'host status' command")

        status_type = "Host"

        if slack_message.startswith("hs"):
            slack_message = slack_message[len("hs"):].strip()
        else:
            slack_message = slack_message[len("host status"):].strip()

        response = run_icinga_status_query(config, status_type, slack_message)

    elif slack_message.startswith("status overview") or slack_message.startswith("so"):

        logging.debug("Found 'status overview' command")

        response = get_icinga_status_overview(config)

    # we didn't understand the message
    if not response:
        response = SlackResponse(text=default_response_text)

    return response


# noinspection PyUnresolvedReferences
@slack.RTMClient.run_on(event="message")
async def message(**payload):
    """parse payload of every Slack message received

    This functions extracts the text entry from payload and passes
    it to handle_command(). Payloads which contain a bot_id entry are ignored.
    The response will be posted to the same channel.

    Parameters
    ----------
    payload : object
        Slack payload to parse

    """

    data = payload["data"]
    web_client = payload["web_client"]

    if data.get("text") is not None:
        channel_id = data.get("channel")
        bot_id = data.get("bot_id")

        # don't answer if message was sent by a bot
        if bot_id is not None:
            return

        logging.debug("Received new Slack message: %s" % data.get("text"))

        # check if user data cache expired
        if user_info.get(data.get("user")) and \
                user_info[data.get("user")]["ts_created"] + user_data_cache_timeout < datetime.now().timestamp():
            logging.debug("User data cache for user '%s' expired." % data.get("user"))
            del user_info[data.get("user")]

        # fetch user data
        if user_info.get(data.get("user")) is None:
            logging.debug("No cached user data found. Fetching from Slack.")
            slack_response = await web_client.users_info(user=data.get("user"))
            if slack_response.get("user"):
                logging.debug("Successfully fetched user data.")
                user_info[data.get("user")] = slack_response.get("user")
                user_info[data.get("user")]["ts_created"] = datetime.now().timestamp()

        # parse command
        response = await handle_command(data.get("text"), data.get("user"))

        slack_api_response = post_slack_message(web_client, channel_id, response)

        if slack_api_response.error:
            # format error message block
            header_text = "Slack API error while posting to Slack"
            error_message = SlackResponse(
                text=header_text,
                blocks="*%s*" % header_text,
                attachments={
                    "fallback": header_text,
                    "text": slack_api_response.error,
                    "color": "danger"
                }
            )

            post_slack_message(web_client, channel_id, error_message)

    return


def post_slack_message(handle=None, channel=None, slack_response=None):
    """
    Post a message to Slack

    Parameters
    ----------
    handle: object
        the Slack client handle to use
    channel: str
        Slack channel to post message to
    slack_response: SlackResponse
        Slack response object

    Returns
    -------
    RequestResponse: slack response from posting a message
    """

    def __do_post(text, blocks, attachments):

        this_response = RequestResponse()

        # try to send of message
        try:
            logging.debug("Posting Slack message to channel '%s'" % channel)

            # noinspection PyUnresolvedReferences
            this_response.response = handle.chat_postMessage(
                channel=channel,
                text=text[:slack_max_message_text_length],
                blocks=blocks,
                attachments=attachments
            )

        except slack.errors.SlackApiError as e:
            this_response.response = e.response
            this_response.error = this_response.response.get("error")

        except Exception as e:
            this_response.error = str(e)

        return this_response

    response = RequestResponse()

    if handle is None:
        return RequestResponse(error="Error in function 'post_slack_message': no client handle defined")
    if channel is None:
        return RequestResponse(error="Error in function 'post_slack_message': no channel defined")
    if slack_response is None:
        return RequestResponse(error="Error in function 'post_slack_message': no slack_response defined")

    # split post into multiple posts
    if slack_response.blocks is not None and len(slack_response.blocks) > 50:

        # use lambda function to split message_blocks to chunks of 'slack_max_message_blocks' blocks
        split_blocks = lambda a, n=slack_max_message_blocks: [a[i:i + n] for i in range(0, len(a), n)]

        splitted_blocks = split_blocks(slack_response.blocks)

        logging.debug("Sending multiple Slack messages as the number of blocks %d exceeds the maximum of %d" %
                      (len(slack_response.blocks), slack_max_message_blocks))

        post_iteration = 1
        for message_blocks in splitted_blocks:

            last_message_attachments = None

            # get attachments and send them only with the last message
            if post_iteration == len(splitted_blocks):
                last_message_attachments = slack_response.dump_attachments()

            response = __do_post(slack_response.text, message_blocks, last_message_attachments)

            if response.error:
                break

            post_iteration += 1

    else:

        response = __do_post(slack_response.text, slack_response.blocks, slack_response.dump_attachments())

    if response.error:
        logging.error("Posting Slack message to channel '%s' failed: " % response.error)

    # only the response of the last message will be returned
    return response


if __name__ == "__main__":
    """main 'function' will setup the Slack bot and initialize connections"""

    ################
    #   parse command line
    args = parse_command_line(self_description=self_description,
                              version=__version__,
                              version_date=__version_date__,
                              default_config_file_path=default_config_file_path)

    ################
    #   setup logging
    setup_logging(args, default_log_level)

    logging.info("Starting " + __description__)

    ################
    #   parse config file(s)
    config = parse_own_config(args, default_log_level)

    if not config:
        do_error_exit("Config parsing error")

    # set up slack ssl context
    slack_ssl_context = ssl_lib.create_default_context(cafile=certifi.where())

    status_reply = get_icinga_daemon_status(config, startup=True)

    # message about start
    client = slack.WebClient(token=config["slack.bot_token"], ssl=slack_ssl_context)

    post_response = post_slack_message(client, config["slack.default_channel"], status_reply)

    del client, status_reply

    if post_response.error:
        do_error_exit("Error while posting startup message to slack (%s): %s" %
                      (config["slack.default_channel"], post_response.error))

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    rtm_client = slack.RTMClient(
        token=config["slack.bot_token"], ssl=slack_ssl_context, run_async=True, loop=loop
    )
    loop.run_until_complete(rtm_client.start())

# EOF
