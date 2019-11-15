####
#
# Some Slack helper function to format messages properly
#

from . import plural, slack_max_block_text_length
from .common import enum
from .classes import SlackResponse


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


def format_slack_response(config, object_type="Host", result_objects=None):
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

    Returns
    -------
    list
        returns a list of slack message blocks
    """

    response = SlackResponse()
    current_host = None
    service_list = list()
    response_objects = list()
    num_results = 0

    if result_objects and len(result_objects) != 0:

        # set state emoji
        if object_type is "Host":
            object_emojies = enum(":white_check_mark:", ":red_circle:", ":octagonal_sign:")
        else:
            object_emojies = enum(":white_check_mark:", ":warning:", ":red_circle:", ":question:")

        # append an "end marker" to avoid code redundancy
        result_objects.append({"last_object": True})

        # add formatted text for each object to response_objects
        for result_object in result_objects:
            last_check = result_object.get("last_check_result")

            if object_type is "Host":

                # stop if we found the "end marker"
                if result_object.get("last_object"):
                    break

                text = "{state_emoji} {url}: {output}".format(
                    state_emoji=object_emojies.reverse[int(result_object.get("state"))],
                    url=get_web2_slack_url(result_object.get("name"), web2_url=config["icinga.web2_url"]),
                    output=last_check.get("output")
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

                service_text = "&gt;{state_emoji} {url}: {output}"

                service_text = service_text.format(
                    state_emoji=object_emojies.reverse[result_object.get("state")],
                    url=get_web2_slack_url(current_host, result_object.get("name"), web2_url=config["icinga.web2_url"]),
                    output=last_check.get("output")
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
    SlackResponse: response with error message
    """

    if header is None:
        header = "Bot internal error"

    if fallback_text is None:
        fallback_text = header

    if error_message is None:
        error_message = "Encountered a bot internal error. Please ask your bot admin for help."

    response = SlackResponse(text=fallback_text)
    response.add_block("*%s*" % header)
    response.add_attachment(
        {
            "fallback": fallback_text,
            "text": "Error: %s" % error_message,
            "color": "danger"
        }
    )

    return response
