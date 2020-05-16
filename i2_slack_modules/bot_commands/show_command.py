
from i2_slack_modules.common import ts_to_date, my_own_function_name
from i2_slack_modules.slack_helper import *
from i2_slack_modules.icinga_connection import *


# noinspection PyUnusedLocal
def show_command(
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

    called_sub_command = None
    called_command = None

    if slack_message is None:
        logging.error("Parameter '%s' missing while calling function '%s'" % ("slack_message", my_own_function_name()))
        return slack_error_response()

    # lowercase makes parsing easier
    slack_message = slack_message.lower()

    called_command = bot_commands.get_command_called(slack_message)

    slack_message = called_command.strip_command(slack_message)

    if called_command.name != "show":
        logging.error("This function (%s) only supports command 'show'", my_own_function_name())
        return slack_error_response()

    if len(slack_message) != 0:
        # we got a filter
        logging.debug("Sub command not set, parsing: %s" % slack_message)

        if called_command.has_sub_commands():
            called_sub_command = called_command.sub_commands.get_command_called(slack_message)

            if called_sub_command:
                slack_message = called_sub_command.strip_command(slack_message)
                logging.debug("Sub command parsed: %s" % called_sub_command.name)

    if called_sub_command is None:
        response_text = "Missing sub command com, dt or ack. Use `help show` for further details."
        return BotResponse(text=response_text)

    split_slack_message = quoted_split(string_to_split=slack_message, preserve_quotations=True)

    split_slack_message = slack_user.get_last_user_filter_if_requested(split_slack_message)

    logging.debug("Filter parsed: %s" % split_slack_message)

    if called_sub_command.name == "downtime":
        object_type = "Downtime"
    else:
        object_type = "Comment"

    object_filter = None
    if called_sub_command.name == "comment":
        object_filter = ["comment.entry_type == 1"]
    elif called_sub_command.name == "acknowledgement":
        object_filter = ["comment.entry_type == 4"]

    i2_result = None
    result_list = list()
    if len(split_slack_message) <= 1:

        i2_result = get_i2_object(config, f"Host{object_type}", object_filter, split_slack_message)

        result_list.extend(i2_result.data)

    if i2_result is None or (i2_result.error is None and len(i2_result.data) == 0):

        i2_result = get_i2_object(config, f"Service{object_type}", object_filter, split_slack_message)

        result_list.extend(i2_result.data)

    # encountered Icinga request issue
    if i2_result.error:
        logging.debug("No icinga objects found for filter: %s" % split_slack_message)

        return slack_error_response(
            header="Icinga request error while trying to find matching hosts/services %s" % called_sub_command.name,
            fallback_text="Icinga Error",
            error_message=i2_result.error
        )

    if len(result_list) == 0:
        response_text = f"Sorry. No {called_sub_command.name}s found"
        if len(split_slack_message) > 0:
            response_text += " for " + " and ".join(split_slack_message)
        return BotResponse(text=response_text)

    slack_user.add_last_filter(split_slack_message)

    result_list = sorted(result_list, key=lambda k: (k['host_name'], k['service_name'], k['entry_time']))

    block_text_list = list()
    for result in result_list:

        host_url = get_web2_slack_url(result.get("host_name"), web2_url=config["icinga.web2_url"])
        service_url = get_web2_slack_url(result.get("host_name"),
                                         result.get("service_name"), web2_url=config["icinga.web2_url"])

        if result.get("service_name"):
            object_text = "*%s | %s*" % (host_url, service_url)
        else:
            object_text = "*%s*" % host_url

        if called_sub_command.name == "downtime":

            # add text and info about expiration
            this_text = result.get("comment")
            if result.get("fixed") is True:
                this_text += " (fixed from {} until {})".format(
                    ts_to_date(result.get("start_time")), ts_to_date(result.get("end_time")))
            else:
                this_text += " (flexible for {} minutes between {} and {})".format(
                    result.get("duration") / 60,
                    ts_to_date(result.get("start_time")), ts_to_date(result.get("end_time")))

        else:

            # add text and info about expiration
            this_text = result.get("text")
            if result.get("expire_time") is not None and result.get("expire_time") > 0:
                this_text += " (expires: {})".format(ts_to_date(result.get("expire_time")))

        this_title = "{} by {} ({})\n&gt;`{}`".format(object_text, result.get("author"),
                                                      ts_to_date(result.get("entry_time")), this_text)

        block_text_list.append(this_title)

    response = BotResponse()

    response.text = "Icinga %s %ss response" % (called_command.name, called_sub_command.name)

    block_text = "Found %d matching %s%s" % \
                 (len(result_list), called_sub_command.name, plural(len(result_list)))

    response.add_block(block_text)

    # fill blocks with formatted response
    block_text = ""
    for response_object in block_text_list:

        if len(block_text) + len(response_object) + 2 > slack_max_block_text_length:
            response.add_block(block_text)
            block_text = ""

        block_text += "%s\n\n" % response_object

    else:
        response.add_block(block_text)

    return response

# EOF
