
from i2_slack_modules.slack_helper import BotResponse


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

            example_sub_command_shortcut = "sn"
            if getattr(requested_help_command, "sub_commands", None) is not None:

                sub_commands_list = list()
                for sub_command in requested_help_command.sub_commands:
                    sub_command_shortcut = ""
                    if sub_command.shortcut is not None:
                        if isinstance(sub_command.shortcut, list):
                            sub_command_shortcut = "|".join(sub_command.shortcut)
                        else:
                            sub_command_shortcut = sub_command.shortcut

                        example_sub_command_shortcut = sub_command_shortcut
                        sub_command_shortcut = " (%s)" % sub_command_shortcut

                    sub_commands_list.append("*Name*: %s%s" % (sub_command.name, sub_command_shortcut))

                    example_suffix = ""
                    if hasattr(sub_command, "object_type"):
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
                                        "`<bot> %s %s webserver`" % (
                                            requested_help_command.name,
                                            requested_help_command.shortcut,
                                            example_sub_command_shortcut),
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
