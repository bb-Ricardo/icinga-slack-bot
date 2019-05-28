#!/usr/bin/env python3

# The slack basics are mostly taken from here:
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
from icinga2api.client import Client as i2_client, Icinga2ApiException


__version__ = "0.0.1"
__version_date__ = "2019-05-28"
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

def setup_icinga_connection():
    global config

    i2_handle = None
    i2_error = None

    try:
        i2_handle = i2_client(url="https://" + config["icinga.hostname"] + ":" + config["icinga.port"], \
                              username=config["icinga.username"], \
                              password=config["icinga.password"])

    except Icinga2ApiException as e:
        # implement error handling
        log.error("Unable to set up Icinga2 connection: %s" % str(e))

    return (i2_handle, i2_error)

def get_i2_status():

    i2_response = None

    i2_handle, i2_error  = setup_icinga_connection()

    if not i2_handle:
        return None

    try:
        i2_response = i2_handle.status.list()
    except Exception as e:
        # implement error handling
        log.error("Unable to query Icinga2 status: %s" % str(e))

    return (i2_response, i2_error)

def get_i2_object(type="Host", filter_states=None, filter_names=None):

    i2_response = None
    i2_filters = None

    i2_handle, i2_error = setup_icinga_connection()

    if not i2_handle:
        return None

    # default attributes
    list_attrs = ['name', 'state', 'last_check_result', 'acknowledgement', 'downtime_depth', 'last_state_change']

    # add host_name to attribute list
    if type is "Service":
        list_attrs.append("host_name")

    if filter_states:
        i2_filters = '(' + ' || '.join(filter_states) + ')'

    logging.debug("filter_names: %s" % filter_names)

    if filter_names and len(filter_names) >= 1 and filter_names[0] is not "":
        if i2_filters:
            i2_filters += " && "
        else:
            i2_filters = str("")

        if type is "Host":

            hosts = list()
            for host in filter_names:
                hosts.append('match("*{}*", host.name)'.format(host))
            i2_filters += '(' + ' || '.join(hosts) + ')'
        else:
            if len(filter_names) == 1:
                i2_filters += '( match("*%s*", host.name) || match("*%s*", service.name) )' % ( filter_names[0], filter_names[0])
            else:
                i2_filters += '( match("*%s*", host.name) && match("*%s*", service.name) )' % ( filter_names[0], filter_names[1])
                i2_filters += ' || ( match("*%s*", host.name) && match("*%s*", service.name) )' % ( filter_names[1], filter_names[0])


    logging.debug("Filter: %s" % i2_filters)

    try:
        i2_response =  i2_handle.objects.list(type, attrs=list_attrs, filters=i2_filters)
    except Exception as e:
        log.error("Unable to query Icinga2 status: %s" % str(e))
        if "404" in str(e):
            i2_error = "No objects found"
            pass

    return (i2_response, i2_error)

def query_i2(type=None, filter=None, names=None):

    type_sring = "host"
    object_states = enum("UP", "DOWN", "UNREACHABLE")
    response_objects = list()
    response_text = ""

    if not type:
        return None

    if type is "Service":
        type_sring = "service"
        object_states = enum("OK", "WARNING", "CRITICAL", "UNKNOWN")

    i2_response, i2_error = get_i2_object(type, filter, names)

    if i2_response:
        for object in i2_response:
            #pprint.pprint(object)
            response_objects.append(object.get("attrs"))

    # no service problems
    if len(response_objects) == 0:
        #response_text = ("Good news, all %d %s are %s" % (len(i2_response), type_sring, object_states.reverse[0]))
        response_text = "Your command returned no results"
    else:

        # sort
        if type is "Host":
            response_objects = sorted(response_objects, key=lambda k: k['name'])
        else:
            response_objects = sorted(response_objects, key=lambda k: (k['host_name'], k['name']))

        response_text = "found %d %s objects:" % ( len(response_objects), type_sring )
        for object in response_objects:
            last_check = object.get("last_check_result")
            if type is "Host":
                response_text += ("\n\t%s is in status %s" % (
                                  object.get("name"), object_states.reverse[object.get("state")]))
            else:
                response_text += ("\n\t%s: %s is in status %s" % (
                                  object.get("host_name"), object.get("name"),
                                  object_states.reverse[object.get("state")]))
            response_text += ("\n\t\t%s" % (last_check.get("output")))

    return response_text

def get_i2_filter(type="Host", message=""):

    filter_error = list()
    filter_options = list()
    filter_states = list()

    host_states = enum("UP", "DOWN", "UNREACHABLE")
    service_states = enum("OK", "WARNING", "CRITICAL", "UNKNOWN")

    if message.strip() is not "":
        filter_options = message.split(" ")
        filter_options = sorted(set(filter_options))

    # use a copy of filter_options to not remove items from current iteration
    for filter_option in list(filter_options):

        logging.debug("checking Filter option: %s" % filter_option)

        if "up" == filter_option:
            if type is "Host":
                filter_states.append("host.state == %s" % str(host_states.UP))
            else:
                filter_error.append(filter_option)
            filter_options.remove(filter_option)
        if "down" == filter_option:
            if type is "Host":
                filter_states.append("host.state == %s" % str(host_states.DOWN))
            else:
                filter_error.append(filter_option)
            filter_options.remove(filter_option)
        if "unreach" == filter_option or "unreachable" == filter_option:
            if type is "Host":
                filter_states.append("host.state == %s" % str(host_states.UNREACHABLE))
            else:
                filter_error.append(filter_option)
            filter_options.remove(filter_option)

        if "ok" == filter_option:
            if type is "Service":
                filter_states.append("service.state == %s" % str(service_states.OK))
            else:
                filter_error.append(filter_option)
            filter_options.remove(filter_option)
        if "warn" == filter_option or "warning" == filter_option:
            if type is "Service":
                filter_states.append("service.state == %s" % str(service_states.WARNING))
            else:
                filter_error.append(filter_option)
            filter_options.remove(filter_option)
        if "crit" == filter_option or "critical" == filter_option:
            if type is "Service":
                filter_states.append("service.state == %s" % str(service_states.CRITICAL))
            else:
                filter_error.append(filter_option)
            filter_options.remove(filter_option)
        if "unknown" == filter_option:
            if type is "Service":
                filter_states.append("service.state == %s" % str(service_states.UNKNOWN))
            else:
                filter_error.append(filter_option)
            filter_options.remove(filter_option)

#        # get problem services if no filters are requested
#        if len(filter_states) == 0 and not "all" in filter_options:
#            filter_states.append("service.state != ServiceOK")


    # get problem host/services if no filters are requested
    if len(filter_states) == 0 and not "all" in filter_options and len(filter_options) == 0:
        if type is "Host":
            filter_states.append("host.state != HostUP")
        else:
            filter_states.append("service.state != ServiceOK")

    # remove all attribute from filter
    if "all" in filter_options:
        filter_options.remove("all")

    # remaining command will be used to match host/service name
    logging.debug("states: %s" % filter_states)
    logging.debug("names: %s" % filter_options)
    logging.debug("errors: %s" % filter_error)

    if len(filter_error) == 0:
        filter_error = None

    return (filter_states, filter_options, filter_error)

async def handle_command(slack_message):

    """DESCRIPTION
    """

    response_text = None
    query_icinga = False
    default_response_text = "I didn't understand the command. Please use 'help' for more details."

    matches = re.search(MENTION_REGEX, slack_message)
    if matches:
        slack_message = matches.group(2).strip()

    # lowercase makes parsing easier
    slack_message = slack_message.lower()

    if slack_message.startswith("ping"):
        response_text = "pong"

    elif slack_message.startswith("help"):
        response_text = """Following commands are implemented:
        help:                   this help
        service status (ss):    display service status of all services in non OK state
        host status (hs):       display host status of all hosts in non UP state
        """

    elif slack_message.startswith("service status") or slack_message.startswith("ss"):

        status_type = "Service"

        if slack_message.startswith("ss"):
            slack_message = slack_message[len("ss"):].strip()
        else:
            slack_message = slack_message[len("service status"):].strip()

        query_icinga = True

    elif slack_message.startswith("host status") or slack_message.startswith("hs"):

        status_type = "Host"

        if slack_message.startswith("hs"):
            slack_message = slack_message[len("hs"):].strip()
        else:
            slack_message = slack_message[len("host status"):].strip()

        query_icinga = True

    # query icinga
    if query_icinga:

        i2_filter_status, i2_filter_names, i2_filter_error = get_i2_filter(status_type, slack_message)

        if i2_filter_error:
            if len(i2_filter_error) == 1:
                response_text = "filter '%s' not valid for %s status commands, check 'help' command" % (i2_filter_error[0], status_type)
            else:
                response_text = "filters '%s' and '%s' are not valid for %s status commands, check 'help' command" % ("', '".join(i2_filter_error[:-1]), i2_filter_error[-1], status_type)
        else:
            response_text = query_i2(status_type, i2_filter_status, i2_filter_names)

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
    get_i2_status()

    # set up slack
    slack_ssl_context = ssl_lib.create_default_context(cafile=certifi.where())

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    rtm_client = slack.RTMClient(
        token=config["slack.bot_tocken"], ssl=slack_ssl_context, run_async=True, loop=loop
    )
    loop.run_until_complete(rtm_client.start())

# EOF
