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


#################
#
#   import extra modules
#

import certifi
import slack
from icinga2api.client import Client as I2Client, Icinga2ApiException


__version__ = "0.0.1"
__version_date__ = "2019-07-02"
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

max_messages_to_display_detailed_status = 4

#################
#
#   internal vars
#

mention_regex = "^<@(|[WU].+?)>(.*)"

# define valid log levels
valid_log_levels = [ "DEBUG", "INFO", "WARNING", "ERROR"]

args = None
config = None

plural = lambda x : "s" if x != 1 else ""
yes_no = lambda x: "Yes" if x > 0 else "No"


#################
#
#   classes
#

class SlackResponse:
    """
    A class used to represent a Slack Response

    Attributes
    ----------
    text : str
        a string which will be used in "text" attribute of the Slack Post
    blocks : str, list, dict
        holds all the Slack message blocks
    attachments : list, dict, SlackAttachment
        holds all the Slack message attachments

    Methods
    -------
    add_blocks(block)
        add a Slack message block. If 'block' is a string it will be converted into
        a block using method get_single_block()
    add_attachment(attachment)
        adds a new attachment to this response.
    dump_attachments()
        returns this.attachments as json blob
    get_single_block(text)
        return a slack message block
    """

    def __init__(self,
                 text = None,
                 blocks = None,
                 attachments = None):
        self.text = text
        self.blocks = []
        self.attachments = []

        if blocks:
            self.add_block(blocks)

        if attachments:
            self.add_attachment(attachments)

    def add_block(self, block):

        if block is None or len(block) == 0:
            return
        if isinstance(block, dict):
            self.blocks.append(block)
        elif isinstance(block, list):
            self.blocks.extend(block)
        else:
            self.blocks.extend(self.get_single_block(block))

    def add_attachment(self, attachment):

        if attachment is None or len(attachment) == 0:
            return
        if isinstance(attachment, dict):
            self.attachments.append(attachment)
        elif isinstance(attachment, list):
            self.attachments.extend(attachment)
        elif isinstance(attachment, SlackAttachment):
            self.attachments.append(vars(attachment))

    def dump_attachments(self):

        if len(self.attachments) == 0:
            return None

        return json.dumps(self.attachments)

    @staticmethod
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

class SlackAttachment:
    """
    A simple placeholder class to manipulate attachments
    """

    def __init__(self):
        pass


class RequestResponse:
    """
    A class used to hold responses for different kinds of requests
    """

    def __init__(self,
                 response = None,
                 error = None):

        self.response = response
        self.error = error

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

    Parameters
    ----------
    application : str, optional
        application to request (defaults are all applications)

    Returns
    -------
    RequestResponse: with Icinga2 status
    """

    response = RequestResponse()

    i2_handle, i2_error  = setup_icinga_connection()

    if not i2_handle:
        if i2_error is not None:
            return RequestResponse(error=i2_error)
        else:
            return RequestResponse(error="Unknown error while setting up Icinga2 connection")

    try:
        logging.debug("Requesting Icinga2 status for application: %s " % application)

        response.response = i2_handle.status.list(application)

    except Exception as e:
        response.error = str(e)
        logging.error("Unable to query Icinga2 status: %s" % response.error)
        pass

    return response

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
    RequestResponse: with Icinga host/service objects
    """

    response = RequestResponse()
    i2_filters = None

    i2_handle, i2_error = setup_icinga_connection()

    if not i2_handle:
        if i2_error is not None:
            return RequestResponse(error=i2_error)
        else:
            return RequestResponse(error="Unknown error while setting up Icinga2 connection")

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
                hosts.append('match("*%s*", host.name)' % host)
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
            #   hostname: ntp, service: testserver
            else:
                i2_filters += '( match("*%s*", host.name) && match("*%s*", service.name) )' % \
                              ( filter_names[0], filter_names[1])
                i2_filters += ' || ( match("*%s*", host.name) && match("*%s*", service.name) )' % \
                              ( filter_names[1], filter_names[0])

    logging.debug("Used filter for Icinga2 query: %s" % i2_filters)

    try:
        response.response = i2_handle.objects.list(type, attrs=list_attrs, filters=i2_filters)

    except Icinga2ApiException as e:
        response.error = str(e)
        if "failed with status" in response.error:
            error = response.error.split(" failed with status ")[1]
            return_code, icinga_return = error.split(":", 1)
            icinga_return = json.loads(icinga_return)
            response.error = "Error %s: %s" % ( return_code, icinga_return.get("status"))

            if int(return_code) == 404:
                response.response = "No match for %s" % filter_states
                if filter_names:
                    response.response += " and %s" % filter_names
                response.response += " found."

                response.error = None
            pass

    except Exception as e:
        response.error = str(e)
        pass

    if response.error is None and response.response is not None and isinstance(response.response, list):
        response_objects = list()
        for object in response.response:
            response_objects.append(object.get("attrs"))
        response.response = response_objects

        # sort objects
        if type is "Host":
            response.response = sorted(response.response, key=lambda k: k['name'])
        else:
            response.response = sorted(response.response, key=lambda k: (k['host_name'], k['name']))

        logging.debug("Icinga2 returned with %d results" % len(response.response))

    if response.error:
        logging.error("Unable to query Icinga2 status: %s" % response.error)

    return response

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

def get_web2_slack_url(host, service = None):
    """
    Return a Slack formatted hyperlink

    Parameters
    ----------
    host: str
        host name to use for url. If service is None a hyperlink
        to a Icingaweb2 host page will be returned
    service : str, optional
        service name to use for url. A hyperlink
        to a Icingaweb2 service page will be returned

    Returns
    -------
    str: formatted url
    """

    if host is None:
        return

    if service:
        url = "<{web2_url}/monitoring/service/show?host={host_name}&amp;service={service_name}|{service_name}>"
    else:
        url = "<{web2_url}/monitoring/host/show?host={host_name}|{host_name}>"

    url = url.format(web2_url=config["icinga.web2_url"], host_name=host, service_name=service)

    return url

def format_response(type="Host", result_objects = list()):
    """Format a slack response

    The objects will compiled into Slack message blocks.
    This function will try to fill up blocks until
    'slack_max_block_text_length' is reached.

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

    response = SlackResponse()
    current_host = None
    service_list = list()
    response_objects = list()

    if len(result_objects) != 0:

        # set state emoji
        if type is "Host":
            object_emojies = enum(":white_check_mark:", ":red_circle:", ":red_circle:")
        else:
            object_emojies = enum(":white_check_mark:", ":warning:", ":red_circle:", ":question:")

        # append an "end marker" to avoid code redundancy
        result_objects.append({ "last_object" : True })

        # add formatted text for each object to response_objects
        for object in result_objects:
            last_check = object.get("last_check_result")

            if type is "Host":

                # stop if we found the "end marker"
                if object.get("last_object"):
                    break

                text = "{state_emoji} {url}: {output}".format(
                    state_emoji=object_emojies.reverse[object.get("state")],
                    url=get_web2_slack_url(object.get("name")), output=last_check.get("output")
                )

                response_objects.append(text)

            else:
                if (current_host and current_host != object.get("host_name")) or object.get("last_object"):

                    text = "*%s* (%d service%s)" % \
                           (get_web2_slack_url(current_host), len(service_list), plural(len(service_list)))

                    response_objects.append(text)
                    response_objects.extend(service_list)
                    service_list = []

                # stop if we found the "end marker"
                if object.get("last_object"):
                    break

                current_host = object.get("host_name")

                service_text = "&gt;{state_emoji} {url}: {output}"

                service_text = service_text.format(
                    state_emoji=object_emojies.reverse[object.get("state")],
                    url=get_web2_slack_url(current_host, object.get("name")), output=last_check.get("output")
                )

                service_list.append(service_text)

    # fill blocks with formatted response
    block_text = ""
    for object in response_objects:

        if len(block_text) + len(object) + 2 > slack_max_block_text_length:
            response.add_block(block_text)
            block_text = ""

        block_text += "%s\n\n" % object

    else:
        response.add_block(block_text)

    return response.blocks

def run_icinga_status_query(status_type = None, slack_message = None):
    """
    Query Icinga2 to get host/service status based on Slack command

    First the Slack message will be parsed for object status and
    names. Then the response will be compiled based on the amount
    of returned objects. A more detailed object list will be returned
    if the results are 'max_messages_to_display_detailed_status' or less.

    Parameters
    ----------
    status_type : str
        the object type to request (Host or Service)
    slack_message : string
        the Slack command which will be parsed


    Returns
    -------
    SlackResponse: with command result
    """

    response = SlackResponse()

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

        response.text = "Command error"
        response.add_block("*I'm having trouble understanding what you meant*")
        response.add_attachment(
            {
                "fallback":  response.text,
                "text" : i2_error_response,
                "color": "danger"
            }
        )

    else:

        # get icinga objects
        i2_response = get_i2_object(status_type, i2_filter_status, i2_filter_names)

        if i2_response.error:
            response.text = "Icinga request error"
            response.add_block("*%s*" % response.text)
            response.add_attachment(
                {
                    "fallback":  response.text,
                    "text" : "Error: %s" % i2_response.error,
                    "color": "danger"
                }
            )

        # Just a String was returned
        elif type(i2_response.response) is str:
            response.text = "Icinga status response"
            response.add_block(i2_response.response)

        # show more detailed information if only a few objects are returned
        elif len(i2_response.response) in list(range(1, (max_messages_to_display_detailed_status +1))):

            response.text = "Icinga status response"
            block_text = "Found %d matching %s%s" % \
                         (len(i2_response.response), status_type.lower(), plural(len(i2_response.response)))

            response.add_block(block_text)

            for object in i2_response.response:
                if object.get("host_name"):
                    host_name = object.get("host_name")
                    service_name = object.get("name")
                    states = enum("OK", "WARNING", "CRITICAL", "UNKNOWN")
                    colors = enum("good", "warning", "danger", "#E066FF")
                else:
                    host_name = object.get("name")
                    service_name = None
                    states = enum("UP", "DOWN", "UNREACHABLE")
                    colors = enum("good", "danger", "danger")

                host_url = get_web2_slack_url(host_name)
                service_url = get_web2_slack_url(host_name,service_name)

                if object.get("host_name"):
                    text = "*%s | %s*" % (host_url, service_url)
                else:
                    text = "*%s*" % host_url

                object_fields = {
                    "Output": object.get("last_check_result").get("output"),
                    "Last State Change": ts_to_date(object.get("last_state_change")),
                    "Status": states.reverse[object.get("state")],
                    "Acknowledged": yes_no(object.get("acknowledgement")),
                    "In Downtime": yes_no(object.get("downtime_depth"))
                }

                fields = list()
                for title, value in object_fields.items():
                    short = True
                    if title in ["Output"]:
                        short = False
                    fields.append({
                        "title": title,
                        "value": value,
                        "short": short
                    })

                response.add_attachment(
                    {
                        "color": colors.reverse[object.get("state")],
                        "text": text,
                        "fields": fields
                    }
                )

        # the more condensed object list
        elif len(i2_response.response) > 0:

            block_text = "Found %d matching %s%s" % \
                         (len(i2_response.response), status_type.lower(), plural(len(i2_response.response)))

            response.text = "Icinga status response"
            response.add_block(block_text)
            response.add_block(format_response(status_type, i2_response.response))

        # the result returned empty
        else:
            problematic_text = ""

            if len(i2_filter_status) == 1 and \
               i2_filter_status[0] in ["host.state != HostUP", "service.state != ServiceOK"]:
                problematic_text = "problematic "

            response.text = "No %s%s objects " % (problematic_text,status_type.lower())

            if len(i2_filter_names) == 1:
                response.text += "for '%s' " % i2_filter_names[0]
            elif len(i2_filter_names) > 1:
                response.text += "for '%s' and '%s' " % ("', '".join(i2_filter_names[:-1]), i2_filter_names[-1])

            response.text += "found."

            if len(problematic_text) != 0:
                response.text += " Everything seems in good condition."

    return response

def slack_command_help():
    """
    Return a short command description

    Returns
    -------
    SlackResponse: with help text
    """

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

    return SlackResponse(
        text = "Bot help",
        blocks = "*Following commands are implemented*",
        attachments = {
            "fallback" : "Bot help",
            "color": "#03A8F3",
            "fields": fields,
            "footer": "<%s#command-status-filter|Further Help @ GitHub>" % __url__,
            "footer_icon": github_logo_url
        }
    )

def ts_to_date(ts, format = "%Y-%m-%d %H:%M:%S"):
    """
    Return a formatted date/time string from a given time stamp

    Parameters
    ----------
    ts : int, float
        time stamp to convert
    format : string
        format to convert time stamp to

    Returns
    -------
    str: formatted date/time string
    """
    return datetime.fromtimestamp(ts).strftime(format)

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
    SlackResponse: with response for Slack command
    """

    response = None
    status_type = None

    default_response_text = "I didn't understand the command. Please use `help` for more details."

    matches = re.search(mention_regex, slack_message)
    if matches:
        slack_message = matches.group(2).strip()

    # lowercase makes parsing easier
    slack_message = slack_message.lower()

    if slack_message.startswith("ping"):

        logging.debug("Found 'ping' command")

        response = SlackResponse(
            text = "pong :table_tennis_paddle_and_ball:"
        )

    elif slack_message.startswith("help"):

        logging.debug("Found 'help' command")

        response = slack_command_help()

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
        response = run_icinga_status_query(status_type, slack_message)

    if not response:

        response = SlackResponse(
            text = default_response_text
        )

    return response

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

        # parse command
        response = await handle_command(data.get("text"))

        slack_api_response = post_slack_message(web_client, channel_id, response)

        if slack_api_response.error:

            # format error message block
            header_text = "Slack API error while posting to Slack"
            error_message = SlackResponse(
                text = header_text,
                blocks = "*%s*" % header_text,
                attachments = {
                    "fallback": header_text,
                    "text": slack_api_response.error,
                    "color": "danger"
                }
            )

            post_slack_message(web_client, channel_id, error_message)

    return

def post_slack_message(handle = None, channel = None, slack_response = None):
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
    i2_status = get_i2_status("IcingaApplication")

    status_reply = SlackResponse()
    status_color = "good"

    if i2_status.error:

        # format error message block
        status_header = "Icinga connection error during bot start"
        status_text = i2_status.error
        status_color = "danger"

    else:

        # get icinga app status from response
        icing_status = i2_status.response["results"][0]["status"]["icingaapplication"]["app"]

        icinga_status_text = list()
        icinga_status_text.append("Successfully connected to Icinga")
        icinga_status_text.append("Node name: *%s*" % icing_status["node_name"])
        icinga_status_text.append("Version: *%s*" % icing_status["version"])
        icinga_status_text.append("Running since: *%s*" % ts_to_date(icing_status["program_start"]))

        status_header = "Starting up %s" % __description__
        status_text = "\n\t".join(icinga_status_text)

    status_reply.text = status_header
    status_reply.add_block("*%s*" % status_header)
    status_reply.add_attachment(
        {
            "fallback": status_header,
            "text": status_text,
            "color": status_color
        }
    )

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
