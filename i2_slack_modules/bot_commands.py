####
#
# Slack user commands to be interpreted and answered
#

from . import *
from .common import *
from .icinga_connection import *
from .slack_helper import *
from .classes import SlackConversation
from .icinga_states import IcingaStates

max_messages_to_display_detailed_status = 4


# noinspection PyUnusedLocal
def slack_command_ping(*args, **kwargs):
    """
    Just respond with a simple pong

    Parameters
    ----------
    args, kwargs: None
        used to hold additional args which are just ignored

    Returns
    -------
    BotResponse: pong answer
    """
    return BotResponse(
            text="pong :table_tennis_paddle_and_ball:"
    )


# noinspection PyUnusedLocal
def reset_conversation(slack_user_id=None, conversations=None, *args, **kwargs):
    """
    reset a conversation

    Parameters
    ----------
    conversations: dict
        object to hold current state of conversation
    slack_user_id : string
        slack user id
    args, kwargs: None
        used to hold additional args which are just ignored

    Returns
    -------
    BotResponse: response if action was successful
    """

    if slack_user_id is not None and conversations is not None and conversations.get(slack_user_id) is not None:
        del conversations[slack_user_id]
        return BotResponse(text="Your conversation has been reset.")

    return None


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

                object_fields = {
                    "Output": icinga_object.get("last_check_result").get("output"),
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
                    comment_title = "Comment by {} ({})".format(comment.get("author"),
                                                                ts_to_date(comment.get("entry_time")))

                    # add text and info about expiration
                    comment_text = comment.get("text")
                    if comment.get("expire_time") is not None and comment.get("expire_time") > 0:
                        comment_text += " (expires: {})".format(ts_to_date(comment.get("expire_time")))

                    object_fields[comment_title] = comment_text

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

                    object_fields[downtime_title] = downtime_text

                fields = list()
                for title, value in object_fields.items():
                    short = True
                    if title in ["Output"] or "Comment" in title or "Downtime" in title:
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


# noinspection PyUnusedLocal
def get_icinga_status_overview(config=None, *args, **kwargs):
    """return overview of current host and service status

    Parameters
    ----------
    config : dict
        dictionary with items parsed from config file
    args, kwargs: None
        used to hold additional args which are just ignored

    Returns
    -------
    BotResponse: with response for Slack command
    """

    response = BotResponse(text="Status Overview")

    i2_status = get_i2_status(config, "CIB")

    if i2_status.error:
        return slack_error_response(header="Icinga request error", error_message=i2_status.error)

    data = i2_status.data["results"][0]["status"]

    host_count = {
        "UP": data.get("num_hosts_up"),
        "DOWN": data.get("num_hosts_down"),
        "UNREACHABLE": data.get("num_hosts_unreachable"),
        "UNHANDLED": int(data.get("num_hosts_problem") - data.get("num_hosts_handled")),
        "ACKNOWLEDGED": data.get("num_hosts_acknowledged"),
        "IN DOWNTIME": data.get("num_hosts_in_downtime")
    }

    service_count = {
        "OK": data.get("num_services_ok"),
        "WARNING": data.get("num_services_warning"),
        "CRITICAL": data.get("num_services_critical"),
        "UNKNOWN": data.get("num_services_unknown"),
        "UNHANDLED": int(data.get("num_services_problem") - data.get("num_services_handled")),
        "ACKNOWLEDGED": data.get("num_services_acknowledged"),
        "IN DOWNTIME": data.get("num_services_in_downtime")
    }

    # add block text with number of unhandled problems
    problems_unhandled = host_count["UNHANDLED"] + service_count["UNHANDLED"]
    response.add_block("*Found %s unhandled problem%s*" %
                       ("no" if problems_unhandled == 0 else
                        str(problems_unhandled), plural(problems_unhandled)))

    # compile answer for host objects
    host_fields = list()
    for title, value in host_count.items():
        if title == "UNHANDLED":
            continue
        host_fields.append({
            "title": title,
            "value": int(value),
            "short": True
        })

    response.add_attachment(
        {
            "fallback": "Host status",
            "text": "*%s unhandled host%s*" %
                    ("No" if host_count["UNHANDLED"] == 0 else
                     str(host_count["UNHANDLED"]), plural(host_count["UNHANDLED"])),
            "color": "%s" % "good" if host_count["UNHANDLED"] == 0 else "danger",
            "fields": host_fields
        }
    )

    # compile answer for service objects
    service_fields = list()
    for title, value in service_count.items():
        if title == "UNHANDLED":
            continue
        service_fields.append({
            "title": title,
            "value": int(value),
            "short": True
        })

    response.add_attachment(
        {
            "fallback": "Service status",
            "text": "*%s unhandled service%s*" %
                    ("No" if service_count["UNHANDLED"] == 0 else
                     str(service_count["UNHANDLED"]), plural(service_count["UNHANDLED"])),
            "color": "%s" % "good" if service_count["UNHANDLED"] == 0 else "danger",
            "fields": service_fields
        }
    )

    return response


# noinspection PyUnusedLocal
def slack_command_help(config=None, slack_message=None, bot_commands=None, *args, **kwargs):
    """
    Return a short command description

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
    BotResponse: with help text
    """

    github_logo_url = "https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png"
    fields = list()
    help_color = "#03A8F3"
    help_headline = None

    if slack_message is None or slack_message.strip().lower() == "help":
        for command in bot_commands:
            command_shortcut = ""
            if command.shortcut is not None:
                if isinstance(command.shortcut, list):
                    command_shortcut = "|".join(command.shortcut)
                else:
                    command_shortcut = command.shortcut

                command_shortcut = " (%s)" % command_shortcut

            fields.append({
                "title": "`<bot> %s%s`" % (
                    command.name, command_shortcut
                ),
                "value": command.short_description
            })

        help_headline = "Following commands are implemented"

        fields.append({"title": "Detailed help", "value": "For a detailed help type `help <command>`", "short": False})

    else:
        # user asked for detailed help
        requested_help_topic = slack_message[4:].strip()
        requested_help_command = bot_commands.get_command_called(requested_help_topic)

        if requested_help_command:
            help_headline = "Detailed help for command: %s" % requested_help_command.name

            command_shortcut = "None"
            if requested_help_command.shortcut is not None:
                if isinstance(requested_help_command.shortcut, list):
                    command_shortcut = "`, `".join(requested_help_command.shortcut)
                else:
                    command_shortcut = requested_help_command.shortcut

                command_shortcut = "`%s`" % command_shortcut

            # fill fields
            fields.append({"title": "Full command",
                           "value": "`%s`" % requested_help_command.name,
                           "short": False})
            fields.append({"title": "Shortcut",
                           "value": command_shortcut,
                           "short": False})
            fields.append({"title": "Detailed description",
                           "value": requested_help_command.long_description,
                           "short": False})

            if getattr(requested_help_command, "sub_commands", None) is not None:

                sub_commands_list = list()
                for sub_command in requested_help_command.sub_commands:
                    sub_command_shortcut = ""
                    if sub_command.shortcut is not None:
                        if isinstance(sub_command.shortcut, list):
                            sub_command_shortcut = "|".join(sub_command.shortcut)
                        else:
                            sub_command_shortcut = sub_command.shortcut

                        sub_command_shortcut = " (%s)" % sub_command_shortcut

                    sub_commands_list.append("*Name*: %s%s" % (sub_command.name, sub_command_shortcut))

                    example_suffix = ""
                    if sub_command.object_type == "Host":
                        example_suffix = " <host>"
                    elif sub_command.object_type == "Service":
                        example_suffix = " <host/service>"

                    sub_commands_list.append("`<bot> %s %s%s`" % (
                            requested_help_command.name, sub_command.name, example_suffix)
                    )

                fields.append({"title": "Available sub commands",
                               "value": "\n".join(sub_commands_list),
                               "short": False})

                fields.append({"title": "Example of shortcut usage",
                               "value": "%s notifications for webserver services\n"
                                        "`<bot> %s sn webserver`" % (
                                            requested_help_command.name, requested_help_command.shortcut),
                               "short": False})

        if help_headline is None:
            # Command doesn't seem to be implemented
            help_headline = "Sorry, the supplied command is not implemented"
            fields.append({
                "title": "Error",
                "value": "I understood the command `%s`, which is not implemented!" % requested_help_topic,
                "short": False
            })
            help_color = "danger"

    return BotResponse(
        text="Bot help",
        blocks="*%s*" % help_headline,
        attachments={
            "fallback": "Bot help",
            "color": help_color,
            "fields": fields,
            "footer": "<%s#command-status-filter|Further Help @ GitHub>" % config["bot.url"],
            "footer_icon": github_logo_url
        }
    )


# noinspection PyUnusedLocal
def chat_with_user(
        config=None,
        conversations=None,
        bot_commands=None,
        slack_message=None,
        slack_user_id=None,
        slack_user_data=None,
        *args, **kwargs):
    """
    Have a conversation with the user about the action the user wants to perform

    Parameters
    ----------
    config : dict
        dictionary with items parsed from config file
    conversations: dict
        object to hold current state of conversation
    bot_commands: BotCommands
        class with bot commands to avoid circular imports
    slack_message : string
        slack message to parse
    slack_user_id : string
        slack user id
    slack_user_data: SlackUsers
        a SlackUsers object with user information pulled from Slack
    args, kwargs: None
        used to hold additional args which are just ignored

    Returns
    -------
    BotResponse: questions about the action, confirmations or errors
    """

    if slack_message is None:
        logging.error("Parameter '%s' missing while calling function '%s'" % ("slack_message", my_own_function_name()))

    if slack_user_id is None:
        logging.error("Parameter '%s' missing while calling function '%s'" % ("slack_user_id", my_own_function_name()))

    if slack_message is None or slack_user_id is None:
        return slack_error_response()

    # New conversation
    if conversations.get(slack_user_id) is None:
        conversations[slack_user_id] = SlackConversation(slack_user_id)

    this_conversation = conversations.get(slack_user_id)

    # check or command
    if this_conversation.command is None:
        logging.debug("Command not set, parsing: %s" % slack_message)
        this_conversation.command = bot_commands.get_command_called(slack_message)

        if this_conversation.command.name not in ["acknowledge", "downtime", "comment"]:
            this_conversation.command = None
            return None

        logging.debug("Command parsed: %s" % this_conversation.command.name)

        conversations[slack_user_id] = this_conversation

        slack_message = this_conversation.command.strip_command(slack_message)

    # check for filter
    if this_conversation.filter is None:
        if len(quoted_split(string_to_split=slack_message)) != 0:
            # we got a filter
            logging.debug("Filter not set, parsing: %s" % slack_message)

            index_string = " from"  # for downtime
            if this_conversation.command.name == "acknowledge":
                index_string = " until"
            elif this_conversation.command.name == "comment":
                index_string = " with"

            #  everything left of the index string will be parsed as filter
            if index_string in slack_message.lower():

                # get end of filter list
                end_of_filter_string = slack_message.lower().index(index_string)

                filter_string = slack_message[:end_of_filter_string]

                # strip the filter from the supplied string
                slack_message = slack_message[end_of_filter_string:]

                # strip index string from slack message on comments
                if this_conversation.command.name == "comment":
                    slack_message = slack_message.replace(index_string, "", 1)
            else:
                # index string not found
                # assuming the whole message is meant to be a filter
                filter_string = slack_message
                slack_message = ""

            filter_list = quoted_split(string_to_split=filter_string, preserve_quotations=True)

            logging.debug("Filter parsed: %s" % filter_list)

            this_conversation.filter = filter_list
            conversations[slack_user_id] = this_conversation

    # split slack_message into an array (chat message array)
    cma = quoted_split(string_to_split=slack_message, preserve_quotations=True)

    # try to find objects based on filter
    if this_conversation.filter and this_conversation.filter_result is None:

        logging.debug("Filter result list empty. Query Icinga for objects.")

        host_filter = list()
        service_filter = list()
        if this_conversation.command.name == "acknowledge":
            host_filter = ["host.state != 0"]
            service_filter = ["service.state != 0"]

        # query hosts and services
        if len(this_conversation.filter) == 1:

            object_type = "Host"
            i2_result = get_i2_object(config, object_type, host_filter, this_conversation.filter)

            if i2_result.error is None and len(i2_result.data) == 0:
                object_type = "Service"
                i2_result = get_i2_object(config, object_type, service_filter, this_conversation.filter)

        # just query services
        else:
            object_type = "Service"
            i2_result = get_i2_object(config, object_type, service_filter, this_conversation.filter)

        # encountered Icinga request issue
        if i2_result.error:
            logging.debug("No icinga objects found for filter: %s" % this_conversation.filter)

            return slack_error_response(
                header="Icinga request error while trying to find matching hosts/services",
                fallback_text="Icinga Error",
                error_message=i2_result.error
            )

        # we can set a downtime for all objects no matter their state
        if this_conversation.command.name == "downtime" and len(i2_result.data) > 0:

            this_conversation.filter_result = i2_result.data
        else:

            # only objects which are not acknowledged can be acknowledged
            ack_filter_result = list()
            for result in i2_result.data:
                # only add results which are not acknowledged
                if result.get("acknowledgement") == 0:
                    ack_filter_result.append(result)

            if len(ack_filter_result) > 0:
                this_conversation.filter_result = ack_filter_result

        # save current conversation state if filter returned any objects
        if this_conversation.filter_result and len(this_conversation.filter_result) > 0:
            logging.debug("Found %d objects for command %s" %
                          (len(this_conversation.filter_result), this_conversation.command.name))

            this_conversation.object_type = object_type
            conversations[slack_user_id] = this_conversation

    # parse start time information for downtime
    if this_conversation.command.name == "downtime" and this_conversation.start_date is None:

        if len(cma) != 0:

            logging.debug("Start date not set, parsing: %s" % " ".join(cma))

            for index, item in enumerate(cma):
                if item.lower() == "from":
                    cma[index] = "from"
                    break

            for index, item in enumerate(cma):
                if item.lower() == "until":
                    cma[index] = "until"
                    break

            if "from" in cma:
                cma = cma[cma.index("from") + 1:]

            if "until" in cma:
                string_parse = " ".join(cma[0:cma.index("until")])
                cma = cma[cma.index("until"):]
            else:
                string_parse = " ".join(cma)

            start_date_data = parse_relative_date(string_parse)

            if start_date_data:

                logging.debug("Start date successfully parsed")

                # get timestamp from returned datetime object
                if start_date_data.get("dt"):
                    this_conversation.start_date = start_date_data.get("dt").timestamp()

                if cma[0] != "until":
                    cma = string_parse[start_date_data.get("mend"):].strip().split(" ")
            else:
                this_conversation.start_date_parsing_failed = string_parse

            conversations[slack_user_id] = this_conversation

    # parse end time information
    if this_conversation.command.name in ["acknowledge", "downtime"] and this_conversation.end_date is None:

        if len(cma) != 0:

            logging.debug("End date not set, parsing: %s" % " ".join(cma))

            for index, item in enumerate(cma):
                if item.lower() == "until":
                    cma[index] = "until"
                    break

            if "until" in cma:
                cma = cma[cma.index("until") + 1:]

            if cma[0].lower() in ["never", "infinite"]:
                # add rest of message as description
                this_conversation.end_date = -1
                del cma[0]

            else:
                string_parse = " ".join(cma)
                end_date_data = parse_relative_date(string_parse)

                if end_date_data:

                    # get timestamp from returned datetime object
                    if end_date_data.get("dt"):
                        this_conversation.end_date = end_date_data.get("dt").timestamp()

                    # add rest of string back to cma
                    cma = string_parse[end_date_data.get("mend"):].strip().split(" ")
                else:
                    this_conversation.end_date_parsing_failed = string_parse

            conversations[slack_user_id] = this_conversation

    if this_conversation.description is None:

        if len(cma) != 0 and len("".join(cma).strip()) != 0:
            logging.debug("Description not set, parsing: %s" % " ".join(cma))

            this_conversation.description = " ".join(cma)
            cma = list()

        conversations[slack_user_id] = this_conversation

    # ask for missing info
    if this_conversation.filter is None:

        logging.debug("Filter not set, asking for it")

        response_text = None
        if this_conversation.command.name == "acknowledge":
            response_text = "What do you want acknowledge?"
        elif this_conversation.command.name == "downtime":
            response_text = "What do you want to set a downtime for?"
        elif this_conversation.command.name == "comment":
            response_text = "What do you want to add a comment to?"

        conversations[slack_user_id] = this_conversation
        return BotResponse(text=response_text)

    # no objects found based on filter
    if this_conversation.filter_result is None:
        problematic = ""

        logging.debug("Icinga2 object request returned empty, asking for a different filter")

        if this_conversation.command.name == "acknowledge":
            problematic = " problematic"

        response_text = "Sorry, I was not able to find any%s hosts or services for your search '%s'. Try again." \
                        % (problematic, " ".join(this_conversation.filter))

        this_conversation.filter = None
        conversations[slack_user_id] = this_conversation
        return BotResponse(text=response_text)

    # ask for not parsed start time
    if this_conversation.command.name == "downtime" and this_conversation.start_date is None:

        if not this_conversation.start_date_parsing_failed:
            logging.debug("Start date not set, asking for it")
            response_text = "When should the downtime start?"
        else:
            logging.debug("Failed to parse start date, asking again for it")
            response_text = "Sorry, I was not able to understand the start date '%s'. Try again please." \
                            % this_conversation.start_date_parsing_failed

        conversations[slack_user_id] = this_conversation
        return BotResponse(text=response_text)

    # ask for not parsed end date
    if this_conversation.command.name in ["acknowledge", "downtime"] and this_conversation.end_date is None:

        if not this_conversation.end_date_parsing_failed:

            logging.debug("End date not set, asking for it")

            if this_conversation.command.name == "acknowledge":
                response_text = "When should the acknowledgement expire? Or never?"
            else:
                response_text = "When should the downtime end?"
        else:
            logging.debug("Failed to parse end date, asking again for it")
            response_text = "Sorry, I was not able to understand the end date '%s'. Try again please." \
                            % this_conversation.end_date_parsing_failed

        conversations[slack_user_id] = this_conversation
        return BotResponse(text=response_text)

    if this_conversation.end_date and this_conversation.end_date != -1 and \
            this_conversation.end_date - 60 < datetime.now().timestamp():
        logging.debug("End date is already in the past. Ask user again for end date")

        response_text = "Sorry, end date '%s' lies (almost) in the past. Please define a valid end/expire date." % \
                        ts_to_date(this_conversation.end_date)

        this_conversation.end_date = None
        conversations[slack_user_id] = this_conversation

        return BotResponse(text=response_text)

    if this_conversation.command.name == "downtime" and this_conversation.start_date > this_conversation.end_date:
        logging.debug("Start date is after end date for downtime. Ask user again for start date.")

        response_text = "Sorry, start date '%s' can't be after and date '%s'. When should the downtime start?" % \
                        (ts_to_date(this_conversation.start_date), ts_to_date(this_conversation.end_date))

        this_conversation.start_date = None
        conversations[slack_user_id] = this_conversation

        return BotResponse(text=response_text)

    if this_conversation.description is None:
        logging.debug("Description not set, asking for it")

        conversations[slack_user_id] = this_conversation
        return BotResponse(text="Please add a comment.")

    # now we seem to have all information and ask user if that's what the user wants
    if not this_conversation.confirmed:

        if this_conversation.confirmation_sent:
            if cma[0].startswith("y") or cma[0].startswith("Y"):
                this_conversation.confirmed = True
            elif cma[0].startswith("n") or cma[0].startswith("N"):
                this_conversation.canceled = True
            else:
                this_conversation.confirmation_sent = False

        if not this_conversation.confirmation_sent:

            # get object type
            if this_conversation.command.name == "acknowledge":
                command = "Acknowledgement"
            else:
                command = this_conversation.command.name.capitalize()

            confirmation = {
                "Command": command,
                "Type": this_conversation.object_type
            }
            if this_conversation.command.name == "downtime":
                confirmation["Start"] = ts_to_date(this_conversation.start_date)
                confirmation["End"] = ts_to_date(this_conversation.end_date)

            elif this_conversation.command.name == "acknowledge":
                confirmation["Expire"] = "Never" if this_conversation.end_date == -1 else ts_to_date(
                    this_conversation.end_date)

            confirmation["Comment"] = this_conversation.description
            confirmation["Objects"] = ""

            response = BotResponse(text="Confirm your action")

            confirmation_fields = list()
            for title, value in confirmation.items():
                confirmation_fields.append(">*%s*: %s" % (title, value))

            for i2_object in this_conversation.filter_result[0:10]:
                if this_conversation.object_type == "Host":
                    name = i2_object.get("name")
                else:
                    name = '%s - %s' % (i2_object.get("host_name"), i2_object.get("name"))

                confirmation_fields.append(u">\t• %s" % name)

            if len(this_conversation.filter_result) > 10:
                confirmation_fields.append(">\t... and %d more" % (len(this_conversation.filter_result) - 10))
            response.add_block("\n".join(confirmation_fields))
            response.add_block("Do you want to confirm this action?:")

            this_conversation.confirmation_sent = True
            conversations[slack_user_id] = this_conversation

            return response

    if this_conversation.canceled:
        del conversations[slack_user_id]
        return BotResponse(text="Ok, action has been canceled!")

    if this_conversation.confirmed:

        # delete conversation history
        del conversations[slack_user_id]

        i2_handle, i2_error = setup_icinga_connection(config)

        if not i2_handle:
            if i2_error is not None:
                error_message = i2_error
            else:
                error_message = "Unknown error while setting up Icinga2 connection"

            return slack_error_response(header="Icinga request error", error_message=error_message)

        # define filters
        filter_list = list()
        if this_conversation.object_type == "Host":
            for i2_object in this_conversation.filter_result:
                filter_list.append('host.name=="%s"' % i2_object.get("name"))
        else:
            for i2_object in this_conversation.filter_result:
                filter_list.append('( host.name=="%s" && service.name=="%s" )' %
                                   (i2_object.get("host_name"), i2_object.get("name")))

        success_message = None
        i2_error = None

        # get username to add as comment
        this_user_info = slack_user_data.get_user_info(slack_user_id)

        author_name = "Anonymous Slack user"
        if this_user_info is not None and this_user_info.get("real_name"):
            author_name = this_user_info.get("real_name")

        try:

            if this_conversation.command.name == "downtime":

                logging.debug("Sending Downtime to Icinga2")

                success_message = "Successfully scheduled downtime!"

                i2_response = i2_handle.actions.schedule_downtime(
                    object_type=this_conversation.object_type,
                    filters='(' + ' || '.join(filter_list) + ')',
                    author=author_name,
                    comment=this_conversation.description,
                    start_time=this_conversation.start_date,
                    end_time=this_conversation.end_date,
                    duration=this_conversation.end_date - this_conversation.start_date,
                    all_services=True
                )

            elif this_conversation.command.name == "acknowledge":
                logging.debug("Sending Acknowledgement to Icinga2")

                success_message = "Successfully acknowledged %s problem%s!" % \
                                  (this_conversation.object_type, plural(len(filter_list)))

                # https://github.com/fmnisme/python-icinga2api/blob/master/doc/4-actions.md#-actionsacknowledge_problem
                i2_response = i2_handle.actions.acknowledge_problem(
                    object_type=this_conversation.object_type,
                    filters='(' + ' || '.join(filter_list) + ')',
                    author=author_name,
                    comment=this_conversation.description,
                    expiry=None if this_conversation.end_date == -1 else this_conversation.end_date,
                    sticky=True
                )

            elif this_conversation.command.name == "comment":
                logging.debug("Sending Comment to Icinga2")

                success_message = "Successfully added %s comment%s!" % \
                                  (this_conversation.object_type, plural(len(filter_list)))

                i2_response = i2_handle.actions.add_comment(
                    object_type=this_conversation.object_type,
                    filters='(' + ' || '.join(filter_list) + ')',
                    author=author_name,
                    comment=this_conversation.description
                )

        except Exception as e:
            i2_error = str(e)
            logging.error("Unable to perform Icinga2 action: %s" % i2_error)
            pass

        if i2_error:
            return slack_error_response(header="Icinga request error", error_message=i2_error)

        return BotResponse(text=success_message)

    return None


# noinspection PyTypeChecker
# noinspection PyUnusedLocal
def get_icinga_daemon_status(config=None, startup=False, *args, **kwargs):
    """
    Get the current status of the Icinga2 instance

    Parameters
    ----------
    config : dict
        dictionary with items parsed from config file
    startup : bool
        define if function is called during startup
    args, kwargs: None
        used to hold additional args which are just ignored

    Returns
    -------
    BotResponse: questions about the action, confirmations or errors
    """

    i2_status = get_i2_status(config, "")

    icingaapplication = {
        "component_name": "IcingaApplication",
        "data": None
    }
    apilistener = {
        "component_name": "ApiListener",
        "data": None
    }

    if not i2_status.error:
        for component in i2_status.data.get("results"):

            if component["name"] == apilistener["component_name"]:
                apilistener["data"] = component["status"]["api"]
            if component["name"] == icingaapplication["component_name"]:
                icingaapplication["data"] = component["status"]["icingaapplication"]["app"]

    status_reply = BotResponse()
    status_color = "good"

    missing_data = []

    if not icingaapplication["data"]:
        missing_data.append(icingaapplication["component_name"])
    if not apilistener["data"]:
        missing_data.append(apilistener["component_name"])

    if i2_status.error:

        # format error message block
        status_header = "Icinga connection error"
        if startup:
            status_header += " during bot start"

        status_text = i2_status.error
        status_color = "danger"

    elif len(missing_data) > 0:

        status_header = "Icinga request error"
        if startup:
            status_header += " during bot start"

        status_text = "No data for component '%s' found in Icinga reply" % \
            "' and '".join(missing_data)
        status_color = "danger"

    else:

        icinga_status_text = list()
        if startup:
            status_header = "Starting up %s (version: %s)" % (config["bot.description"], config["bot.version"])
            icinga_status_text.append("Successfully connected to Icinga")
        else:
            status_header = "Icinga Status"
            icinga_status_text.append("Current Icinga2 Status:")

        icinga_status_text.append("Node name: *%s*" % icingaapplication["data"]["node_name"])
        icinga_status_text.append("Version: *%s*" % icingaapplication["data"]["version"])
        icinga_status_text.append("Running since: *%s*" % ts_to_date(icingaapplication["data"]["program_start"]))
        if not startup:
            icinga_status_text.append("Event handlers: *%s*" %
                                      enabled_disabled(icingaapplication["data"]["enable_event_handlers"]))
            icinga_status_text.append("Flap detection: *%s*" %
                                      enabled_disabled(icingaapplication["data"]["enable_flapping"]))
            icinga_status_text.append("Host checks: *%s*" %
                                      enabled_disabled(icingaapplication["data"]["enable_host_checks"]))
            icinga_status_text.append("Service checks: *%s*" %
                                      enabled_disabled(icingaapplication["data"]["enable_service_checks"]))
            icinga_status_text.append("Notifications: *%s*" %
                                      enabled_disabled(icingaapplication["data"]["enable_notifications"]))
            icinga_status_text.append("Writing perfdata: *%s*" %
                                      enabled_disabled(icingaapplication["data"]["enable_perfdata"]))
            icinga_status_text.append("Number of endpoints: *%s*" % int(apilistener["data"]["num_endpoints"]))

            not_connected_endpoints = "None"
            if len(apilistener["data"]["not_conn_endpoints"]) > 0:
                not_connected_endpoints = ", ".join(apilistener["data"]["not_conn_endpoints"])
                status_color = "danger"

            icinga_status_text.append("Not connected endpoints: *%s*" % not_connected_endpoints)

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

    return status_reply


# noinspection PyTypeChecker
# noinspection PyUnusedLocal
def enable_disable_action(
        config=None,
        conversations=None,
        bot_commands=None,
        slack_message=None,
        slack_user_id=None,
        *args, **kwargs):
    """
    Have a conversation with the user about the attribute the user wants to enable/disable

    Parameters
    ----------
    config : dict
        dictionary with items parsed from config file
    conversations: dict
        object to hold current state of conversation
    bot_commands: BotCommands
        class with bot commands to avoid circular imports
    slack_message : string
        slack message to parse
    slack_user_id : string
        slack user id
    args, kwargs: None
        used to hold additional args which are just ignored

    Returns
    -------
    BotResponse: questions about the action, confirmations or errors
    """

    if slack_message is None:
        logging.error("Parameter '%s' missing while calling function '%s'" % ("slack_message", my_own_function_name()))

    if slack_user_id is None:
        logging.error("Parameter '%s' missing while calling function '%s'" % ("slack_user_id", my_own_function_name()))

    if slack_message is None or slack_user_id is None:
        return slack_error_response()

    # New conversation
    if conversations.get(slack_user_id) is None:
        conversations[slack_user_id] = SlackConversation(slack_user_id)

    this_conversation = conversations.get(slack_user_id)

    # check or command
    if this_conversation.command is None:
        logging.debug("Command not set, parsing: %s" % slack_message)
        this_conversation.command = bot_commands.get_command_called(slack_message)

        # see if checking for sub_commands works better here
        if this_conversation.command.name not in ["enable", "disable"]:
            this_conversation.command = None
            return None

        logging.debug("Command parsed: %s" % this_conversation.command.name)

        conversations[slack_user_id] = this_conversation

        slack_message = this_conversation.command.strip_command(slack_message)

    # check for sub command
    if this_conversation.sub_command is None:
        if len(slack_message) != 0:
            # we got a filter
            logging.debug("Sub command not set, parsing: %s" % slack_message)

            if this_conversation.command.has_sub_commands():
                this_conversation.sub_command = \
                    this_conversation.command.sub_commands.get_command_called(slack_message)

                if this_conversation.sub_command:
                    slack_message = this_conversation.sub_command.strip_command(slack_message)
                    logging.debug("Sub command parsed: %s" % this_conversation.sub_command.name)

            conversations[slack_user_id] = this_conversation

    # check for filter
    if this_conversation.sub_command is not None and \
            this_conversation.sub_command.object_type != "global" and this_conversation.filter is None:
        if len(slack_message) != 0:

            filter_list = quoted_split(string_to_split=slack_message, preserve_quotations=True)

            logging.debug("Filter parsed: %s" % filter_list)

            this_conversation.filter = filter_list
            conversations[slack_user_id] = this_conversation

    # try to find objects based on filter
    if this_conversation.filter and this_conversation.filter_result is None:

        logging.debug("Filter result list empty. Query Icinga for objects.")

        # query hosts and services
        i2_result = get_i2_object(config, this_conversation.sub_command.object_type, None, this_conversation.filter)

        # encountered Icinga request issue
        if i2_result.error:
            logging.debug("No icinga objects found for filter: %s" % this_conversation.filter)

            return slack_error_response(
                header="Icinga request error while trying to find matching hosts/services",
                fallback_text="Icinga Error",
                error_message=i2_result.error
            )

        this_conversation.filter_result = i2_result.data
        this_conversation.filter_used = i2_result.filter

        # save current conversation state if filter returned any objects
        if this_conversation.filter_result and len(this_conversation.filter_result) > 0:
            logging.debug("Found %d objects to %s %s for" %
                          (len(this_conversation.filter_result),
                           this_conversation.command.name,
                           this_conversation.sub_command.name))

            conversations[slack_user_id] = this_conversation

    # ask for sub command
    if this_conversation.sub_command is None:

        logging.debug("Sub command not set, asking for it")

        response_text = \
            "Sorry, I wasn't able to parse your sub command. Check `help %s` to get available sub commands" % \
            this_conversation.command.name

        conversations[slack_user_id] = this_conversation
        return BotResponse(text=response_text)

    # ask for missing info
    if this_conversation.sub_command.object_type != "global" and this_conversation.filter is None:

        logging.debug("Filter not set, asking for it")

        response_text = "For which object do you want to %s %s?" % (
            this_conversation.command.name,
            this_conversation.sub_command.name)

        conversations[slack_user_id] = this_conversation
        return BotResponse(text=response_text)

    # no objects found based on filter
    if this_conversation.sub_command.object_type != "global" and this_conversation.filter_result is None:

        logging.debug("Icinga2 object request returned empty, asking for a different filter")

        response_text = "Sorry, I was not able to find any hosts or services for your search '%s'. Try again." \
                        % " ".join(this_conversation.filter)

        this_conversation.filter = None
        conversations[slack_user_id] = this_conversation
        return BotResponse(text=response_text)

    # now we seem to have all information and ask user if that's what the user wants
    if not this_conversation.confirmed:

        if this_conversation.confirmation_sent:
            if slack_message.startswith("y") or slack_message.startswith("Y"):
                this_conversation.confirmed = True
            elif slack_message.startswith("n") or slack_message.startswith("N"):
                this_conversation.canceled = True
            else:
                this_conversation.confirmation_sent = False

        if not this_conversation.confirmation_sent:

            confirmation = {
                "Command": "%s %s" % (this_conversation.command.name, this_conversation.sub_command.name)
            }

            if this_conversation.sub_command.object_type != "global" and this_conversation.filter_result is not None:
                confirmation.update({"Objects": ""})

            response = BotResponse(text="Confirm your action")

            confirmation_fields = list()

            for title, value in confirmation.items():
                confirmation_fields.append(">*%s*: %s" % (title, value))

            if this_conversation.sub_command.object_type != "global" and this_conversation.filter_result is not None:

                for i2_object in this_conversation.filter_result[0:10]:
                    if this_conversation.sub_command.object_type == "Host":
                        name = i2_object.get("name")
                    else:
                        name = '%s - %s' % (i2_object.get("host_name"), i2_object.get("name"))

                    confirmation_fields.append(u">\t• %s" % name)

                if len(this_conversation.filter_result) > 10:
                    confirmation_fields.append(">\t... and %d more" % (len(this_conversation.filter_result) - 10))

            response.add_block("\n".join(confirmation_fields))
            response.add_block("Do you want to confirm this action?:")

            this_conversation.confirmation_sent = True
            conversations[slack_user_id] = this_conversation

            return response

    if this_conversation.canceled:
        del conversations[slack_user_id]
        return BotResponse(text="Ok, action has been canceled!")

    if this_conversation.confirmed:

        # delete conversation history
        del conversations[slack_user_id]

        i2_handle: object
        i2_handle, i2_error = setup_icinga_connection(config)

        if not i2_handle:
            if i2_error is not None:
                error_message = i2_error
            else:
                error_message = "Unknown error while setting up Icinga2 connection"

            return slack_error_response(header="Icinga request error", error_message=error_message)

        success_message = None
        i2_error = None

        enable = True
        if this_conversation.command.name == "disable":
            enable = False

        logging.debug("Sending command '%s %s' to Icinga2" %
                      (this_conversation.command.name, this_conversation.sub_command.name))

        try:

            if this_conversation.sub_command.object_type == "global":

                success_message = "Successfully %sd %s!" % \
                                  (this_conversation.command.name, this_conversation.sub_command.name)

                i2_response = i2_handle.objects.update(
                    object_type="IcingaApplication",
                    name="app", attrs={"attrs": {this_conversation.sub_command.icinga_attr_name: enable}}
                )

            else:

                success_message = "Successfully %sd %s for %s!" % \
                                  (this_conversation.command.name,
                                   this_conversation.sub_command.name,
                                   " ".join(this_conversation.filter))

                # noinspection PyProtectedMember
                url_path = '{}/{}'.format(
                    i2_handle.objects.base_url_path,
                    i2_handle.objects._convert_object_type(this_conversation.sub_command.object_type)
                )

                logging.debug(url_path)

                payload = {
                    'attrs': {
                        this_conversation.sub_command.icinga_attr_name: enable
                    },
                    'filter': this_conversation.filter_used
                }

                # noinspection PyProtectedMember
                i2_response = i2_handle.objects._request('POST', url_path, payload)

        except Exception as e:
            i2_error = str(e)
            logging.error("Unable to perform Icinga2 object update: %s" % i2_error)
            pass

        if i2_error:
            return slack_error_response(header="Icinga request error", error_message=i2_error)

        return BotResponse(text=success_message)

    return None
