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
import configparser

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
config = None


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

def parse_own_config(config_file):

    config_dict = {}

    global log, args

    config_error = False

    log.debug("Parsing daemon config file: %s" % config_file)

    if config_file == None or config_file == "":
        do_error_exit("Config file not defined.")

    # setup config parser and read config
    config_handler = configparser.ConfigParser(strict=True, allow_no_value=True)

    try:
        config_handler.read_file(open(config_file))
    except configparser.Error as e:
        do_error_exit("Error during config file parsing: %s" % e )
    except:
        do_error_exit("Unable to open file '%s'" % config_file )

    # read logging section
    this_section = "main"
    if not this_section in config_handler.sections():
        log.warning("Section '%s' not found in '%s'" % (this_section, config_file) )

    # read logging if present
    config_dict["log_level"] = config_handler.get(this_section, "log_level", fallback=default_log_level)

    log.debug("Config: %s = %s" % ("log_level", config_dict["log_level"]))

    # overwrite log level with command line argument
    if args.log_level != None and args.log_level != "":
        config_dict["log_level"] = args.log_level
        log.debug("Config: overwriting log_level with command line arg: %s" % args.log_level)

    # set log level again
    if args.log_level is not config_dict["log_level"]:
        setup_logging(config_dict["log_level"])

    # read common section
    this_section = "slack"
    if not this_section in config_handler.sections():
        do_error_exit("Section '%s' not found in '%s'" % (this_section, config_file) )
    else:
        config_dict["slack.bot_tocken"] = config_handler.get(this_section, "bot_tocken", fallback="")
        log.debug("Config: %s = %s" % ("slack.bot_tocken", config_dict["slack.bot_tocken"]))
        config_dict["slack.default_channel"] = config_handler.get(this_section, "default_channel", fallback="")
        log.debug("Config: %s = %s" % ("slack.default_channel", config_dict["slack.default_channel"]))

    # read paths section
    this_section = "icinga"
    if not this_section in config_handler.sections():
        do_error_exit("Section '%s' not found in '%s'" % (this_section, config_file) )
    else:
        config_dict["icinga.hostname"] = config_handler.get(this_section, "hostname", fallback="")
        log.debug("Config: %s = %s" % ("icinga.hostname", config_dict["icinga.hostname"]))
        config_dict["icinga.port"] = config_handler.get(this_section, "port", fallback="")
        log.debug("Config: %s = %s" % ("icinga.port", config_dict["icinga.port"]))
        config_dict["icinga.username"] = config_handler.get(this_section, "username", fallback="")
        log.debug("Config: %s = %s" % ("icinga.username", config_dict["icinga.username"]))
        config_dict["icinga.password"] = config_handler.get(this_section, "password", fallback="")
        log.debug("Config: %s = %s" % ("icinga.password", config_dict["icinga.password"]))

    for key, value in config_dict.items():
        if value is "":
            log.error("Config: option '%s' undefined or empty!" % key)
            config_error = True

    if config_error:
        return False

    return config_dict

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

    ################
    #   parse config file(s)
    config = parse_own_config(args.config_file)

    if not config:
        do_error_exit("Config parsing error")

    # set up icinga
    icinga2_client = i2_client("https://" + config["icinga.hostname"] + ":" + config["icinga.port"], config["icinga.username"], config["icinga.password"])

    # set up slack
    slack_ssl_context = ssl_lib.create_default_context(cafile=certifi.where())

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    rtm_client = slack.RTMClient(
        token=config["slack.bot_tocken"], ssl=slack_ssl_context, run_async=True, loop=loop
    )
    loop.run_until_complete(rtm_client.start())

# EOF
