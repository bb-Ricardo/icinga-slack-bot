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
import json
from datetime import datetime

# use while debugging
#import pprint


#################
#
#   import extra modules
#

import certifi
import slack
from icinga2api.client import Client as I2Client, Icinga2ApiException


__version__ = "0.0.1"
__version_date__ = "2019-06-29"
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
default_connection_timeout = 5

slack_max_message_text_length = 40000
slack_max_block_text_length = 3000
slack_max_message_blocks = 50
slack_max_message_attachments = 100

github_logo_url = "https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png"

#################
#
#   internal vars
#

mention_regex = "^<@(|[WU].+?)>(.*)"

# define valid log levels
valid_log_levels = [ "DEBUG", "INFO", "WARNING", "ERROR"]

args = None
config = None


#################
#
#   functions
#

def parse_command_line():
    """parse command line arguments

    Also add current version and version date to description
    """

    # define command line options
    parser = ArgumentParser(
        description=self_description + "\nVersion: " + __version__ + " (" + __version_date__ + ")",
        formatter_class=RawDescriptionHelpFormatter)

    parser.add_argument("-c", "--config", default=default_config_file_path, dest="config_file",
                        help="points to the config file to read config data from " +
                             "which is not installed under the default path '" +
                             default_config_file_path + "'" ,
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

    global args

    config_error = False

    logging.debug("Parsing daemon config file: %s" % config_file)

    if config_file is None or config_file == "":
        do_error_exit("Config file not defined.")

    # setup config parser and read config
    config_handler = configparser.ConfigParser(strict=True, allow_no_value=True)

    try:
        config_handler.read_file(open(config_file))
    except configparser.Error as e:
        do_error_exit("Error during config file parsing: %s" % e )
    except Exception:
        do_error_exit("Unable to open file '%s'" % config_file )

    # read logging section
    this_section = "main"
    if not this_section in config_handler.sections():
        logging.warning("Section '%s' not found in '%s'" % (this_section, config_file) )

    # read logging if present
    config_dict["log_level"] = config_handler.get(this_section, "log_level", fallback=default_log_level)

    # overwrite log level with command line argument
    if args.log_level is not None and args.log_level != "":
        config_dict["log_level"] = args.log_level
        logging.info("Config: overwriting log_level with command line arg: %s" % args.log_level)

    # set log level again
    if args.log_level is not config_dict["log_level"]:
        set_log_level(config_dict["log_level"])

    logging.debug("Config: %s = %s" % ("log_level", config_dict["log_level"]))

    # read common section
    this_section = "slack"
    if not this_section in config_handler.sections():
        do_error_exit("Section '%s' not found in '%s'" % (this_section, config_file) )
    else:
        config_dict["slack.bot_token"] = config_handler.get(this_section, "bot_token", fallback="")
        logging.debug("Config: %s = %s***" % ("slack.bot_token", config_dict["slack.bot_token"][0:10]))
        config_dict["slack.default_channel"] = config_handler.get(this_section, "default_channel", fallback="")
        logging.debug("Config: %s = %s" % ("slack.default_channel", config_dict["slack.default_channel"]))

    # read paths section
    this_section = "icinga"
    if not this_section in config_handler.sections():
        do_error_exit("Section '%s' not found in '%s'" % (this_section, config_file) )
    else:
        config_dict["icinga.hostname"] = config_handler.get(this_section, "hostname", fallback="")
        logging.debug("Config: %s = %s" % ("icinga.hostname", config_dict["icinga.hostname"]))
        config_dict["icinga.port"] = config_handler.get(this_section, "port", fallback="")
        logging.debug("Config: %s = %s" % ("icinga.port", config_dict["icinga.port"]))
        config_dict["icinga.username"] = config_handler.get(this_section, "username", fallback="")
        logging.debug("Config: %s = %s" % ("icinga.username", config_dict["icinga.username"]))
        config_dict["icinga.password"] = config_handler.get(this_section, "password", fallback="")
        logging.debug("Config: %s = %s***" % ("icinga.password", config_dict["icinga.password"][0:3]))
        config_dict["icinga.web2_url"] = config_handler.get(this_section, "web2_url", fallback="")
        logging.debug("Config: %s = %s" % ("icinga.web2_url", config_dict["icinga.web2_url"]))
        config_dict["icinga.certificate"] = config_handler.get(this_section, "certificate", fallback="")
        logging.debug("Config: %s = %s" % ("icinga.certificate", config_dict["icinga.certificate"]))
        config_dict["icinga.key"] = config_handler.get(this_section, "key", fallback="")
        logging.debug("Config: %s = %s" % ("icinga.key", config_dict["icinga.key"]))
        config_dict["icinga.ca_certificate"] = config_handler.get(this_section, "ca_certificate", fallback="")
        logging.debug("Config: %s = %s" % ("icinga.ca_certificate", config_dict["icinga.ca_certificate"]))
        config_dict["icinga.timeout"] = config_handler.get(this_section, "timeout",
                                                           fallback=str(default_connection_timeout))
        logging.debug("Config: %s = %s" % ("icinga.timeout", config_dict["icinga.timeout"]))

    for key, value in config_dict.items():
        if value is "":
            # if we use a certificate then don't care if user or password are defined
            if key in [ "icinga.username", "icinga.password" ] and config_dict["icinga.certificate"] != "":
                continue
            # these vars can be empty
            if key in [ "icinga.key", "icinga.certificate", "icinga.web2_url", "icinga.ca_certificate" ]:
                continue
            logging.error("Config: option '%s' undefined or empty!" % key)
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

    logging.error(log_text)
    exit(1)

def set_log_level(log_level = None):
    """set or reset the log level

    Parameters
    ----------
    log_level : str
        Log level to set

    """

    global valid_log_levels

    # check set log level against self defined log level array
    if not log_level.upper() in valid_log_levels:
        do_error_exit('Invalid log level: %s' % log_level)

    # check the provided log level and bail out if something is wrong
    numeric_log_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_log_level, int):
        do_error_exit('Invalid log level: %s' % log_level)

    logging.info("Setting log level to: %s" % log_level)

    # unfortunately we have to manipulate the root logger
    if log_level == "DEBUG":
        logging.disable(logging.NOTSET)
    elif log_level == "INFO":
        logging.disable(logging.DEBUG)
    elif log_level == "WARNING":
        logging.disable(logging.INFO)
    elif log_level == "ERROR":
        logging.disable(logging.WARNING)

def setup_logging(log_level = None):
    """Setup logging

    Parameters
    ----------
    log_level : str, optional
        Log level to use during runtime (defaults to default_log_level)

    """

    global args

    if args.daemon:
        # omit time stamp if run in daemon mode
        logging.basicConfig(level="DEBUG", format='%(levelname)s: %(message)s')
    else:
        logging.basicConfig(level="DEBUG", format='%(asctime)s - %(levelname)s: %(message)s')

    if log_level is None or log_level == "":
        logging.debug("Configuring logging: No log level defined, using default level: %s" % default_log_level)
        log_level = default_log_level

    set_log_level(log_level)

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
        i2_error = str(e)
        logging.error("Unable to set up Icinga2 connection: %s" % i2_error)
        pass

    logging.debug("Successfully connected to Icinga2")

    return i2_handle, i2_error

def get_i2_status(application = None):
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
        if i2_error is not None:
            return None, i2_error
        else:
            return None, "Unknown error while setting up Icinga2 connection"

    try:
        logging.debug("Requesting Icinga2 status for application: %s " % application)

        i2_response = i2_handle.status.list(application)

    except Exception as e:
        i2_error = str(e)
        logging.error("Unable to query Icinga2 status: %s" % i2_error)
        pass

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
        if i2_error is not None:
            return None, i2_error
        else:
            return None, "Unknown error while setting up Icinga2 connection"

    # default attributes to query
    list_attrs = ['name', 'state', 'last_check_result', 'acknowledgement', 'downtime_depth', 'last_state_change']

    # add host_name to attribute list if services are requested
    if type is "Service":
        list_attrs.append("host_name")

    if filter_states:
        i2_filters = '(' + ' || '.join(filter_states) + ')'

    if filter_names and len(filter_names) >= 1 and filter_names[0] is not "":
        if i2_filters:
            i2_filters += " && "
        else:
            i2_filters = str("")

        if type is "Host":

            hosts = list()
            for host in filter_names:
                hosts.append(f'match("*{host}*", host.name)')
            i2_filters += '(' + ' || '.join(hosts) + ')'
        else:

            # if user provided just one name we search for hosts and services with this name
            if len(filter_names) == 1:
                i2_filters += '( match("*%s*", host.name) || match("*%s*", service.name) )' % \
                              ( filter_names[0], filter_names[0])

            # if user provided more then one name we use the first and second name to search for host and service
            # all additional names are being ignored
            # example: testserver ntp
            #   hostname: testserver, service: ntp
            #   hostname: ntp, service testserver
            else:
                i2_filters += '( match("*%s*", host.name) && match("*%s*", service.name) )' % \
                              ( filter_names[0], filter_names[1])
                i2_filters += ' || ( match("*%s*", host.name) && match("*%s*", service.name) )' % \
                              ( filter_names[1], filter_names[0])

    logging.debug("Used filter for Icinga2 query: %s" % i2_filters)

    try:
        i2_response = i2_handle.objects.list(type, attrs=list_attrs, filters=i2_filters)

    except Icinga2ApiException as e:
        i2_error = str(e)
        if "failed with status" in i2_error:
            error = i2_error.split(" failed with status ")[1]
            return_code, icinga_return = error.split(":", 1)
            icinga_return = json.loads(icinga_return)
            i2_error = "Error %s: %s" % ( return_code, icinga_return.get("status"))

            if int(return_code) == 404:
                i2_response = "No match for %s" % filter_states
                if filter_names:
                    i2_response += " and %s" % filter_names
                i2_response += " found."

                i2_error = None
            pass

    except Exception as e:
        i2_error = str(e)
        pass

    if i2_error is None and i2_response is not None and isinstance(i2_response, list):
        response_objects = list()
        for object in i2_response:
            response_objects.append(object.get("attrs"))
        i2_response = response_objects

        logging.debug("Icinga2 returned with %d results" % len(i2_response))

    if i2_error:
        logging.error("Unable to query Icinga2 status: %s" % i2_error)

    return i2_response, i2_error

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

    logging.debug("Start compiling Icinga2 filters for received message: %s" % slack_message)

    if slack_message.strip() is not "":
        filter_options = slack_message.split(" ")

    # define valid state filter options
    valid_filter_states = {
        "up": {
            "type": "Host",
            "state_id": host_states.UP
        },
        "down": {
            "type": "Host",
            "state_id": host_states.DOWN
        },
        "unreachable": {
            "type": "Host",
            "state_id": host_states.UNREACHABLE
        },
        "ok": {
            "type": "Service",
            "state_id": service_states.OK
        },
        "warning": {
            "type": "Service",
            "state_id": service_states.WARNING
        },
        "critical": {
            "type": "Service",
            "state_id": service_states.CRITICAL
        },
        "unknown": {
            "type": "Service",
            "state_id": service_states.UNKNOWN
        }
    }

    # use a copy of filter_options to not remove items from current iteration
    for filter_option in list(filter_options):

        logging.debug("Checking Filter option: %s" % filter_option)

        unaltered_filter_option = filter_option

        if filter_option == "unreach":
            filter_option = "unreachable"
        if filter_option == "warn":
            filter_option = "warning"
        if filter_option == "crit":
            filter_option = "critical"

        if valid_filter_states.get(filter_option):
            this_filter_state = valid_filter_states.get(filter_option)

            if type == this_filter_state.get("type"):
                filter_string = "%s.state == %d" % \
                    (this_filter_state.get("type").lower(),
                     this_filter_state.get("state_id"))

                if not filter_string in filter_states:
                    filter_states.append(filter_string)
            else:
                if not filter_option in filter_error:
                    filter_error.append(filter_option)

            filter_options.remove(unaltered_filter_option)

    # get problem host/services if no filters are requested
    if len(filter_states) == 0 and not "all" in filter_options and len(filter_options) == 0:
        if type is "Host":
            filter_states.append("host.state != HostUP")
        else:
            filter_states.append("service.state != ServiceOK")

    # remove all attribute from filter
    if "all" in filter_options:
        filter_options.remove("all")

    if len(filter_error) == 0:
        filter_error = None

    # remaining command will be used to match host/service name
    logging.debug("Filter states: %s" % filter_states)
    logging.debug("Filter names: %s" % filter_options)
    logging.debug("Filter errors: %s" % filter_error)

    return filter_states, filter_options, filter_error

def get_single_block(text):
    """return a slack message block

    Parameters
    ----------
    text : str
        text to add to slack message block
        obeys var slack_max_block_text_length

    Returns
    -------
    dict
        returns a slack message block dictionary
    """

    # limit text to 3000 characters
    if len(text) > slack_max_block_text_length:
        text = "%s..." % text[:(slack_max_block_text_length - 3)]

    return [
        {"type": "section", "text": {"type": "mrkdwn", "text": text}},
    ]

def format_response(type="Host", result_objects = list()):
    """Format a slack response

    The objects will be sorted after name before they are compiled into
    a response. Service objects will first be sorted after host name and
    then after service name

    Parameters
    ----------
    type : str
        the object type to request (Host or Service)
    result_objects : list
        a list of objects to include in the Slack message

    Returns
    -------
    list
        returns a list of slack message blocks
    """

    global config

    response_blocks = None
    current_host = None
    service_list = list()
    response_objects = list()

    # no service problems
    if len(result_objects) is not 0:

        # sort objects
        if type is "Host":
            result_objects = sorted(result_objects, key=lambda k: k['name'])
            object_emojies = enum(":white_check_mark:", ":red_circle:", ":red_circle:")
        else:
            result_objects = sorted(result_objects, key=lambda k: (k['host_name'], k['name']))
            object_emojies = enum(":white_check_mark:", ":warning:", ":red_circle:", ":question:")

        response_blocks = []

        # append an "end marker" to avoid code redundancy
        result_objects.append({ "last_object" : True })
        for object in result_objects:
            last_check = object.get("last_check_result")
            if type is "Host":

                text = "{state_emoji} <{web2_url}/monitoring/host/show?host={host_name}|{host_name}>: {output}".format(
                    state_emoji=object_emojies.reverse[object.get("state")], web2_url=config["icinga.web2_url"],
                    host_name=object.get("name"), output=last_check.get("output")
                )

                response_objects.append(text)

            else:
                if (current_host and current_host != object.get("host_name")) or object.get("last_object"):
                    host_text = "<{web2_url}/monitoring/host/show?host={host_name}|{host_name}>".format(
                        web2_url=config["icinga.web2_url"], host_name=current_host
                    )
                    text = "*%s* (%d services)" % (host_text, len(service_list))

                    response_objects.append(text)
                    response_objects.extend(service_list)
                    service_list = []

                # stop if we found the "end marker"
                if object.get("last_object"):
                    break

                current_host = object.get("host_name")

                service_text = "&gt;{state_emoji} <{web2_url}/monitoring/service/show?host={host_name}" + \
                               "&amp;service={service_name}|{service_name}>: {output}"

                service_text = service_text.format(
                    state_emoji=object_emojies.reverse[object.get("state")], web2_url=config["icinga.web2_url"],
                    host_name=current_host, service_name=object.get("name"), output=last_check.get("output")
                )

                service_list.append(service_text)

    block_text = ""
    for object in response_objects:

        if len(block_text) + len(object) + 2 > slack_max_block_text_length:
            response_blocks.extend(get_single_block(block_text))
            block_text = ""

        block_text += "%s\n\n" % object

    else:
        response_blocks.extend(get_single_block(block_text))

    return response_blocks

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

    global github_logo_url

    response_text = None
    response_blocks = None
    response_attachment = None
    status_type = None

    default_response_text = "I didn't understand the command. Please use `help` for more details."

    matches = re.search(mention_regex, slack_message)
    if matches:
        slack_message = matches.group(2).strip()

    # lowercase makes parsing easier
    slack_message = slack_message.lower()

    if slack_message.startswith("ping"):

        logging.debug("Found 'ping' command")
        response_text = "pong :table_tennis_paddle_and_ball:"

    elif slack_message.startswith("help"):

        logging.debug("Found 'help' command")

        commands = {
            "help":                 "this help",
            "ping":                 "bot will answer with `pong`",
            "service status (ss)":  "display service status of all services in non OK state",
            "host status (hs)":     "display host status of all hosts in non UP state"
        }

        fields = list()
        for command, description in commands.items():
            fields.append({
                "title": "`<bot> %s`" % command,
                "value": description
            })

        response_text = "Bot help"
        response_blocks = get_single_block("*Following commands are implemented*")
        response_attachment = [
            {
                "fallback" : response_text,
                "color": "#03A8F3",
                "fields": fields,
                "footer": f"<{__url__}#command-status-filter|Further Help @ GitHub>",
                "footer_icon": github_logo_url
            }
        ]

    elif slack_message.startswith("service status") or slack_message.startswith("ss"):

        logging.debug("Found 'service status' command")

        status_type = "Service"

        if slack_message.startswith("ss"):
            slack_message = slack_message[len("ss"):].strip()
        else:
            slack_message = slack_message[len("service status"):].strip()

    elif slack_message.startswith("host status") or slack_message.startswith("hs"):

        logging.debug("Found 'host status' command")

        status_type = "Host"

        if slack_message.startswith("hs"):
            slack_message = slack_message[len("hs"):].strip()
        else:
            slack_message = slack_message[len("host status"):].strip()

    # query icinga
    if status_type:

        i2_filter_status, i2_filter_names, i2_filter_error = get_i2_filter(status_type, slack_message)

        # inform user about the filter mistake
        if i2_filter_error:

            logging.debug("Found error during filter compilation. Icinga2 won't be queried.")

            if len(i2_filter_error) == 1:
                i2_error_response = "filter '%s' not valid for %s status commands,\ncheck `help` command" % \
                                    (i2_filter_error[0], status_type)
            else:
                i2_error_response = \
                    "filters '%s' and '%s' are not valid for %s status commands,\ncheck `help` command" % \
                    ("', '".join(i2_filter_error[:-1]), i2_filter_error[-1], status_type)

            response_text = "Command error"
            response_blocks = get_single_block("*I'm having trouble understanding what you meant*")
            response_attachment = [
                {
                    "fallback" : response_text,
                    "color": "danger",
                    "text": i2_error_response
                }
            ]

        else:

            # get icinga objects
            i2_response, i2_error = get_i2_object(status_type, i2_filter_status, i2_filter_names)

            if i2_error:
                response_text = "Icinga request error"
                response_blocks = get_single_block("*%s*" % response_text)
                response_attachment = [
                    {
                        "fallback": response_text,
                        "color": "danger",
                        "text": "Error: %s" % i2_error
                    }
                ]

            elif type(i2_response) is str:
                response_text = "Icinga status response"
                response_blocks = get_single_block(i2_response)
            else:
                response_text = "Icinga status response"
                response_blocks = format_response(status_type, i2_response)

            if not response_blocks:
                response_text = "No problematic %s objects found. Everything seems in good condition." \
                                % status_type.lower()

    if not response_text and not response_blocks and not response_attachment:
        response_text = default_response_text
        response_blocks = get_single_block(default_response_text)

    return response_text, response_blocks, response_attachment

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
        bot_id = data.get("bot_id")

        # don't answer if message was sent by a bot
        if bot_id is not None:
            return

        logging.debug("Received new Slack message: %s" % data.get("text"))

        # parse command
        message_text, message_blocks, message_attachments = await handle_command(data.get("text"))

        if message_attachments:
            message_attachments = json.dumps(message_attachments)

        post_slack_message(web_client, channel_id, message_text, message_blocks, message_attachments)

    return

def post_slack_message(handle = None,
                       channel = None,
                       message_text = None,
                       message_blocks = None,
                       message_attachments = None):
    """post a message to Slack

    Parameters
    ----------
    handle: object
        the Slack client hand to use
    channel: str
        Slack channel to post message to
    message_text: str
        message to post to Slack
    message_blocks: str, optional
        message in blocks format
    message_attachments: list, optional
        list of slack attachments

    Returns
    -------
    tuple
        returns a tuple with two elements
            response: slack response object
            error: error string if error occurred
    """

    error = None
    response = None

    if handle is None:
        return response, "Error in function 'post_slack_message': no client handle defined"
    if channel is None:
        return response, "Error in function 'post_slack_message': no channel defined"
    if message_text is None:
        return response, "Error in function 'post_slack_message': no message text defined"

    # use lambda function to split message_blocks zu chunks of 'slack_max_message_blocks' blocks
    split_blocks = lambda a, n=slack_max_message_blocks: [a[i:i + n] for i in range(0, len(a), n)]

    if message_blocks and len(message_blocks) > 50:
        logging.debug("Sending multiple Slack messages as the number of blocks %d exceeds the maximum of %d" %
                      (len(message_blocks), slack_max_message_blocks))

    # post the message
    for message_blocks in split_blocks(message_blocks):

        try:
            logging.debug("Posting Slack message to channel '%s'" % channel)

            response = handle.chat_postMessage(
                channel=channel,
                text=message_text[:slack_max_message_text_length],
                blocks=message_blocks,
                attachments=message_attachments
            )

        except slack.errors.SlackApiError as e:
            response = e.response
            error = response.get("error")

        except Exception as e:
            error = str(e)

        if error:
            logging.error("Posting Slack message to channel '%s' failed: " % error)

    # only the response of the last message will be returned
    return response, error


if __name__ == "__main__":
    """main 'function' will setup the Slack bot and initialize connections"""

    ################
    #   parse command line
    args = parse_command_line()

    ################
    #   setup logging
    setup_logging(args.log_level)

    logging.info("Starting " + __description__)

    ################
    #   parse config file(s)
    config = parse_own_config(args.config_file)

    if not config:
        do_error_exit("Config parsing error")

    # set up slack ssl context
    slack_ssl_context = ssl_lib.create_default_context(cafile=certifi.where())

    # set up icinga
    i2_status_response, i2_status_error = get_i2_status("IcingaApplication")

    if i2_status_error:

        # format error message block
        status_text = "Icinga connection error during bot start"
        status_blocks = get_single_block("*%s*" % status_text)
        status_attachments = [
            {
                "fallback": status_text,
                "color": "danger",
                "text": i2_status_error
            }
        ]

    else:

        # get icinga app status from response
        icing_status = i2_status_response["results"][0]["status"]["icingaapplication"]["app"]
        icinga_start_date_time = datetime.fromtimestamp(icing_status["program_start"])

        icinga_status_text = list()
        icinga_status_text.append("Successfully connected to Icinga")
        icinga_status_text.append("Node name: *%s*" % icing_status["node_name"])
        icinga_status_text.append("Version: *%s*" % icing_status["version"])
        icinga_status_text.append("Running since: *%s*" % icinga_start_date_time.strftime("%Y-%m-%d %H:%M:%S"))

        # format message block
        status_text = "Starting up %s" % __description__
        status_blocks = get_single_block("*%s*" % status_text)
        status_attachments = [
            {
                "fallback": status_text,
                "color": "good",
                "text": "\n\t".join(icinga_status_text)
            }
        ]

    # message about start
    client = slack.WebClient(token=config["slack.bot_token"], ssl=slack_ssl_context)

    slack_startup_message_response, slack_startup_message_error = \
        post_slack_message(client,
                           config["slack.default_channel"],
                           status_text,
                           status_blocks,
                           status_attachments)
    del client

    if slack_startup_message_error:
        do_error_exit("Error while posting startup message to slack (%s): %s" %
                      (config["slack.default_channel"], slack_startup_message_error))


    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    rtm_client = slack.RTMClient(
        token=config["slack.bot_token"], ssl=slack_ssl_context, run_async=True, loop=loop
    )
    loop.run_until_complete(rtm_client.start())

# EOF
