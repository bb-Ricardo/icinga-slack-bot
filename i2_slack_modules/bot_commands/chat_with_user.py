
from i2_slack_modules.common import ts_to_date, parse_relative_date, my_own_function_name
from i2_slack_modules.slack_helper import *
from i2_slack_modules.icinga_connection import *
from datetime import datetime


# noinspection PyUnusedLocal
def chat_with_user(
        config=None,
        bot_commands=None,
        slack_message=None,
        slack_user=None,
        *args, **kwargs):
    """
    Have a conversation with the user about the action the user wants to perform

    Parameters
    ----------
    config : dict
        dictionary with items parsed from config file
    bot_commands: BotCommands
        class with bot commands to avoid circular imports
    slack_message : string
        slack message to parse
    slack_user : SlackUser
        SlackUser object
    args, kwargs: None
        used to hold additional args which are just ignored

    Returns
    -------
    BotResponse: questions about the action, confirmations or errors
    """

    # set properties for available action commands
    action_commands = {
        "acknowledge": {
            "filter_end_marker": "until",
            "need_start_date": False,
            "need_end_date": True,
            "need_comment": True,
            "filter_question": "What do you want acknowledge?"
        },
        "downtime": {
            "filter_end_marker": "from",
            "need_start_date": True,
            "need_end_date": True,
            "need_comment": True,
            "filter_question": "What do you want to set a downtime for?"
        },
        "comment": {
            "filter_end_marker": "with",
            "need_start_date": False,
            "need_end_date": False,
            "need_comment": True,
            "filter_question": "What do you want to add a comment to?"
        },
        "reschedule": {
            "filter_end_marker": None,
            "need_start_date": False,
            "need_end_date": False,
            "need_comment": False,
            "filter_question": "What do you want to reschedule?"
        },
        "send notification": {
            "filter_end_marker": "with",
            "need_start_date": False,
            "need_end_date": False,
            "need_comment": True,
            "filter_question": "What do you want to send notifications for?"
        },
        "delay notification": {
            "filter_end_marker": "until",
            "need_start_date": False,
            "need_end_date": True,
            "need_comment": False,
            "filter_question": "What do you want to delay notifications for?"
        },
        "remove": {
            "filter_end_marker": None,
            "need_start_date": False,
            "need_end_date": False,
            "need_comment": False,
            "has_sub_commands": True,
            "filter_question": "For which object do you want to remove {}s?"
        }
    }

    # set defaults control vars
    filter_end_marker = None
    need_start_date = False
    need_end_date = False
    need_comment = False
    has_sub_commands = False
    filter_question = None

    if slack_message is None:
        logging.error("Parameter '%s' missing while calling function '%s'" % ("slack_message", my_own_function_name()))

    if slack_user is None:
        logging.error("Parameter '%s' missing while calling function '%s'" % ("slack_user_id", my_own_function_name()))

    if slack_message is None or slack_user is None:
        return slack_error_response()

    # New conversation
    if slack_user.conversation is None:
        slack_user.start_conversation()

    conversation = slack_user.conversation

    # check or command
    if conversation.command is None:
        logging.debug("Command not set, parsing: %s" % slack_message)
        conversation.command = bot_commands.get_command_called(slack_message)

        if conversation.command.name not in action_commands.keys():
            conversation.command = None
            return None

        logging.debug("Command parsed: %s" % conversation.command.name)

        slack_message = conversation.command.strip_command(slack_message)

    if conversation.command is not None:

        command_data = action_commands.get(conversation.command.name)

        if command_data is not None:
            # update control vars
            filter_end_marker = command_data.get("filter_end_marker", None)
            need_start_date = command_data.get("need_start_date", False)
            need_end_date = command_data.get("need_end_date", False)
            need_comment = command_data.get("need_comment", False)
            has_sub_commands = command_data.get("has_sub_commands", False)
            filter_question = command_data.get("filter_question", None)

    if has_sub_commands is True and conversation.sub_command is None:

        if len(slack_message) != 0:
            # we got a filter
            logging.debug("Sub command not set, parsing: %s" % slack_message)

            if conversation.command.has_sub_commands():
                conversation.sub_command = \
                    conversation.command.sub_commands.get_command_called(slack_message)

                if conversation.sub_command:
                    slack_message = conversation.sub_command.strip_command(slack_message)
                    logging.debug("Sub command parsed: %s" % conversation.sub_command.name)

    # check for filter
    if conversation.filter is None:
        if len(quoted_split(string_to_split=slack_message)) != 0:
            # we got a filter
            logging.debug("Filter not set, parsing: %s" % slack_message)

            split_slack_message = quoted_split(string_to_split=slack_message, preserve_quotations=True)

            #  everything left of the index string will be parsed as filter
            if filter_end_marker is not None and filter_end_marker in [s.lower() for s in split_slack_message]:

                index = [s.lower() for s in split_slack_message].index(filter_end_marker)

                # get end of filter list
                filter_list = split_slack_message[0:index]

                # strip index string from slack message on comments
                if filter_end_marker == "with":
                    index += 1

                # strip the filter from the supplied string
                slack_message = " ".join(split_slack_message[index:])

            else:
                # index string not found
                # assuming the whole message is meant to be a filter
                filter_list = split_slack_message
                slack_message = ""

            filter_list = slack_user.get_last_user_filter_if_requested(filter_list)

            logging.debug("Filter parsed: %s" % filter_list)

            if len(filter_list) > 0:
                conversation.filter = filter_list
                slack_user.add_last_filter(conversation.filter)

    # split slack_message into an array (chat message array)
    cma = quoted_split(string_to_split=slack_message, preserve_quotations=True)

    # try to find objects based on filter
    if conversation.filter and conversation.filter_result is None:

        logging.debug("Filter result list empty. Query Icinga for objects.")

        host_filter = list()
        service_filter = list()
        if conversation.command.name == "acknowledge":
            host_filter = ["host.state != 0"]
            service_filter = ["service.state != 0"]

        # query hosts and services
        if len(conversation.filter) == 1:

            object_type = "Host"
            if conversation.sub_command is not None:
                if conversation.sub_command.name == "downtime":
                    object_type = "HostDowntime"
                else:
                    object_type = "HostComment"

            i2_result = get_i2_object(config, object_type, host_filter, conversation.filter)

            if i2_result.error is None and len(i2_result.data) == 0:
                object_type = "Service"
                if conversation.sub_command is not None:
                    if conversation.sub_command.name == "downtime":
                        object_type = "ServiceDowntime"
                    else:
                        object_type = "ServiceComment"

                i2_result = get_i2_object(config, object_type, service_filter, conversation.filter)

        # just query services
        else:
            object_type = "Service"
            if conversation.sub_command is not None:
                if conversation.sub_command.name == "downtime":
                    object_type = "ServiceDowntime"
                else:
                    object_type = "ServiceComment"

            i2_result = get_i2_object(config, object_type, service_filter, conversation.filter)

        # encountered Icinga request issue
        if i2_result.error:
            logging.debug("No icinga objects found for filter: %s" % conversation.filter)

            return slack_error_response(
                header="Icinga request error while trying to find matching hosts/services",
                fallback_text="Icinga Error",
                error_message=i2_result.error
            )

        # we can set a downtime for all objects no matter their state
        if conversation.sub_command is not None:

            if conversation.sub_command.name == "downtime" and len(i2_result.data) > 0:
                conversation.filter_result = i2_result.data
            else:
                # filter results based on sub command name
                ack_filter_result = list()
                for result in i2_result.data:
                    if conversation.sub_command.name == "comment" and result.get("entry_type") == 1:
                        ack_filter_result.append(result)
                    if conversation.sub_command.name == "acknowledgement" and result.get("entry_type") == 4:
                        ack_filter_result.append(result)

                if len(ack_filter_result) > 0:
                    conversation.filter_result = ack_filter_result

        elif conversation.command.name == "acknowledge" and len(i2_result.data) > 0:

            # only objects which are not acknowledged can be acknowledged
            ack_filter_result = list()
            for result in i2_result.data:
                # only add results which are not acknowledged
                if result.get("acknowledgement") == 0:
                    ack_filter_result.append(result)

            if len(ack_filter_result) > 0:
                conversation.filter_result = ack_filter_result

        else:
            conversation.filter_result = i2_result.data

        # save current conversation state if filter returned any objects
        if conversation.filter_result and len(conversation.filter_result) > 0:
            sub_command_name = ""
            if conversation.sub_command is not None:
                sub_command_name = f" {conversation.sub_command.name}"

            logging.debug("Found %d objects for command %s%s" %
                          (len(conversation.filter_result), conversation.command.name, sub_command_name))

            conversation.object_type = object_type
        else:
            conversation.filter_result = None

    # parse start time information for downtime
    if need_start_date is True and conversation.start_date is None and conversation.filter_result is not None:

        if len(cma) != 0:

            logging.debug("Start date not set, parsing: %s" % " ".join(cma))

            date_string_parse = " ".join(cma)

            cma_lower = [s.lower() for s in cma]

            from_index = None
            until_index = None
            if "from" in cma_lower:
                from_index = cma_lower.index("from")

                if "until" in cma_lower:
                    until_index = cma_lower.index("until")

            if from_index is not None and len(cma) > from_index + 1:
                cma = cma[from_index + 1:]

                if until_index is not None:
                    until_index -= 1
                    date_string_parse = " ".join(cma[0:until_index])
                    cma = cma[until_index:]

            start_date_data = parse_relative_date(date_string_parse)

            if start_date_data:

                logging.debug("Start date successfully parsed")

                # get timestamp from returned datetime object
                if start_date_data.get("dt"):
                    conversation.start_date = start_date_data.get("dt").timestamp()

                if len(cma) >= 1 and cma[0].lower() != "until":
                    cma = date_string_parse[start_date_data.get("mend"):].strip().split(" ")
            else:
                conversation.start_date_parsing_failed = date_string_parse

    # parse end time information
    if need_end_date is True and conversation.end_date is None and conversation.filter_result is not None:

        if len(cma) != 0:

            logging.debug("End date not set, parsing: %s" % " ".join(cma))

            cma_lower = [s.lower() for s in cma]

            until_index = None
            if "until" in cma_lower:
                until_index = cma_lower.index("until")

            if until_index is not None and len(cma) > until_index + 1:
                cma = cma[until_index + 1:]

            if len(cma) >= 1 and cma[0].lower() in ["never", "infinite"]:
                # add rest of message as description
                conversation.end_date = -1
                del cma[0]

            else:
                string_parse = " ".join(cma)
                end_date_data = parse_relative_date(string_parse)

                if end_date_data:

                    # get timestamp from returned datetime object
                    if end_date_data.get("dt"):
                        conversation.end_date = end_date_data.get("dt").timestamp()

                    # add rest of string back to cma
                    cma = string_parse[end_date_data.get("mend"):].strip().split(" ")
                else:
                    conversation.end_date_parsing_failed = string_parse

    if need_comment is True and conversation.description is None and conversation.filter_result is not None:

        if len(cma) != 0 and len("".join(cma).strip()) != 0:
            logging.debug("Description not set, parsing: %s" % " ".join(cma))

            conversation.description = " ".join(cma)
            cma = list()

    # ask for sub command
    if has_sub_commands is True and conversation.sub_command is None:

        logging.debug("Sub command not set, asking for it")

        response_text = \
            "Sorry, I wasn't able to parse your sub command. Check `help %s` to get available sub commands" % \
            conversation.command.name

        return BotResponse(text=response_text)

    # ask for missing info
    if conversation.filter is None:

        logging.debug("Filter not set, asking for it")

        if has_sub_commands is True:
            filter_question = filter_question.format(conversation.sub_command.name)

        return BotResponse(text=filter_question)

    # no objects found based on filter
    if conversation.filter_result is None:
        problematic = ""

        logging.debug("Icinga2 object request returned empty, asking for a different filter")

        if conversation.command.name == "acknowledge":
            problematic = " problematic"

        object_text = "hosts or services"
        if conversation.sub_command is not None:
            object_text = conversation.sub_command.name

        response_text = "Sorry, I was not able to find any%s %s for your search '%s'. Try again." \
                        % (problematic, object_text, " ".join(conversation.filter))

        conversation.filter = None
        return BotResponse(text=response_text)

    # ask for not parsed start time
    if need_start_date is True and conversation.start_date is None:

        if not conversation.start_date_parsing_failed:
            logging.debug("Start date not set, asking for it")
            response_text = "When should the downtime start?"
        else:
            logging.debug("Failed to parse start date, asking again for it")
            response_text = "Sorry, I was not able to understand the start date '%s'. Try again please." \
                            % conversation.start_date_parsing_failed

        return BotResponse(text=response_text)

    # ask for not parsed end date
    if need_end_date is True and conversation.end_date is None:

        if not conversation.end_date_parsing_failed:

            logging.debug("End date not set, asking for it")

            if conversation.command.name == "acknowledge":
                response_text = "When should the acknowledgement expire? Or never?"
            else:
                response_text = "When should the downtime end?"
        else:
            logging.debug("Failed to parse end date, asking again for it")
            response_text = "Sorry, I was not able to understand the end date '%s'. Try again please." \
                            % conversation.end_date_parsing_failed

        return BotResponse(text=response_text)

    if conversation.end_date and conversation.end_date != -1 and \
            conversation.end_date - 60 < datetime.now().timestamp():
        logging.debug("End date is already in the past. Ask user again for end date")

        response_text = "Sorry, end date '%s' lies (almost) in the past. Please define a valid end/expire date." % \
                        ts_to_date(conversation.end_date)

        conversation.end_date = None

        return BotResponse(text=response_text)

    if need_start_date is True and conversation.start_date > conversation.end_date:

        logging.debug("Start date is after end date for downtime. Ask user again for start date.")

        response_text = "Sorry, start date '%s' can't be after and date '%s'. When should the downtime start?" % \
                        (ts_to_date(conversation.start_date), ts_to_date(conversation.end_date))

        conversation.start_date = None

        return BotResponse(text=response_text)

    if need_comment is True and conversation.description is None:

        logging.debug("Description not set, asking for it")

        return BotResponse(text="Please add a comment.")

    # now we seem to have all information and ask user if that's what the user wants
    if not conversation.confirmed:

        if conversation.confirmation_sent:
            if cma[0].startswith("y") or cma[0].startswith("Y"):
                conversation.confirmed = True
            elif cma[0].startswith("n") or cma[0].startswith("N"):
                conversation.canceled = True
            else:
                # see if user tried to filter the selection (i.e.: 1,2)
                if conversation.sub_command is not None:
                    selection_list = [x.strip() for x in " ".join(cma).split(",")]
                    if len(selection_list) > 0:
                        objects_to_keep = list()
                        for selection in selection_list:
                            try:
                                objects_to_keep.append(conversation.filter_result[int(selection) - 1])
                            except Exception:
                                pass

                        if len(objects_to_keep) > 0:
                            conversation.filter_result = objects_to_keep

                conversation.confirmation_sent = False

        if not conversation.confirmation_sent:

            # get object type
            if conversation.command.name == "acknowledge":
                command = "Acknowledgement"
            else:
                command = conversation.command.name.capitalize()

            confirmation_type = conversation.object_type
            if conversation.sub_command is not None:
                confirmation_type = conversation.sub_command.name

            confirmation = {
                "Command": command,
                "Type": confirmation_type
            }
            if need_start_date is True:
                confirmation["Start"] = ts_to_date(conversation.start_date)
                confirmation["End"] = ts_to_date(conversation.end_date)

            elif conversation.command.name == "acknowledge":
                confirmation["Expire"] = "Never" if conversation.end_date == -1 else ts_to_date(
                    conversation.end_date)

            elif conversation.command.name == "delay notification":
                confirmation["Delayed until"] = "Never" if conversation.end_date == -1 else ts_to_date(
                    conversation.end_date)

            if need_comment is True:
                confirmation["Comment"] = conversation.description

            confirmation["Objects"] = ""

            response = BotResponse(text="Confirm your action")

            confirmation_fields = list()
            for title, value in confirmation.items():
                confirmation_fields.append(">*%s*: %s" % (title, value))

            object_num = 0
            for i2_object in conversation.filter_result[0:10]:
                object_num += 1
                host_name = service_name = comment_text = author = None
                bullet_text = "•"

                if conversation.object_type == "Service":
                    host_name = i2_object.get("host_name")
                    service_name = i2_object.get("name")

                elif "Comment" in conversation.object_type or "Downtime" in conversation.object_type:

                    bullet_text = f"{object_num}."
                    host_name = i2_object.get("host_name")
                    if len(i2_object.get("service_name", "")) > 0:
                        service_name = i2_object.get("service_name")

                    if i2_object.get("comment") is not None:
                        comment_text = i2_object.get("comment")
                    else:
                        comment_text = i2_object.get("text")

                    author = i2_object.get("author")

                else:  # host
                    host_name = i2_object.get("name")

                host_url = get_web2_slack_url(host_name, web2_url=config["icinga.web2_url"])
                service_url = get_web2_slack_url(host_name, service_name, web2_url=config["icinga.web2_url"])

                if service_name is not None:
                    object_text = "%s | %s" % (host_url, service_url)
                else:
                    object_text = host_url

                if comment_text is not None:
                    object_text += f" - {comment_text}"
                if comment_text is not None:
                    object_text += f" (by: {author})"

                confirmation_fields.append(u">\t%s %s" % (bullet_text, object_text))

            if len(conversation.filter_result) > 10:
                confirmation_fields.append(">\t... and %d more" % (len(conversation.filter_result) - 10))
            response.add_block("\n".join(confirmation_fields))

            if conversation.sub_command is not None:
                response.add_block("Do you want to confirm this action (yes|no)\n"
                                   "or do you want to select single/multiple %s (i.e.: 1,2)?:" %
                                   conversation.sub_command.name)
            else:
                response.add_block("Do you want to confirm this action?:")

            conversation.confirmation_sent = True

            return response

    if conversation.canceled:
        slack_user.reset_conversation()
        return BotResponse(text="Ok, action has been canceled!")

    if conversation.confirmed:

        # delete conversation history
        slack_user.reset_conversation()

        i2_handle, i2_error = setup_icinga_connection(config)

        if not i2_handle:
            if i2_error is not None:
                error_message = i2_error
            else:
                error_message = "Unknown error while setting up Icinga2 connection"

            return slack_error_response(header="Icinga request error", error_message=error_message)

        # define filters
        filter_list = list()
        if conversation.object_type == "Host":
            for i2_object in conversation.filter_result:
                filter_list.append('host.name=="%s"' % i2_object.get("name"))
        else:
            for i2_object in conversation.filter_result:
                filter_list.append('( host.name=="%s" && service.name=="%s" )' %
                                   (i2_object.get("host_name"), i2_object.get("name")))

        success_message = None
        i2_error = None

        # get username to add as comment
        this_user_info = slack_user.data

        author_name = "Anonymous Slack user"
        if this_user_info is not None and this_user_info.get("real_name"):
            author_name = this_user_info.get("real_name")

        icinga2_filters = '(' + ' || '.join(filter_list) + ')'

        try:

            if conversation.command.name == "downtime":

                logging.debug("Sending Downtime to Icinga2")

                success_message = "Successfully scheduled downtime!"

                i2_response = i2_handle.actions.schedule_downtime(
                    object_type=conversation.object_type,
                    filters=icinga2_filters,
                    author=author_name,
                    comment=conversation.description,
                    start_time=conversation.start_date,
                    end_time=conversation.end_date,
                    duration=conversation.end_date - conversation.start_date,
                    all_services=True
                )

            elif conversation.command.name == "acknowledge":
                logging.debug("Sending Acknowledgement to Icinga2")

                success_message = "Successfully acknowledged %s problem%s!" % \
                                  (conversation.object_type, plural(len(filter_list)))

                i2_response = i2_handle.actions.acknowledge_problem(
                    object_type=conversation.object_type,
                    filters=icinga2_filters,
                    author=author_name,
                    comment=conversation.description,
                    expiry=None if conversation.end_date == -1 else conversation.end_date,
                    sticky=True
                )

            elif conversation.command.name == "comment":
                logging.debug("Sending Comment to Icinga2")

                success_message = "Successfully added %s comment%s!" % \
                                  (conversation.object_type, plural(len(filter_list)))

                i2_response = i2_handle.actions.add_comment(
                    object_type=conversation.object_type,
                    filters=icinga2_filters,
                    author=author_name,
                    comment=conversation.description
                )

            elif conversation.command.name == "reschedule":
                logging.debug("Sending reschedule check to Icinga2")

                success_message = "Successfully rescheduled %s check%s!" % \
                                  (conversation.object_type, plural(len(filter_list)))

                i2_response = i2_handle.actions.reschedule_check(
                    object_type=conversation.object_type,
                    filters=icinga2_filters,
                )

            elif conversation.command.name == "send notification":
                logging.debug("Sending custom notification to Icinga2")

                success_message = "Successfully sent %s notification%s!" % \
                                  (conversation.object_type, plural(len(filter_list)))

                i2_response = i2_handle.actions.send_custom_notification(
                    object_type=conversation.object_type,
                    filters=icinga2_filters,
                    author=author_name,
                    comment=conversation.description
                )

            elif conversation.command.name == "delay notification":
                logging.debug("Sending delay notification to Icinga2")

                success_message = "Successfully delayed %s notification%s!" % \
                                  (conversation.object_type, plural(len(filter_list)))

                i2_response = i2_handle.actions.delay_notification(
                    object_type=conversation.object_type,
                    filters=icinga2_filters,
                    timestamp=conversation.end_date
                )
            elif conversation.command.name == "remove":

                logging.debug(f"Sending remove {conversation.sub_command.name} to Icinga2")

                success_message = f"Successfully removed {conversation.sub_command.name}!"

                if conversation.sub_command.name == "acknowledgement":

                    for acknowledgement in conversation.filter_result:

                        this_object_type = "Host"
                        this_filter = 'host.name=="%s"' % acknowledgement.get("host_name")
                        if len(acknowledgement.get("service_name", "")) > 0:
                            this_object_type = "Service"
                            this_filter += ' && service.name=="%s"' % acknowledgement.get("service_name")

                        i2_response = i2_handle.actions.remove_acknowledgement(
                            object_type=this_object_type,
                            filters=this_filter,
                        )

                if conversation.sub_command.name == "comment":

                    for comment in conversation.filter_result:
                        name = "!".join(
                            [comment.get("host_name"), comment.get("service_name"), comment.get("name")]
                        ).replace("!!", "!")
                        i2_response = i2_handle.actions.remove_comment(
                            object_type="Comment",
                            name=name,
                            filters=None  # bug in icinga2apic
                        )

                if conversation.sub_command.name == "downtime":

                    for downtime in conversation.filter_result:
                        name = "!".join(
                            [downtime.get("host_name"), downtime.get("service_name"), downtime.get("name")]
                        ).replace("!!", "!")
                        i2_response = i2_handle.actions.remove_downtime(
                            object_type="Downtime",
                            name=name,
                            filters=None
                        )

        except Exception as e:
            i2_error = str(e)
            logging.error("Unable to perform Icinga2 action: %s" % i2_error)
            pass

        if i2_error:
            return slack_error_response(header="Icinga request error", error_message=i2_error)

        return BotResponse(text=success_message)

    return None
