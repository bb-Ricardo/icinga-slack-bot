####
#
#   Functions and classes to handle Icinga2 connections
#

import json
import logging

from icinga2api.client import Client as I2Client, Icinga2ApiException

from . import host_states, service_states


class RequestResponse:
    """
    A class used to hold responses for different kinds of requests
    """

    def __init__(self,
                 response=None,
                 error=None):

        self.response = response
        self.error = error


def setup_icinga_connection(config):
    """Setup an Icinga connection and pass all parameters

    Parameters
    ----------
    config : dict
        dictionary with items parsed from config file

    Returns
    -------
    tuple
        returns a tuple with two elements
            i2_handle: icinga2 client object
            i2_error: an error string in case a client connection failed
    """

    i2_handle = None
    i2_error = None

    default_icinga_connection_timeout = 5

    icinga_timeout = default_icinga_connection_timeout

    if config["icinga.timeout"] is not None and str(config["icinga.timeout"]) != "":
        icinga_timeout = int(config["icinga.timeout"])

    try:
        i2_handle = I2Client(url="https://" + config["icinga.hostname"] + ":" + config["icinga.port"],
                             username=config["icinga.username"], password=config["icinga.password"],
                             certificate=config["icinga.certificate"], key=config["icinga.key"],
                             ca_certificate=config["icinga.ca_certificate"], timeout=icinga_timeout)

    except Icinga2ApiException as e:
        i2_error = str(e)
        logging.error("Unable to set up Icinga2 connection: %s" % i2_error)
        pass

    logging.debug("Successfully connected to Icinga2")

    return i2_handle, i2_error


def get_i2_status(config, application=None):
    """Request Icinga2 API Endpoint /v1/status

    Parameters
    ----------
    config : dict
        dictionary with items parsed from config file

    application : str, optional
        application to request (defaults are all applications)

    Returns
    -------
    RequestResponse: with Icinga2 status
    """

    response = RequestResponse()

    i2_handle, i2_error = setup_icinga_connection(config)

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


def get_i2_object(config, object_type="Host", filter_states=None, filter_names=None):
    """Request Icinga2 API Endpoint /v1/objects

    Parameters
    ----------
    config : dict
        dictionary with items parsed from config file
    object_type : str
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

    i2_handle, i2_error = setup_icinga_connection(config)

    if not i2_handle:
        if i2_error is not None:
            return RequestResponse(error=i2_error)
        else:
            return RequestResponse(error="Unknown error while setting up Icinga2 connection")

    # default attributes to query
    list_attrs = ['name', 'state', 'last_check_result', 'acknowledgement', 'downtime_depth', 'last_state_change']

    # add host_name to attribute list if services are requested
    if object_type is "Service":
        list_attrs.append("host_name")

    if filter_states:
        i2_filters = '(' + ' || '.join(filter_states) + ')'

    if filter_names and len(filter_names) >= 1 and filter_names[0] is not "":
        if i2_filters:
            i2_filters += " && "
        else:
            i2_filters = str("")

        if object_type is "Host":

            hosts = list()
            for host in filter_names:
                hosts.append('match("*%s*", host.name)' % host)
            i2_filters += '(' + ' || '.join(hosts) + ')'
        else:

            # if user provided just one name we search for hosts and services with this name
            if len(filter_names) == 1:
                i2_filters += '( match("*%s*", host.name) || match("*%s*", service.name) )' % \
                              (filter_names[0], filter_names[0])

            # if user provided more then one name we use the first and second name to search for host and service
            # all additional names are being ignored
            # example: testserver ntp
            #   hostname: testserver, service: ntp
            #   hostname: ntp, service: testserver
            else:
                i2_filters += '( ( match("*%s*", host.name) && match("*%s*", service.name) )' % \
                              (filter_names[0], filter_names[1])
                i2_filters += ' || ( match("*%s*", host.name) && match("*%s*", service.name) ) )' % \
                              (filter_names[1], filter_names[0])

    if config["icinga.filter"] != "":
        if i2_filters:
            i2_filters = "(%s) && %s" % (i2_filters, config["icinga.filter"])
        else:
            i2_filters = "%s" % config["icinga.filter"]

    logging.debug("Used filter for Icinga2 query: %s" % i2_filters)

    try:
        response.response = i2_handle.objects.list(object_type, attrs=list_attrs, filters=i2_filters)

    except Icinga2ApiException as e:
        response.error = str(e)
        if "failed with status" in response.error:
            error = response.error.split(" failed with status ")[1]
            return_code, icinga_return = error.split(":", 1)
            icinga_return = json.loads(icinga_return)
            response.error = "Error %s: %s" % (return_code, icinga_return.get("status"))

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
        for response_object in response.response:
            response_objects.append(response_object.get("attrs"))
        response.response = response_objects

        # sort objects
        if object_type is "Host":
            response.response = sorted(response.response, key=lambda k: k['name'])
        else:
            response.response = sorted(response.response, key=lambda k: (k['host_name'], k['name']))

        logging.debug("Icinga2 returned with %d results" % len(response.response))

    if response.error:
        logging.error("Unable to query Icinga2 status: %s" % response.error)

    return response


def get_i2_filter(object_type="Host", slack_message=""):
    """Parse a Slack message and create lists of filters depending on the
    object type

    Parameters
    ----------
    object_type : str
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

    logging.debug("Start compiling Icinga2 filters for received message: %s" % slack_message)

    if slack_message.strip() is not "":
        filter_options = slack_message.split(" ")

    # define valid state filter options
    valid_filter_states = {
        "up": {
            "object_type": "Host",
            "state_id": host_states.UP
        },
        "down": {
            "object_type": "Host",
            "state_id": host_states.DOWN
        },
        "unreachable": {
            "object_type": "Host",
            "state_id": host_states.UNREACHABLE
        },
        "ok": {
            "object_type": "Service",
            "state_id": service_states.OK
        },
        "warning": {
            "object_type": "Service",
            "state_id": service_states.WARNING
        },
        "critical": {
            "object_type": "Service",
            "state_id": service_states.CRITICAL
        },
        "unknown": {
            "object_type": "Service",
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

            if object_type == this_filter_state.get("object_type"):
                filter_string = "%s.state == %d" % \
                                (this_filter_state.get("object_type").lower(),
                                 this_filter_state.get("state_id"))

                if filter_string not in filter_states:
                    filter_states.append(filter_string)
            else:
                if filter_option not in filter_error:
                    filter_error.append(filter_option)

            filter_options.remove(unaltered_filter_option)

    # get problem host/services if no filters are requested
    if len(filter_states) == 0 and "all" not in filter_options and len(filter_options) == 0:
        if object_type is "Host":
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