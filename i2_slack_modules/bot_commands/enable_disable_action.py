
from i2_slack_modules.common import my_own_function_name
from i2_slack_modules.slack_helper import BotResponse, slack_error_response
from i2_slack_modules.icinga_connection import *


# noinspection PyTypeChecker
# noinspection PyUnusedLocal
def enable_disable_action(
        config=None,
        bot_commands=None,
        slack_message=None,
        slack_user=None,
        *args, **kwargs):
    """
    Have a conversation with the user about the attribute the user wants to enable/disable

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

    if slack_message is None:
        logging.error("Parameter '%s' missing while calling function '%s'" % ("slack_message", my_own_function_name()))

    if slack_user is None:
        logging.error("Parameter '%s' missing while calling function '%s'" % ("slack_user", my_own_function_name()))

    if slack_message is None or slack_user is None:
        return slack_error_response()

    # New conversation
    if slack_user.conversation is None:
        slack_user.start_conversation()

    this_conversation = slack_user.conversation

    # check or command
    if this_conversation.command is None:
        logging.debug("Command not set, parsing: %s" % slack_message)
        this_conversation.command = bot_commands.get_command_called(slack_message)

        # see if checking for sub_commands works better here
        if this_conversation.command.name not in ["enable", "disable"]:
            this_conversation.command = None
            return None

        logging.debug("Command parsed: %s" % this_conversation.command.name)

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

    # check for filter
    if this_conversation.sub_command is not None and \
            this_conversation.sub_command.object_type != "global" and this_conversation.filter is None:
        if len(slack_message) != 0:

            filter_list = quoted_split(string_to_split=slack_message, preserve_quotations=True)

            filter_list = slack_user.get_last_user_filter_if_requested(filter_list)

            logging.debug("Filter parsed: %s" % filter_list)

            this_conversation.filter = filter_list
            slack_user.add_last_filter(this_conversation.filter)

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

        # save current conversation state if filter returned any objects
        if i2_result.data and len(i2_result.data) > 0:
            logging.debug("Found %d objects to %s %s for" %
                          (len(i2_result.data),
                           this_conversation.command.name,
                           this_conversation.sub_command.name))

            this_conversation.filter_result = i2_result.data
            this_conversation.filter_used = i2_result.filter

    # ask for sub command
    if this_conversation.sub_command is None:

        logging.debug("Sub command not set, asking for it")

        response_text = \
            "%sSorry, I wasn't able to parse your sub command. Check `help %s` to get available sub commands" % \
            (this_conversation.get_path(), this_conversation.command.name)

        return BotResponse(text=response_text)

    # ask for missing info
    if this_conversation.sub_command.object_type != "global" and this_conversation.filter is None:

        logging.debug("Filter not set, asking for it")

        response_text = "%sFor which object do you want to %s %s?" % (
            this_conversation.get_path(),
            this_conversation.command.name,
            this_conversation.sub_command.name)

        return BotResponse(text=response_text)

    # no objects found based on filter
    if this_conversation.sub_command.object_type != "global" and this_conversation.filter_result is None:

        logging.debug("Icinga2 object request returned empty, asking for a different filter")

        response_text = "%sSorry, I was not able to find any hosts or services for your search '%s'. Try again." \
                        % (this_conversation.get_path(), " ".join(this_conversation.filter))

        this_conversation.filter = None
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

            return response

    if this_conversation.canceled:
        slack_user.reset_conversation()
        return BotResponse(text="%sOk, action has been canceled!" % this_conversation.get_path())

    if this_conversation.confirmed:

        # delete conversation history
        slack_user.reset_conversation()

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
