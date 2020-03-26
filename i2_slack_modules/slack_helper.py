####
#
# Some Slack helper function to format messages properly
#

from . import plural, slack_max_block_text_length
from .classes import BotResponse
from .icinga_states import IcingaStates


def get_web2_slack_url(host, service=None, web2_url=""):
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
    web2_url: str
        url to icingaweb2 instance
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

    url = url.format(web2_url=web2_url, host_name=host, service_name=service)

    return url


def format_slack_response(config, object_type="Host", result_objects=None, comment_downtime_list=None):
    """Format a slack response

    The objects will compiled into Slack message blocks.
    This function will try to fill up blocks until
    'slack_max_block_text_length' is reached.

    Parameters
    ----------
    config : dict
        dictionary with items parsed from config file
    object_type : str
        the object type to request (Host or Service)
    result_objects : list
        a list of objects to include in the Slack message
    comment_downtime_list: list
        a list of comments and downtimes which returned for the results , add speech bubble, zzz and handled

    Returns
    -------
    list
        returns a list of slack message blocks
    """

    response = BotResponse()
    current_host = None
    service_list = list()
    response_objects = list()
    num_results = 0
    icinga_states = IcingaStates()

    if result_objects and len(result_objects) != 0:

        # append an "end marker" to avoid code redundancy
        result_objects.append({"last_object": True})

        # add formatted text for each object to response_objects
        for result_object in result_objects:
            last_check = result_object.get("last_check_result")

            # take care of pending status which don't have a check result
            output = None
            if last_check is not None:
                output = last_check.get("output")

            # get comments for this object
            if object_type is "Host":
                object_comment_downtime_list = \
                    [item for item in comment_downtime_list
                     if item["host_name"] == result_object.get("name") and item["service_name"] == ""]
            else:
                object_comment_downtime_list = \
                    [item for item in comment_downtime_list
                     if item["host_name"] == result_object.get("host_name") and
                        item["service_name"] == result_object.get("name")]

            # add speech bubble if object has comments
            append_to_title = ""
            if len([item for item in object_comment_downtime_list if item['type'] == 'Comment']) > 0:
                append_to_title += " :speech_balloon:"

            # add zzz if object has downtime
            if len([item for item in object_comment_downtime_list if item['type'] == 'Downtime']) > 0:
                append_to_title += " :zzz:"

            # change attachment color and add hint to status text if object is taken care of
            if result_object.get("state") is not None and result_object.get("state") > 0:
                if result_object.get("acknowledgement") >= 1 or result_object.get("downtime_depth") >= 1:
                    append_to_title += " (handled)"

            if object_type is "Host":

                # stop if we found the "end marker"
                if result_object.get("last_object"):
                    break

                text = "{state_emoji} {url}{additional_info}: {output}".format(
                    state_emoji=icinga_states.value(result_object.get("state"), object_type).icon,
                    url=get_web2_slack_url(result_object.get("name"), web2_url=config["icinga.web2_url"]),
                    additional_info=append_to_title,
                    output=f"{output}"
                )

                response_objects.append(text)

            else:
                if (current_host and current_host != result_object.get("host_name")) or \
                        result_object.get("last_object"):

                    text = "*%s* (%d service%s)" % (
                        get_web2_slack_url(current_host, web2_url=config["icinga.web2_url"]),
                        len(service_list),
                        plural(len(service_list))
                    )

                    response_objects.append(text)
                    response_objects.extend(service_list)
                    service_list = []

                # stop if we found the "end marker"
                if result_object.get("last_object"):
                    break

                current_host = result_object.get("host_name")

                service_text = "&gt;{state_emoji} {url}{additional_info}: {output}"

                service_text = service_text.format(
                    state_emoji=icinga_states.value(result_object.get("state"), object_type).icon,
                    url=get_web2_slack_url(current_host, result_object.get("name"), web2_url=config["icinga.web2_url"]),
                    additional_info=append_to_title,
                    output=f"{output}"
                )

                service_list.append(service_text)

            num_results += 1

            if config["icinga.max_returned_results"] != "":
                if num_results >= int(config["icinga.max_returned_results"]):
                    if object_type is "Service":
                        text = "*%s* (%d service%s)" % (
                            get_web2_slack_url(current_host, web2_url=config["icinga.web2_url"]),
                            len(service_list),
                            plural(len(service_list))
                        )

                        response_objects.append(text)
                        response_objects.extend(service_list)

                    response_objects.append(":end: *reached maximum number (%s) of allowed results*" %
                                            config["icinga.max_returned_results"])
                    response_objects.append("\t\t*please narrow down your search pattern*")

                    break

    # fill blocks with formatted response
    block_text = ""
    for response_object in response_objects:

        if len(block_text) + len(response_object) + 2 > slack_max_block_text_length:
            response.add_block(block_text)
            block_text = ""

        block_text += "%s\n\n" % response_object

    else:
        response.add_block(block_text)

    return response.blocks


def slack_error_response(header=None, fallback_text=None, error_message=None):
    """generate a slack error response

    Parameters
    ----------
    header : str
        string which should be used as header (default: Bot internal error)
    fallback_text : str
        fallback text with e short error message (default: header)
    error_message : str
        a meaningful error description (default: see below)

    Returns
    -------
    BotResponse: response with error message
    """

    if header is None:
        header = "Bot internal error"

    if fallback_text is None:
        fallback_text = header

    if error_message is None:
        error_message = "Encountered a bot internal error. Please ask your bot admin for help."

    response = BotResponse(text=fallback_text)
    response.add_block("*%s*" % header)
    response.add_attachment(
        {
            "fallback": fallback_text,
            "text": "Error: %s" % error_message,
            "color": "danger"
        }
    )

    return response
