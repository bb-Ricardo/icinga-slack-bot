#!/usr/bin/env python3

# This is mostly taken from:
# https://github.com/slackapi/python-slackclient/blob/master/tutorial/02-building-a-message.md

#################
#
#   import standard modules
#

import os
import re
import logging
import asyncio
import ssl as ssl_lib
from argparse import ArgumentParser, RawDescriptionHelpFormatter


# use while debugging
import pprint


#################
#
#   import extra modules
#

import certifi
import slack
from icinga2api.client import Client as i2_client


__version__ = "0.0.1"
__version_date__ = "2019-05-24"
__author__ = "Ricardo Bartels <ricardo@bitchbrothers.com>"


#################
#
#   default vars
#

default_log_level = "INFO"
default_config_file_path = "./icinga-bot.ini"

SLACK_BOT_TOKEN = os.environ["SLACK_BOT_TOKEN"]

ICINGA2_HOST = os.environ["ICINGA2_HOST"]
ICINGA2_PORT = os.environ["ICINGA2_PORT"]
ICINGA2_USER = os.environ["ICINGA2_USER"]
ICINGA2_PASS = os.environ["ICINGA2_PASS"]

#################
#
#   INTERNAL VARS
#

# define a program description
self_description = "ICINGA BOT DESCRIPTION"

MENTION_REGEX = "^<@(|[WU].+?)>(.*)"

# define valid log levels
valid_log_levels = [ "DEBUG", "INFO", "WARNING", "ERROR"]

args = None
log = None


#################
#
#   FUNCTIONS
#

# parse command line arguments
def parse_command_line():

    # define command line options
    parser = ArgumentParser(description=self_description + "\nVersion: " + __version__ + " (" + __version_date__ + ")", formatter_class=RawDescriptionHelpFormatter)

    parser.add_argument("-c", "--config", default=default_config_file_path, dest="config_file",
                        help="points to the config file to read config data from which is not installed under the default path '" + default_config_file_path + "'" ,
                        metavar="icinga-bot.ini")
    parser.add_argument("-l", "--log_level", choices=valid_log_levels, dest="log_level",
                        help="set log level (overrides config)")
    parser.add_argument("-d", "--daemon",  action='store_true', dest="daemon",
                        help="define if the script is run as a systemd daemon")

    return parser.parse_args()

# log an error and exit with error level 1
def do_error_exit(log_text):
    global log
    if log:
        log.error(log_text)
    else:
        logging.error(log_text)
    exit(1)

# setup logging
def setup_logging(log_level):

    global args

    logger = None

    # define log format first
    if args.daemon:
        # ommit time stamp if run in daemon mode
        logging.basicConfig(level="DEBUG", format='%(levelname)s: %(message)s')
    else:
        logging.basicConfig(level="DEBUG", format='%(asctime)s - %(levelname)s: %(message)s')

    if log_level == None or log_level == "":
        logging.debug("Configuring logging: No log level defined, using default level: %s" % default_log_level)
        log_level = default_log_level
    else:
        logging.debug("Configuring logging: Setting log level to: %s" % log_level)


    # create logger handler
    logger = logging.getLogger(__name__)

    # check set log level against self defined log level array
    if not log_level.upper() in valid_log_levels:
        do_error_exit('Invalid log level: %s' % log_level)

    # check the provided log level and bail out if something is wrong
    numeric_log_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_log_level, int):
        do_error_exit('Invalid log level: %s' % log_level)

    # set handler log level
    logger.setLevel(numeric_log_level)

    return logger

def enum(*sequential, **named):
    enums = dict(zip(sequential, range(len(sequential))), **named)
    reverse = dict((value, key) for key, value in enums.items())
    enums['reverse'] = reverse
    return type('Enum', (), enums)


HOST_STATE = enum("UP", "DOWN", "UNREACHABLE")
SERVICE_STATE = enum("OK", "WARNING", "CRITICAL", "UNKNWON")


async def handle_command(slack_message):
    global icinga2_client
    global HOST_STATE, SERVICE_STATE

    """DESCRIPTION
    """

    response_text = None
    default_response_text = "I didn't understand the command. Please use 'help' for more details."

    matches = re.search(MENTION_REGEX, slack_message)
    if matches:
        slack_message = matches.group(2).strip()

    if slack_message.startswith("help"):
        response_text = """Following commands are implemented:
        help:                   this help
        service status (ss):    display service status of all services in non OK state
        host status (hs):       display host status of all hosts in non UP state
        """

    elif slack_message.startswith("service status") or slack_message.startswith("ss"):
        response_text = "All services are OK"

    elif slack_message.startswith("host status") or slack_message.startswith("hs"):

        i2_response = icinga2_client.objects.list('Host', attrs=['name', 'state'])

        host_problems = list()
        host_problems.append({'name': "TEST Server", "state": 1})

        for host in i2_response:
            host_atr = host.get("attrs")

            if host_atr.get("state") and host_atr.get("state") != HOST_STATE.UP:
                host_problems.append(host_atr)
                pprint.pprint(host_atr.get("name"))

        # no host problems
        if len(host_problems) == 0:
            response_text = ("Good news, all %d hosts are UP" % len(i2_response))
        else:
            response_text = "Sorry, these Hosts having problems:"
            for host in host_problems:
                response_text += ("\n\t%s is in status %s" % (host.get("name"), HOST_STATE.reverse[host.get("state")]))

        pprint.pprint(response_text)

    return response_text or default_response_text


@slack.RTMClient.run_on(event="message")
async def message(**payload):
    """DESCRIPTION
    """
    data = payload["data"]
    web_client = payload["web_client"]

    if data.get("text") != None:
        channel_id = data.get("channel")
        user_id = data.get("user")
        bot_id = data.get("bot_id")

        # don't answer if message was sent by a bot
        if bot_id != None:
            return

        # parse command
        response = await handle_command(data.get("text"))

        web_client.chat_postMessage(
            channel=channel_id,
            text=response
        )

    return

if __name__ == "__main__":

    ################
    #   parse command line
    args = parse_command_line()

    ################
    #   setup logging
    log = setup_logging(args.log_level)

    log.info("Starting " + self_description)

    # set up icinga
    icinga2_client = i2_client("https://" + ICINGA2_HOST + ":" + ICINGA2_PORT, ICINGA2_USER, ICINGA2_PASS)

    # set up slack
    slack_ssl_context = ssl_lib.create_default_context(cafile=certifi.where())

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    rtm_client = slack.RTMClient(
        token=SLACK_BOT_TOKEN, ssl=slack_ssl_context, run_async=True, loop=loop
    )
    loop.run_until_complete(rtm_client.start())

# EOF
