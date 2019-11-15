####
#
# Slack user commands to be interpreted and answered
#

from . import *
from .common import *
from .icinga_connection import *
from .slack_helper import *
from .classes import SlackConversation
from .command_definition import implemented_commands

max_messages_to_display_detailed_status = 4


def get_command_called(slack_message=None):
    """
    return the command dict for a slack_message

    Parameters
    ----------
    slack_message : string
        the Slack command which will be parsed

    Returns
    -------
    dict, None: response with command dict if found
    """

    command_starts_with = list()

    for command in implemented_commands:
        name = command.get("name")
        shortcut = command.get("shortcut")
        if name is None:
            logging.error("Command name undefined. Check 'command_definition.py' for command with undefined name!")
        else:
            command_starts_with.append(name)
        if shortcut:
            if isinstance(shortcut, list):
                command_starts_with.extend(shortcut)
            elif isinstance(shortcut, str):
                command_starts_with.append(shortcut)
            else:
                logging.error("Command shortcut must be a string or a list")

        for command_start in command_starts_with:
            if slack_message.startswith(command_start):
                return command

    return None


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
    SlackResponse: pong answer
    """
    return SlackResponse(
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
    SlackResponse: response if acton was successful
    """

    if slack_user_id is not None and conversations is not None and conversations.get(slack_user_id) is not None:
        del conversations[slack_user_id]
        return SlackResponse(text="Your conversation has been reset.")

    return None


# noinspection PyUnusedLocal
def run_icinga_status_query(config=None, slack_message=None, *args, **kwargs):
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
    args, kwargs: None
        used to hold additional args which are just ignored

    Returns
    -------
    SlackResponse: with command result
    """

    # parse slack message and determine if this is a service or host status command
    # also strip off the command from the slack_message

    response = SlackResponse()

    display_just_unhandled_objects_for_default_query = True

    command_start = None
    status_type = None

    called_command = get_command_called(slack_message)

    # determine if command handler is actually called for this function
    if called_command["command_handler"] == my_own_function_name():
        if slack_message.startswith(called_command["name"]):
            command_start = called_command["name"]
        elif called_command["shortcut"] is not None:
            if isinstance(called_command["shortcut"], list):
                for shortcut in called_command["shortcut"]:
                    if slack_message.startswith(shortcut):
                        command_start = shortcut
            else:
                if slack_message.startswith(called_command["shortcut"]):
                    command_start = called_command["shortcut"]

        if command_start is not None:
            slack_message = slack_message[len(command_start):].strip()
            status_type = called_command["status_type"]

    if None in [command_start, status_type]:
        logging.error("Function (%s) call failed. Unable to determine command_start or status_type" %
                      my_own_function_name())
        return SlackResponse(text="Encountered a bot internal error. Please ask your bot admin for help.")

    # take care of special request to get all problems and not just unhandled ones
    if slack_message.startswith("problems"):
        display_just_unhandled_objects_for_default_query = False

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
                "fallback": response.text,
                "text": i2_error_response,
                "color": "danger"
            }
        )

    else:

        # get icinga objects
        acknowledged = None
        downtime = None
        if display_just_unhandled_objects_for_default_query and len(i2_filter_names) == 0:
            acknowledged = downtime = False

        i2_response = get_i2_object(config, status_type, i2_filter_status, i2_filter_names, acknowledged, downtime)

        if i2_response.error:
            response.text = "Icinga request error"
            response.add_block("*%s*" % response.text)
            response.add_attachment(
                {
                    "fallback": response.text,
                    "text": "Error: %s" % i2_response.error,
                    "color": "danger"
                }
            )

        # Just a String was returned
        elif type(i2_response.response) is str:
            response.text = "Icinga status response"
            response.add_block(i2_response.response)

        # show more detailed information if only a few objects are returned
        elif len(i2_response.response) in list(range(1, (max_messages_to_display_detailed_status + 1))):

            response.text = "Icinga status response"
            block_text = "Found %d matching %s%s" % \
                         (len(i2_response.response), status_type.lower(), plural(len(i2_response.response)))

            response.add_block(block_text)

            for icinga_object in i2_response.response:
                if icinga_object.get("host_name"):
                    host_name = icinga_object.get("host_name")
                    service_name = icinga_object.get("name")
                    states = service_states
                    colors = enum("good", "warning", "danger", "#E066FF")
                else:
                    host_name = icinga_object.get("name")
                    service_name = None
                    states = host_states
                    colors = enum("good", "danger", "#BC1414")

                host_url = get_web2_slack_url(host_name, web2_url=config["icinga.web2_url"])
                service_url = get_web2_slack_url(host_name, service_name, web2_url=config["icinga.web2_url"])

                if icinga_object.get("host_name"):
                    text = "*%s | %s*" % (host_url, service_url)
                else:
                    text = "*%s*" % host_url

                object_fields = {
                    "Output": icinga_object.get("last_check_result").get("output"),
                    "Last State Change": ts_to_date(icinga_object.get("last_state_change")),
                    "Status": states.reverse[icinga_object.get("state")],
                    "Acknowledged": yes_no(icinga_object.get("acknowledgement")),
                    "In Downtime": yes_no(icinga_object.get("downtime_depth"))
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
                        "color": colors.reverse[int(icinga_object.get("state"))],
                        "text": text,
                        "fields": fields
                    }
                )

        # the more condensed icinga_object list
        elif len(i2_response.response) > 0:

            block_text = "Found %d matching %s%s" % \
                         (len(i2_response.response), status_type.lower(), plural(len(i2_response.response)))

            response.text = "Icinga status response"
            response.add_block(block_text)
            response.add_block(format_slack_response(config, status_type, i2_response.response))

        # the result returned empty
        else:
            problematic_text = ""

            if len(i2_filter_status) == 1 and \
                    i2_filter_status[0] in ["host.state != 0", "service.state != ServiceOK"]:
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
    SlackResponse: with response for Slack command
    """

    response = SlackResponse(text="Status Overview")

    # get icinga host objects
    i2_host_response = get_i2_object(config, "Host")

    if i2_host_response.error:
        response.text = "Icinga request error"
        response.add_block("*%s*" % response.text)
        response.add_attachment(
            {
                "fallback": response.text,
                "text": "Error: %s" % i2_host_response.error,
                "color": "danger"
            }
        )
        return response

    # get icinga service objects
    i2_service_response = get_i2_object(config, "Service")

    if i2_service_response.error:
        response.text = "Icinga request error"
        response.add_block("*%s*" % response.text)
        response.add_attachment(
            {
                "fallback": response.text,
                "text": "Error: %s" % i2_service_response.error,
                "color": "danger"
            }
        )
        return response

    host_count = {
        "UP": 0,
        "DOWN": 0,
        "UNREACHABLE": 0,
        "UNHANDLED": 0,
        "ACKNOWLEDGED": 0,
        "IN DOWNTIME": 0
    }

    service_count = {
        "OK": 0,
        "WARNING": 0,
        "CRITICAL": 0,
        "UNKNOWN": 0,
        "UNHANDLED": 0,
        "ACKNOWLEDGED": 0,
        "IN DOWNTIME": 0
    }

    # count all host objects
    for host in i2_host_response.response:
        host_count[host_states.reverse[int(host.get("state"))]] += 1

        if host.get("acknowledgement") > 0:
            host_count["ACKNOWLEDGED"] += 1

        if host.get("downtime_depth") > 0:
            host_count["IN DOWNTIME"] += 1

        if host.get("state") > 0 and \
                host.get("acknowledgement") == 0 and \
                host.get("downtime_depth") == 0:
            host_count["UNHANDLED"] += 1

    # count all service objects
    for service in i2_service_response.response:
        service_count[service_states.reverse[int(service.get("state"))]] += 1

        if service.get("acknowledgement") > 0:
            service_count["ACKNOWLEDGED"] += 1

        if service.get("downtime_depth") > 0:
            service_count["IN DOWNTIME"] += 1

        if service.get("state") > 0 and \
                service.get("acknowledgement") == 0 and \
                service.get("downtime_depth") == 0:
            service_count["UNHANDLED"] += 1

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
            "value": value,
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
            "value": value,
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
def slack_command_help(config=None, slack_message=None, *args, **kwargs):
    """
    Return a short command description

    Parameters
    ----------
    config : dict
        dictionary with items parsed from config file
    slack_message : string
        the Slack command which will be parsed
    args, kwargs: None
        used to hold additional args which are just ignored

    Returns
    -------
    SlackResponse: with help text
    """

    github_logo_url = "https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png"
    fields = list()
    help_color = "#03A8F3"
    help_headline = None

    if slack_message is None or slack_message.strip() == "help":
        for command in implemented_commands:
            command_shortcut = ""
            if command["shortcut"] is not None:
                if isinstance(command["shortcut"], list):
                    command_shortcut = "|".join(command["shortcut"])
                else:
                    command_shortcut = command["shortcut"]

                command_shortcut = " (%s)" % command_shortcut

            fields.append({
                "title": "`<bot> %s%s`" % (
                    command["name"], command_shortcut
                ),
                "value": command["short_description"]
            })

        help_headline = "Following commands are implemented"

        fields.append({"title": "Detailed help", "value": "For a detailed help type `help <command>`", "short": False})

    else:
        # user asked for detailed help
        requested_help_topic = slack_message[4:].strip()
        requested_help_command = get_command_called(requested_help_topic)

        if requested_help_command:
            help_headline = "Detailed help for command: %s" % requested_help_command["name"]

            command_shortcut = "None"
            if requested_help_command["shortcut"] is not None:
                if isinstance(requested_help_command["shortcut"], list):
                    command_shortcut = "`, `".join(requested_help_command["shortcut"])
                else:
                    command_shortcut = requested_help_command["shortcut"]

                command_shortcut = "`%s`" % command_shortcut

            # fill fields
            fields.append({"title": "Full command",
                           "value": "`%s`" % requested_help_command["name"],
                           "short": False})
            fields.append({"title": "Shortcut",
                           "value": command_shortcut,
                           "short": False})
            fields.append({"title": "Detailed description",
                           "value": requested_help_command["long_description"],
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

    return SlackResponse(
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
    slack_message : string
        slack message to parse
    slack_user_id : string
        slack user id
    slack_user_data: dict
        dictionary with user information pulled from Slack
    args, kwargs: None
        used to hold additional args which are just ignored

    Returns
    -------
    SlackResponse: questions about the action, confirmations or errors
    """

    if slack_message is None or slack_user_id is None:
        response = SlackResponse()

        response.text = "Slack internal error"
        response.add_block("*%s*" % response.text)
        response.add_attachment(
            {
                "fallback": response.text,
                "text": "Error: parameters missing in 'chat_with_user' function",
                "color": "danger"
            }
        )
        return response

    # New conversation
    if conversations.get(slack_user_id) is None:
        conversations[slack_user_id] = SlackConversation(slack_user_id)

    this_conversation = conversations.get(slack_user_id)

    # split slack_message into an array (chat message array)
    cma = slack_message.split(' ')

    # check or command
    if this_conversation.command is None:
        logging.debug("Command not set, parsing: %s" % " ".join(cma))
        if cma[0].startswith("ack"):
            this_conversation.command = "ACK"
        elif cma[0].startswith("dt") or cma[0].startswith("downtime"):
            this_conversation.command = "DOWNTIME"
        else:
            return None

        logging.debug("Command parsed: %s" % this_conversation.command)

        del cma[0]

    # check for filter
    if this_conversation.filter is None:

        if len(cma) != 0:
            # we got a filter
            logging.debug("Filter not set, parsing: %s" % " ".join(cma))

            # get first word after command as filter
            filter_list = list()
            filter_list.append(cma.pop(0))

            # use second word as well if present
            if len(cma) == 1 or (len(cma) > 1 and cma[0] not in ["from", "until"]):
                filter_list.append(cma.pop(0))

            logging.debug("Filter parsed: %s" % filter_list)

            this_conversation.filter = filter_list
            conversations[slack_user_id] = this_conversation

    # try to find objects based on filter
    if this_conversation.filter and this_conversation.filter_result is None:

        logging.debug("Filter result list empty. Query Icinga for objects.")
        host_filter = list()
        service_filter = list()
        if this_conversation.command == "ACK":
            host_filter = ["host.state != 0"]
            service_filter = ["service.state != 0"]

        # query hosts and services
        if len(this_conversation.filter) == 1:

            object_type = "Host"
            i2_result = get_i2_object(config, object_type, host_filter, this_conversation.filter)

            if i2_result.error is None and len(i2_result.response) == 0:
                object_type = "Service"
                i2_result = get_i2_object(config, object_type, service_filter, this_conversation.filter)

        # just query services
        else:
            object_type = "Service"
            i2_result = get_i2_object(config, object_type, service_filter, this_conversation.filter)

        # encountered Icinga request issue
        if i2_result.error:
            logging.debug("No icinga objects found for filter: %s" % this_conversation.filter)
            error_response = SlackResponse(text="Icinga Error")
            error_response.text = "Icinga request error while trying to find matching hosts/services"
            error_response.add_block("*%s*" % error_response.text)
            error_response.add_attachment(
                {
                    "fallback": error_response.text,
                    "text": "Error: %s" % i2_result.error,
                    "color": "danger"
                }
            )
            return error_response

        # we can set a downtime for all objects no matter their state
        if this_conversation.command == "DOWNTIME" and len(i2_result.response) > 0:

            this_conversation.filter_result = i2_result.response
        else:

            # only objects which are not acknowledged can be acknowledged
            ack_filter_result = list()
            for result in i2_result.response:
                # only add results which are not acknowledged
                if result.get("acknowledgement") == 0:
                    ack_filter_result.append(result)

            if len(ack_filter_result) > 0:
                this_conversation.filter_result = ack_filter_result

        # save current conversation state if filter returned any objects
        if this_conversation.filter_result and len(this_conversation.filter_result) > 0:
            logging.debug("Found %d objects for command %s" %
                          (len(this_conversation.filter_result), this_conversation.command))

            this_conversation.object_type = object_type
            conversations[slack_user_id] = this_conversation

    # parse start time information for downtime
    if this_conversation.command == "DOWNTIME" and this_conversation.start_date is None:

        if len(cma) != 0:

            logging.debug("Start date not set, parsing: %s" % " ".join(cma))

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
    if this_conversation.end_date is None:

        if len(cma) != 0:

            logging.debug("End date not set, parsing: %s" % " ".join(cma))

            if "until" in cma:
                cma = cma[cma.index("until") + 1:]

            if cma[0] in ["never", "infinite"]:
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

        if this_conversation.command == "ACK":
            response_text = "What do you want acknowledge?"
        else:
            response_text = "What do you want to set a downtime for?"

        conversations[slack_user_id] = this_conversation
        return SlackResponse(text=response_text)

    # no objects found based on filter
    if this_conversation.filter_result is None:
        problematic = ""

        logging.debug("Icinga2 object request returned empty, asking for a different filter")

        if this_conversation.command == "ACK":
            problematic = " problematic"

        response_text = "Sorry, I was not able to find any%s hosts or services for your search '%s'. Try again." \
                        % (problematic, " ".join(this_conversation.filter))

        this_conversation.filter = None
        conversations[slack_user_id] = this_conversation
        return SlackResponse(text=response_text)

    # ask for not parsed start time
    if this_conversation.command == "DOWNTIME" and this_conversation.start_date is None:

        if not this_conversation.start_date_parsing_failed:
            logging.debug("Start date not set, asking for it")
            response_text = "When should the downtime start?"
        else:
            logging.debug("Failed to parse start date, asking again for it")
            response_text = "Sorry, I was not able to understand the start date '%s'. Try again please." \
                            % this_conversation.start_date_parsing_failed

        conversations[slack_user_id] = this_conversation
        return SlackResponse(text=response_text)

    # ask for not parsed end date
    if this_conversation.end_date is None:

        if not this_conversation.end_date_parsing_failed:

            logging.debug("End date not set, asking for it")

            if this_conversation.command == "ACK":
                response_text = "When should the acknowledgement expire? Or never?"
            else:
                response_text = "When should the downtime end?"
        else:
            logging.debug("Failed to parse end date, asking again for it")
            response_text = "Sorry, I was not able to understand the end date '%s'. Try again please." \
                            % this_conversation.end_date_parsing_failed

        conversations[slack_user_id] = this_conversation
        return SlackResponse(text=response_text)

    if this_conversation.end_date and this_conversation.end_date != -1 and \
            this_conversation.end_date - 60 < datetime.now().timestamp():
        logging.debug("End date is already in the past. Ask user again for end date")

        response_text = "Sorry, end date '%s' lies (almost) in the past. Please define a valid end/expire date." % \
                        ts_to_date(this_conversation.end_date)

        this_conversation.end_date = None
        conversations[slack_user_id] = this_conversation

        return SlackResponse(text=response_text)

    if this_conversation.command == "DOWNTIME" and this_conversation.start_date > this_conversation.end_date:
        logging.debug("Start date is after end date for downtime. Ask user again for start date.")

        response_text = "Sorry, start date '%s' can't be after and date '%s'. When should the downtime start?" % \
                        (ts_to_date(this_conversation.start_date), ts_to_date(this_conversation.end_date))

        this_conversation.start_date = None
        conversations[slack_user_id] = this_conversation

        return SlackResponse(text=response_text)

    if this_conversation.description is None:
        logging.debug("Description not set, asking for it")

        conversations[slack_user_id] = this_conversation
        return SlackResponse(text="Please add a comment.")

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
            if this_conversation.command == "DOWNTIME":
                command = "Downtime"
            else:
                command = "Acknowledgement"

            confirmation = {
                "Command": command,
                "Type": this_conversation.object_type
            }
            if this_conversation.command == "DOWNTIME":
                confirmation["Start"] = ts_to_date(this_conversation.start_date)
                confirmation["End"] = ts_to_date(this_conversation.end_date)

            else:
                confirmation["Expire"] = "Never" if this_conversation.end_date == -1 else ts_to_date(
                    this_conversation.end_date)

            confirmation["Comment"] = this_conversation.description
            confirmation["Objects"] = ""

            response = SlackResponse(text="Confirm your action")

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
        return SlackResponse(text="Ok, action has been canceled!")

    if this_conversation.confirmed:

        # delete conversation history
        del conversations[slack_user_id]

        response = RequestResponse()

        i2_handle, i2_error = setup_icinga_connection(config)

        if not i2_handle:
            if i2_error is not None:
                return RequestResponse(error=i2_error)
            else:
                return RequestResponse(error="Unknown error while setting up Icinga2 connection")

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
        try:

            if this_conversation.command == "DOWNTIME":

                logging.debug("Sending Downtime to Icinga2")

                success_message = "Successfully scheduled downtime!"

                response.response = i2_handle.actions.schedule_downtime(
                    object_type=this_conversation.object_type,
                    filters='(' + ' || '.join(filter_list) + ')',
                    author=slack_user_data.get(slack_user_id).get("real_name"),
                    comment=this_conversation.description,
                    start_time=this_conversation.start_date,
                    end_time=this_conversation.end_date,
                    duration=this_conversation.end_date - this_conversation.start_date,
                    all_services=True
                )

            else:
                logging.debug("Sending Acknowledgement to Icinga2")

                success_message = "Successfully acknowledged %s problem%s!" % \
                                  (this_conversation.object_type, plural(len(filter_list)))

                # https://github.com/fmnisme/python-icinga2api/blob/master/doc/4-actions.md#-actionsacknowledge_problem
                response.response = i2_handle.actions.acknowledge_problem(
                    object_type=this_conversation.object_type,
                    filters='(' + ' || '.join(filter_list) + ')',
                    author=slack_user_data.get(slack_user_id).get("real_name"),
                    comment=this_conversation.description,
                    expiry=None if this_conversation.end_date == -1 else this_conversation.end_date,
                    sticky=True
                )

        except Exception as e:
            response.error = str(e)
            logging.error("Unable to query Icinga2 status: %s" % response.error)
            pass

        slack_response = SlackResponse()

        if response.error:
            slack_response.text = "Icinga request error"
            slack_response.add_block("*%s*" % response.text)
            slack_response.add_attachment(
                {
                    "fallback": slack_response.text,
                    "text": "Error: %s" % response.error,
                    "color": "danger"
                }
            )
            return slack_response

        slack_response.text = success_message

        return slack_response

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
    SlackResponse: questions about the action, confirmations or errors
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
        for component in i2_status.response.get("results"):

            if component["name"] == apilistener["component_name"]:
                apilistener["data"] = component["status"]["api"]
            if component["name"] == icingaapplication["component_name"]:
                icingaapplication["data"] = component["status"]["icingaapplication"]["app"]

    status_reply = SlackResponse()
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
