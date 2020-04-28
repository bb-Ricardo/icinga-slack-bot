
from i2_slack_modules import yes_no, enabled_disabled
from i2_slack_modules.common import ts_to_date
from i2_slack_modules.slack_helper import *
from i2_slack_modules.icinga_connection import *

max_messages_to_display_detailed_status = 4


# noinspection PyUnusedLocal
def run_icinga_status_query(config=None, slack_message=None, bot_commands=None, *args, **kwargs):
    """
    Query Icinga2 to get host/service status based on Slack command

    First the Slack message will be parsed for icinga_object status and
    names. Then the response will be compiled based on the amount
    of returned objects. A more detailed icinga_object list will be returned
    if the results are 'max_messages_to_display_detailed_status' or less.

    Parameters
    ----------
    config : dict
        dictionary with items parsed from config file
    slack_message : string
        the Slack command which will be parsed
    bot_commands: BotCommands
        class with bot commands to avoid circular imports
    args, kwargs: None
        used to hold additional args which are just ignored

    Returns
    -------
    BotResponse: with command result
    """

    # parse slack message and determine if this is a service or host status command
    # also strip off the command from the slack_message

    response = BotResponse()

    display_just_unhandled_objects_for_default_query = True

    command_start = None
    status_type = None

    icinga_states = IcingaStates()

    # lowercase makes parsing easier
    slack_message = slack_message.lower()

    called_command = bot_commands.get_command_called(slack_message)

    try:
        status_type = called_command.status_type
    except AttributeError:
        logging.error("Unable to get attribute 'status_type' for command %s" % called_command.name)
        return slack_error_response()

    # strip command from slack message
    slack_message = called_command.strip_command(slack_message)

    # take care of special request to get all problems and not just unhandled ones
    if slack_message.startswith("problems"):
        display_just_unhandled_objects_for_default_query = False

    i2_filter_status, i2_filter_names, i2_filter_error = get_i2_filter(status_type, slack_message)

    # inform user about the filter mistake
    if i2_filter_error:

        logging.info("Found error during filter compilation. Icinga2 won't be queried.")

        if len(i2_filter_error) == 1:
            i2_error_response = "filter '%s' not valid for %s status commands,\ncheck `help` command" % \
                                (i2_filter_error[0], status_type)
        else:
            i2_error_response = \
                "filters '%s' and '%s' are not valid for %s status commands,\ncheck `help` command" % \
                ("', '".join(i2_filter_error[:-1]), i2_filter_error[-1], status_type)

        response = slack_error_response(
            header="I'm having trouble understanding what you meant",
            fallback_text="Command error",
            error_message=i2_error_response
        )

    else:

        # get icinga objects
        acknowledged = None
        downtime = None
        if display_just_unhandled_objects_for_default_query and len(i2_filter_names) == 0:
            acknowledged = downtime = False

        i2_response = get_i2_object(config, status_type, i2_filter_status, i2_filter_names, acknowledged, downtime)
        i2_comments_response = get_i2_object(config, f"{status_type}Comment", i2_filter_status, i2_filter_names)
        i2_downtime_response = get_i2_object(config, f"{status_type}Downtime", i2_filter_status, i2_filter_names)

        if i2_response.error:
            response = slack_error_response(header="Icinga request error", error_message=i2_response.error)

        # Just a String was returned
        elif i2_response.text:
            response.text = "Icinga status response"
            response.add_block(i2_response.text)

        # show more detailed information if only a few objects are returned
        elif len(i2_response.data) in list(range(1, (max_messages_to_display_detailed_status + 1))):

            response.text = "Icinga status response"
            block_text = "Found %d matching %s%s" % \
                         (len(i2_response.data), status_type.lower(), plural(len(i2_response.data)))

            response.add_block(block_text)

            for icinga_object in i2_response.data:
                if icinga_object.get("host_name"):
                    host_name = icinga_object.get("host_name")
                    service_name = icinga_object.get("name")
                    comment_downtime_service_name = service_name
                    this_state = icinga_states.value(icinga_object.get("state"), "Service")
                else:
                    host_name = icinga_object.get("name")
                    service_name = None
                    comment_downtime_service_name = ""
                    this_state = icinga_states.value(icinga_object.get("state"), "Host")

                attachment_color = this_state.color

                host_url = get_web2_slack_url(host_name, web2_url=config["icinga.web2_url"])
                service_url = get_web2_slack_url(host_name, service_name, web2_url=config["icinga.web2_url"])

                if icinga_object.get("host_name"):
                    text = "*%s | %s*" % (host_url, service_url)
                else:
                    text = "*%s*" % host_url

                # get comments for this object
                object_comment_list = \
                    [item for item in i2_comments_response.data
                     if item["host_name"] == host_name and item["service_name"] == comment_downtime_service_name]

                # get downtimes for this object
                object_downtime_list = \
                    [item for item in i2_downtime_response.data
                     if item["host_name"] == host_name and item["service_name"] == comment_downtime_service_name]

                # add speech bubble if object has comments
                if len(object_comment_list) > 0:
                    text += " :speech_balloon:"

                # add zzz if object has downtimes
                if len(object_downtime_list) > 0:
                    text += " :zzz:"

                # change attachment color and add hint to status text if object is taken care of
                if icinga_object.get("state") > 0:
                    if icinga_object.get("acknowledgement") >= 1 or icinga_object.get("downtime_depth") >= 1:
                        text += " (handled)"
                        attachment_color = None

                # take care of pending status which don't have a check result
                status_output = None
                if icinga_object.get("last_check_result") is not None:
                    status_output = icinga_object.get("last_check_result").get("output")

                object_fields = {
                    "Output": f"{status_output}",
                    "Last state change": ts_to_date(icinga_object.get("last_state_change")),
                    "Status": this_state.name,
                    "Acknowledged": yes_no(icinga_object.get("acknowledgement")),
                    "In downtime": yes_no(icinga_object.get("downtime_depth")),
                    "Event handlers": enabled_disabled(icinga_object.get("enable_event_handler")),
                    "Flap detection": enabled_disabled(icinga_object.get("enable_flapping")),
                    "Active checks": enabled_disabled(icinga_object.get("enable_active_checks")),
                    "Passive checks": enabled_disabled(icinga_object.get("enable_passive_checks")),
                    "Notifications": enabled_disabled(icinga_object.get("enable_notifications")),
                }

                # add comment to object attachment
                for comment in object_comment_list:
                    this_type = "Comment"
                    if comment.get("entry_type", 1) == 4:
                        this_type = "Acknowledgement"
                    comment_title = "{} by {} ({})".format(this_type, comment.get("author"),
                                                           ts_to_date(comment.get("entry_time")))

                    # add text and info about expiration
                    comment_text = comment.get("text")
                    if comment.get("expire_time") is not None and comment.get("expire_time") > 0:
                        comment_text += " (expires: {})".format(ts_to_date(comment.get("expire_time")))

                    object_fields[comment_title] = f"`{comment_text}`"

                # add downtime info to object attachment
                for downtime in object_downtime_list:
                    downtime_title = "Downtime by {} ({})".format(downtime.get("author"),
                                                                  ts_to_date(downtime.get("entry_time")))

                    # add text and info about expiration
                    downtime_text = downtime.get("comment")
                    if downtime.get("fixed") is True:
                        downtime_text += " (fixed from {} until {})".format(
                            ts_to_date(downtime.get("start_time")), ts_to_date(downtime.get("end_time")))
                    else:
                        downtime_text += " (flexible for {} minutes between {} and {})".format(
                            downtime.get("duration") / 60,
                            ts_to_date(downtime.get("start_time")), ts_to_date(downtime.get("end_time")))

                    object_fields[downtime_title] = f"`{downtime_text}`"

                fields = list()
                for title, value in object_fields.items():
                    short = True
                    if any(x in title for x in ["Output", "Comment", "Downtime", "Acknowledgement"]):
                        short = False
                    fields.append({
                        "title": title,
                        "value": value,
                        "short": short
                    })

                response.add_attachment(
                    {
                        "color": attachment_color,
                        "text": text,
                        "fields": fields
                    }
                )

        # the more condensed icinga_object list
        elif len(i2_response.data) > 0:

            block_text = "Found %d matching %s%s" % \
                         (len(i2_response.data), status_type.lower(), plural(len(i2_response.data)))

            response.text = "Icinga status response"
            response.add_block(block_text)
            response.add_block(format_slack_response(config, status_type, i2_response.data,
                                                     [*i2_comments_response.data, *i2_downtime_response.data]))

        # the result returned empty
        else:
            problematic_text = ""

            if len(i2_filter_status) == 1 and \
                    i2_filter_status[0] in ["host.state != 0", "service.state != 0"]:
                problematic_text = "problematic "

            response.text = "No %s%s objects " % (problematic_text, status_type.lower())

            if len(i2_filter_names) == 1:
                response.text += "for '%s' " % i2_filter_names[0]
            elif len(i2_filter_names) > 1:
                response.text += "for '%s' and '%s' " % ("', '".join(i2_filter_names[:-1]), i2_filter_names[-1])

            response.text += "found."

            if len(problematic_text) != 0:
                response.text += " Everything seems in good condition."

    return response
