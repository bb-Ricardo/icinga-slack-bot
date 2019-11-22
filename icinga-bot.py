#!/usr/bin/env python3

self_description = """This is an Icinga2 Slack bot.

It can be used to interact with Icinga2 from your Slack client. It uses the
Icinga2 API to get Host/Service status details. Simple status filters can be
used to narrow down the returned status list.
"""

# import  modules

import logging
import asyncio
import re
import ssl as ssl_lib
from datetime import datetime

import certifi
import slack

from i2_slack_modules.classes import BotResponse
from i2_slack_modules.icinga_connection import RequestResponse
from i2_slack_modules.common import (
    parse_command_line,
    parse_own_config,
    setup_logging,
    do_error_exit,
    my_own_function_name
)
from i2_slack_modules.command_definition import BotCommands
from i2_slack_modules.slack_helper import slack_error_response
from i2_slack_modules import slack_max_message_blocks, slack_max_message_text_length


__version__ = "0.2.0"
__version_date__ = "2019-11-16"
__author__ = "Ricardo Bartels <ricardo@bitchbrothers.com>"
__description__ = "Icinga2 Slack Bot"
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
    BotResponse: with response for Slack command
    """

    response = None

    default_response_text = "I didn't understand the command. Please use `help` for more details."

    # strip any mention "strings" from beginning of message
    matches = re.search(mention_regex, slack_message)
    if matches:
        slack_message = matches.group(2).strip()

    bot_commands = BotCommands()
    called_command = bot_commands.get_command_called(slack_message)

    """
    If you wonder why the bot_commands object gets passed on to the function here:
    This is to avoid circular imports between command_definition and slack_commands.
    It's probably not the best solution but couldn't come up with anything better.
    """
    command_handler_args = {
        "config": config,
        "conversations": conversations,
        "bot_commands": bot_commands,
        "slack_message": slack_message,
        "slack_user_id": slack_user_id,
        "slack_user_data": user_info
    }

    # special case to reset conversation
    if called_command is not None and called_command.name == "reset":
        response = called_command.get_command_handler()(**command_handler_args)

    # continue with conversion if there is one ongoing
    if response is None and conversations.get(slack_user_id):
        this_command_handler = conversations[slack_user_id].command.get_command_handler()
        # try to chat with user
        response = this_command_handler(**command_handler_args)

    # any regular command which is not reset
    if response is None and called_command and called_command.name != "reset":

        logging.debug("Received '%s' command" % called_command.name)

        command_handler = called_command.get_command_handler()

        if command_handler:
            response = command_handler(**command_handler_args)
        else:
            logging.error("command_handler for command '%s' not defined in command_definition.py" %
                          called_command.name)
            response = slack_error_response()

    # we didn't understand the message
    if not response:
        response = BotResponse(text=default_response_text)

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
            slack_user_data = await web_client.users_info(user=data.get("user"))

            if slack_user_data.get("user"):
                logging.debug("Successfully fetched user data.")
                user_info[data.get("user")] = slack_user_data.get("user")
                user_info[data.get("user")]["ts_created"] = datetime.now().timestamp()

        # parse command
        response = await handle_command(data.get("text"), data.get("user"))

        slack_api_response = post_slack_message(web_client, channel_id, response)

        if slack_api_response.error:
            error_message = slack_error_response(
                header="Slack API error while posting to Slack",
                error_message=slack_api_response.error)

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
    slack_response: BotResponse
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
            this_response.text = handle.chat_postMessage(
                channel=channel,
                text=text[:slack_max_message_text_length],
                blocks=blocks,
                attachments=attachments
            )

        except slack.errors.SlackApiError as e:
            this_response.text = e.response
            this_response.error = this_response.text.get("error")

        except Exception as e:
            this_response.error = str(e)

        return this_response

    response = RequestResponse()

    if handle is None:
        return RequestResponse(error="Error in function '%s': no client handle defined" % (my_own_function_name()))
    if channel is None:
        return RequestResponse(error="Error in function '%s': no channel defined" % (my_own_function_name()))
    if slack_response is None:
        return RequestResponse(error="Error in function '%s': no slack_response defined" % (my_own_function_name()))

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
        """
        if isinstance(slack_response, BotResponse):
        else:
            message can be sent like this with message builder classes
            unfortunately it causes to many log messages
            response.text = handle.chat_postMessage(channel=channel, **slack_response.to_dict())
        """

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

    ################
    #   add bot details to config dict
    config["bot.version"] = __version__
    config["bot.version_date"] = __version_date__
    config["bot.author"] = __author__
    config["bot.description"] = __description__
    config["bot.license"] = __license__
    config["bot.url"] = __url__

    # set up slack ssl context
    slack_ssl_context = ssl_lib.create_default_context(cafile=certifi.where())

    # get command handler and call it to get startup message
    icinga_status_command = BotCommands().get_command_called("icinga status").get_command_handler()
    status_reply = icinga_status_command(config=config, startup=True)

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
