#!/usr/bin/env python3

self_description = \
"""This is an Icinga2 Slack bot.

It can be used to interact with Icinga2 from your Slack client. It uses the
Icinga2 API to get Host/Service status details. Simple status filters can be
used to narrow down the returned status list.
"""

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
from icinga2api.client import Client as I2Client, Icinga2ApiException


__version__ = "0.0.1"
__version_date__ = "2019-05-28"
__author__ = "Ricardo Bartels <ricardo@bitchbrothers.com>"


#################
#
#   default vars
#

default_log_level = "INFO"
default_config_file_path = "./icinga-bot.ini"
default_connection_timeout = 5

#################
#
#   INTERNAL VARS
#

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

def parse_command_line():
    """parse command line arguments

    Also add current version and version date to description
    """

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
    """parsing and basic validation of own config file

    Parameters
    ----------
    config_file : str
        The file location of the config file

    Returns
    -------
    dict
        a dictionary with all config options parsed from the config file
    """

    config_dict = {}

    global log, args

    config_error = False

    log.debug("Parsing daemon config file: %s" % config_file)

    if config_file is None or config_file == "":
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
    if args.log_level is not None and args.log_level != "":
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
        config_dict["slack.bot_token"] = config_handler.get(this_section, "bot_token", fallback="")
        log.debug("Config: %s = %s" % ("slack.bot_token", config_dict["slack.bot_token"]))
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
        #log.debug("Config: %s = %s" % ("icinga.password", config_dict["icinga.password"]))
        config_dict["icinga.web2_url"] = config_handler.get(this_section, "web2_url", fallback="")
        log.debug("Config: %s = %s" % ("icinga.web2_url", config_dict["icinga.web2_url"]))
        config_dict["icinga.certificate"] = config_handler.get(this_section, "certificate", fallback="")
        log.debug("Config: %s = %s" % ("icinga.certificate", config_dict["icinga.certificate"]))
        config_dict["icinga.key"] = config_handler.get(this_section, "key", fallback="")
        log.debug("Config: %s = %s" % ("icinga.key", config_dict["icinga.key"]))
        config_dict["icinga.ca_certificate"] = config_handler.get(this_section, "ca_certificate", fallback="")
        log.debug("Config: %s = %s" % ("icinga.ca_certificate", config_dict["icinga.ca_certificate"]))
        config_dict["icinga.timeout"] = config_handler.get(this_section, "timeout", fallback=str(default_connection_timeout))
        log.debug("Config: %s = %s" % ("icinga.timeout", config_dict["icinga.timeout"]))

    for key, value in config_dict.items():
        if value is "":
            # if we use a certificate then don't care if user or password are defined
            if key in [ "icinga.username", "icinga.password" ] and config_dict["icinga.certificate"] != "":
                continue
            # these vars can be empty
            if key in [ "icinga.key", "icinga.certificate", "icinga.web2_url", "icinga.ca_certificate" ]:
                continue
            log.error("Config: option '%s' undefined or empty!" % key)
            config_error = True

    if config_error:
        return False

    return config_dict

def do_error_exit(log_text):
    """log an error and exit with return code 1

    Parameters
    ----------
    log_text : str
        the text to log as error
    """

    global log
    if log:
        log.error(log_text)
    else:
        logging.error(log_text)
    exit(1)

def setup_logging(log_level = None):
    """Setup logging

    Parameters
    ----------
    log_level : str, optional
        Log level to use during runtime (defaults to default_log_level)

    Returns
    -------
    object
        a logging object
    """

    global args

    logger = None

    # define log format first
    if args.daemon:
        # omit time stamp if run in daemon mode
        logging.basicConfig(level="DEBUG", format='%(levelname)s: %(message)s')
    else:
        logging.basicConfig(level="DEBUG", format='%(asctime)s - %(levelname)s: %(message)s')

    if log_level is None or log_level == "":
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
    """returns an enumerated type"""

    enums = dict(zip(sequential, range(len(sequential))), **named)
    reverse = dict((value, key) for key, value in enums.items())
    enums['reverse'] = reverse
    return type('Enum', (), enums)

def setup_icinga_connection():
    """Setup an Icinga connection and pass all parameters

    Returns
    -------
    tuple
        returns a tuple with two elements
            i2_handle: icinga2 client object
            i2_error: an error string in case a client connection failed
    """

    global config

    i2_handle = None
    i2_error = None

    try:
        i2_handle = I2Client(url="https://" + config["icinga.hostname"] + ":" + config["icinga.port"],
                             username=config["icinga.username"], password=config["icinga.password"],
                             certificate=config["icinga.certificate"], key=config["icinga.key"],
                             ca_certificate=config["icinga.ca_certificate"], timeout=int(config["icinga.timeout"])
                            )

    except Icinga2ApiException as e:
        # implement error handling
        log.error("Unable to set up Icinga2 connection: %s" % str(e))

    return i2_handle, i2_error

def get_i2_status():
    """Request Icinga2 API Endpoint /v1/status

    Returns
    -------
    tuple
        returns a tuple with two elements
            i2_response: json response
            i2_error: an error string in case the query failed
    """

    i2_response = None

    i2_handle, i2_error  = setup_icinga_connection()

    if not i2_handle:
        return None

    try:
        i2_response = i2_handle.status.list()
    except Exception as e:
        # implement error handling
        log.error("Unable to query Icinga2 status: %s" % str(e))

    return i2_response, i2_error

def get_i2_object(type="Host", filter_states=None, filter_names=None):
    """Request Icinga2 API Endpoint /v1/objects

    Parameters
    ----------
    type : str
        the object type to request (Host or Service)
    filter_states : list, optional
        a list of object states to filter for, use function "get_i2_filter"
        to generate this list (default is None)
    filter_names : list, optional
        a list of object names to filter for, use function "get_i2_filter"
        to generate this list (default is None)

    Returns
    -------
    tuple
        returns a tuple with two elements
            i2_response: json response
            i2_error: an error string in case the query failed
    """

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

    return i2_response, i2_error

def query_i2(type=None, filter_states=None, filter_names=None):
    """Request Icinga2 API Endpoint /v1/objects

    Parameters
    ----------
    type : str
        the object type to request (Host or Service)
    filter_states : list, optional
        a list of object states to filter for, use function "get_i2_filter"
        to generate this list (default is None)
    filter_names : list, optional
        a list of object names to filter for, use function "get_i2_filter"
        to generate this list (default is None)

    Returns
    -------
    list
        returns a list of requested objects

    ToDo
    ----
    this function can probably be scrapped an be integrated into get_i2_object
    """

    response_objects = list()

    if not type:
        return None

    i2_response, i2_error = get_i2_object(type, filter_states, filter_names)

    if i2_response:
        for object in i2_response:
            response_objects.append(object.get("attrs"))

    return response_objects

def get_i2_filter(type="Host", slack_message=""):
    """Parse a Slack message and create lists of filters depending on the
    object type

    Parameters
    ----------
    type : str
        the object type to request (Host or Service)
    slack_message : str
        the Slack message to parse

    Returns
    -------
    tuple
        returns a tuple with three elements
            filter_states: a list of filter states
            filter_names: a list of names to filter for
            filter_error: a list of errors which occurred while parsing message
    """

    filter_error = list()
    filter_options = list()
    filter_states = list()

    host_states = enum("UP", "DOWN", "UNREACHABLE")
    service_states = enum("OK", "WARNING", "CRITICAL", "UNKNOWN")

    if slack_message.strip() is not "":
        filter_options = slack_message.split(" ")
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

    return filter_states, filter_options, filter_error

def get_service_block(host, services):
    """return a slack message block for service status details

    Parameters
    ----------
    host : str
        host name in slack message block
    services : list
        list of service names in slack message block

    Returns
    -------
    dict
        returns a slack message block dictionary
    """

    text = "*%s* (%d services)\n\t%s" % (host, len(services), "\n\n\t".join(services))
    return [
        {"type": "section", "text": {"type": "mrkdwn", "text": text}},
    ]

def get_single_block(text):
    """return a slack message block

    Parameters
    ----------
    text : str
        text to add to slack message block

    Returns
    -------
    dict
        returns a slack message block dictionary
    """

#   {"type": "divider"},
    return [
        {"type": "section", "text": {"type": "mrkdwn", "text": text}},
    ]


def format_response(type="Host", response_objects = list()):
    """Format a slack response

    The objects will be sorted after name before they are compiled into
    a response. Service objects will first be sorted after host name and
    then after service name

    Parameters
    ----------
    type : str
        the object type to request (Host or Service)
    response_objects : list
        a list of objects to include in the Slack message

    Returns
    -------
    list
        returns a list of slack message blocks
    """

    response_blocks = None
    current_host = None
    service_list = []

    # no service problems
    if len(response_objects) is not 0:

        # sort
        if type is "Host":
            response_objects = sorted(response_objects, key=lambda k: k['name'])
            #object_states = enum("UP", "DOWN", "UNREACHABLE")
            object_emojies = enum(":white_check_mark:", ":red_circle:", ":red_circle:")
        else:
            response_objects = sorted(response_objects, key=lambda k: (k['host_name'], k['name']))
            #object_states = enum("OK", "WARNING", "CRITICAL", "UNKNOWN")
            object_emojies = enum(":white_check_mark:", ":warning:", ":red_circle:", ":question:")

        #response_text = "found %d %ss objects:" % ( len(response_objects), type.lower() )

        response_blocks = []
        for object in response_objects:
            last_check = object.get("last_check_result")
            if type is "Host":
                text = "%s %s: %s" % (object_emojies.reverse[object.get("state")], object.get("name"), last_check.get("output"))
                response_blocks.extend(get_single_block(text))
            else:
                if current_host and current_host != object.get("host_name"):
                    response_blocks.extend(get_service_block(current_host, service_list))
                    service_list = []

                current_host = object.get("host_name")
                service_list.append("%s %s: %s" % (object_emojies.reverse[object.get("state")], object.get("name"), last_check.get("output")))
        else:
            if type is not "Host":
                response_blocks.extend(get_service_block(current_host, service_list))

    return response_blocks or get_single_block("Your command returned no results")

async def handle_command(slack_message):
    """parse a Slack message and try to interpret commands

    Currently implemented commands:
        ping: return a simple "pong"
        help: print a help description
        host status (hs): request a host status
        service status (ss): request a service status

    Returns "default_response_text" var if parsing failed

    Parameters
    ----------
    slack_message : str
        Slack message to parse

    Returns
    -------
    list
        returns a list of slack message blocks
    """

    #response_text = None
    response_blocks = None
    status_type = None
    query_icinga = False
    default_response_text = "I didn't understand the command. Please use 'help' for more details."

    matches = re.search(MENTION_REGEX, slack_message)
    if matches:
        slack_message = matches.group(2).strip()

    # lowercase makes parsing easier
    slack_message = slack_message.lower()

    if slack_message.startswith("ping"):
        response_blocks = get_single_block("pong")

    elif slack_message.startswith("help"):
        response_blocks = get_single_block("""Following commands are implemented:
        help:                   this help
        service status (ss):    display service status of all services in non OK state
        host status (hs):       display host status of all hosts in non UP state
        """)

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
                response_blocks = get_single_block("filter '%s' not valid for %s status commands, check 'help' command" % (i2_filter_error[0], status_type))
            else:
                response_blocks = get_single_block("filters '%s' and '%s' are not valid for %s status commands, check 'help' command" % ("', '".join(i2_filter_error[:-1]), i2_filter_error[-1], status_type))
        else:
            response_objects = query_i2(status_type, i2_filter_status, i2_filter_names)
            response_blocks = format_response(status_type, response_objects)

    return response_blocks or get_single_block(default_response_text)

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

    Returns
    -------
    list
        returns a list of slack message blocks
    """

    data = payload["data"]
    web_client = payload["web_client"]

    if data.get("text") is not None:
        channel_id = data.get("channel")
        #user_id = data.get("user")
        bot_id = data.get("bot_id")

        # don't answer if message was sent by a bot
        if bot_id is not None:
            return

        # parse command
        response = await handle_command(data.get("text"))

        try:
            web_client.chat_postMessage(
                channel=channel_id,
                blocks=response
            )
        except slack.errors.SlackApiError as e:
            web_client.chat_postMessage(
                channel=channel_id,
                text=str(e)
            )

    return

if __name__ == "__main__":
    """main 'function' will setup the Slack bot and initialize connections"""

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
        token=config["slack.bot_token"], ssl=slack_ssl_context, run_async=True, loop=loop
    )
    loop.run_until_complete(rtm_client.start())

# EOF
