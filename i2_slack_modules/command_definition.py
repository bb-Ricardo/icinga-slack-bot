####
#
# define and describe implemented commands
#

# need import here as they will be called on whatever is defined in command_definition command_handlers
# noinspection PyUnresolvedReferences
from .bot_commands import (
    slack_command_ping,
    reset_conversation,
    run_icinga_status_query,
    get_icinga_status_overview,
    slack_command_help,
    chat_with_user,
    get_icinga_daemon_status,
    enable_disable_action
)
import logging
from typing import Callable, Tuple, Optional

enable_disable_sub_commands = [
    {
        "name": "event handlers global",
        "icinga_attr_name": "enable_event_handlers",
        "object_type": "global",
        "shortcut": "ehg"
    },
    {
        "name": "host event handlers",
        "icinga_attr_name": "enable_event_handler",
        "object_type": "Host",
        "shortcut": "heh"
    },
    {
        "name": "service event handlers",
        "icinga_attr_name": "enable_event_handler",
        "object_type": "Service",
        "shortcut": "seh"
    },
    {
        "name": "flap detection global",
        "icinga_attr_name": "enable_flapping",
        "object_type": "global",
        "shortcut": "fdg"
    },
    {
        "name": "host flap detection",
        "icinga_attr_name": "enable_flapping",
        "object_type": "Host",
        "shortcut": "hfd"
    },
    {
        "name": "service flap detection",
        "icinga_attr_name": "enable_flapping",
        "object_type": "Service",
        "shortcut": "sfd"
    },
    {
        "name": "host checks global",
        "icinga_attr_name": "enable_host_checks",
        "object_type": "global",
        "shortcut": "hcg"
    },
    {
        "name": "service checks global",
        "icinga_attr_name": "enable_service_checks",
        "object_type": "global",
        "shortcut": "scg"
    },
    {
        "name": "active host checks",
        "icinga_attr_name": "enable_active_checks",
        "object_type": "Host",
        "shortcut": "ahc"
    },
    {
        "name": "active service checks",
        "icinga_attr_name": "enable_active_checks",
        "object_type": "Service",
        "shortcut": "asc"
    },
    {
        "name": "passive host checks",
        "icinga_attr_name": "enable_passive_checks",
        "object_type": "Host",
        "shortcut": "phc"
    },
    {
        "name": "passive service checks",
        "icinga_attr_name": "enable_passive_checks",
        "object_type": "Service",
        "shortcut": "psc"
    },
    {
        "name": "notifications global",
        "icinga_attr_name": "enable_notifications",
        "object_type": "global",
        "shortcut": "ng"
    },
    {
        "name": "host notifications",
        "icinga_attr_name": "enable_notifications",
        "object_type": "Host",
        "shortcut": "hn"
    },
    {
        "name": "service notifications",
        "icinga_attr_name": "enable_notifications",
        "object_type": "Service",
        "shortcut": "sn"
    }
]

remove_sub_commands = [
    {
        "name": "acknowledgement",
        "shortcut": "ack"
    },
    {
        "name": "downtime",
        "shortcut": "dt"
    },
    {
        "name": "comment",
        "shortcut": "com"
    },
]

implemented_commands = [
    {
        "name": "help",
        "shortcut": None,
        "short_description": "this help",
        "long_description": "This command displays all implemented commands and details about each command\n"
                            "You can access the detailed help with `help <command>` and it will return a\n"
                            "detailed help about this particular command.",
        "command_handler": "slack_command_help"
    },
    {
        "name": "ping",
        "shortcut": None,
        "short_description": "bot will answer with `pong`",
        "long_description": "This can simply be used to see if the bot is still alive."
                            " Bot will simply answer with `pong`.",
        "command_handler": "slack_command_ping"
    },
    {
        "name": "service status",
        "shortcut": "ss",
        "short_description": "display service status of all services in non OK state",
        "long_description": "This command can be used to query icinga for current service states.\n"
                            "The default filter will only display services which are *NOT* OK and "
                            "have *not been acknowledged* and are *not in a downtime*.\n"
                            "You can also request certain service states like:\n"
                            "• `ok`\n"
                            "• `warning | warn`\n"
                            "• `critical | crit`\n"
                            "• `unknown`\n"
                            "• `all`\n"
                            "• `problems`\n"
                            "Filter can be combined like `warn crit` which would return all services "
                            "in WARNING or CRITICAL state.\n"
                            "To display all service states just add the keyword `all` to your command.\n"
                            "You can add host names or services names to any status command.\n"
                            "To display all services no matter if they are acknowledged or in a downtime "
                            "then you can add the keyword `problems`\n"
                            "Also just parts of host and service names can be used to search for objects.\n"
                            "*IMPORTANT:* when using the service status command only the first two names will "
                            "be used as filter and all others are going to be ignored.\n"
                            "*_Examples_*:\n"
                            "`ss warn crit ntp`\n"
                            "\twill display all services which match \"ntp\" and are in state CRITICAL or WARNING\n"
                            "`ss webserver nginx`\n"
                            "\twill display all services which match \"webserver\" and \"nginx\"\n"
                            "`ss problems`\n"
                            "\twill display problematic services including ones which are acknowledged or "
                            "in a downtime\n",
        "command_handler": "run_icinga_status_query",
        "status_type": "Service"
    },
    {
        "name": "host status",
        "shortcut": "hs",
        "short_description": "display host status of all hosts in non UP state",
        "long_description": "This command can be used to query icinga for current host states.\n"
                            "The default filter will only display hosts which are *NOT* UP and "
                            "have *not been acknowledged* and are *not in a downtime*.\n"
                            "You can also request certain host states like:\n"
                            "• `up`\n"
                            "• `down`\n"
                            "• `unreachable | unreach`\n"
                            "• `all`\n"
                            "• `problems`\n"
                            "Filter can be combined like `down unreach` which would return all hosts "
                            "in DOWN or UNREACHABLE state.\n"
                            "To display all host states just add the keyword `all` to your command.\n"
                            "To display all services no matter if they are acknowledged or in a downtime "
                            "then you can add the keyword `problems`\n"
                            "Also just parts of host names can be used to search for objects.\n"
                            "*_Examples_*:\n"
                            "`hs down test`\n"
                            "\twill display all hosts in DOWN state which match \"test\" "
                            "as host name like \"testserver\" or \"devtest\"\n"
                            "`hs all`\n"
                            "\twill return all hosts and their status\n"
                            "`hs problems`\n"
                            "\twill display problematic hosts including ones which are acknowledged or "
                            "in a downtime\n",
        "command_handler": "run_icinga_status_query",
        "status_type": "Host"
    },
    {
        "name": "status overview",
        "shortcut": "so",
        "short_description": "display a summary of current host and service status numbers",
        "long_description": "This command displays a combined view with numbers about\n"
                            "the current state of all hosts and services. It will show how many\n"
                            "objects are acknowledged or in a downtime and how many are unhandled.",
        "command_handler": "get_icinga_status_overview"
    },
    {
        "name": "acknowledge",
        "shortcut": "ack",
        "short_description": "acknowledge problematic hosts or services",
        "long_description": "This command will start a dialog to set an acknowledgement for "
                            "an unhandled service or host. This can be started with this command "
                            "and the bot will ask questions about the details on following order:\n"
                            "*1.* host/service filter\n"
                            "*2.* time when acknowledgement should expire (or never)\n"
                            "*3.* a comment which should be added to the acknowledgement\n"
                            "*INFO*: time can be submitted in a relative format like:\n"
                            "_tomorrow 3pm_, _friday noon_ or _monday morning_\n"
                            "Or more specific like _january 2nd_ or even more specific "
                            "like _29.02.2020 13:00_. Just try and see what works best for you.\n"
                            "At the end the bot will ask you for a confirmation which can "
                            "be answered with `yes` or just `y` or `no`. "
                            "After that the bot will report if the action was successful or not.\n"
                            "*SORT CUT:*\n"
                            "It's also possible to short cut the whole Q/A and just issue the "
                            "action in one command:\n"
                            "`ack my-server ntp until tomorrow evening Wrong ntp config, needs update`\n"
                            "This will acknowledge a problematic service ntp on my-server "
                            "until 6pm the following day.\n"
                            "*STRUCTURE:*\n"
                            "`ack <host> <service> until <time> <comment>` or\n"
                            "`ack <host> until <time> <comment>` or\n"
                            "`ack <service> until <time> <comment>`\n",
        "command_handler": "chat_with_user"
    },
    {
        "name": "downtime",
        "shortcut": "dt",
        "short_description": "set a downtime for hosts/services",
        "long_description": "This command will start a dialog to set a downtime for "
                            "a service or host. This can be started with this command "
                            "and the bot will ask questions about the details on following order:\n"
                            "*1.* host/service filter\n"
                            "*2.* time when the downtime should start (now)\n"
                            "*3.* time when the downtime should end\n"
                            "*4.* a comment which should be added to the downtime\n"
                            "*INFO*: time can be submitted in a relative format like:\n"
                            "_tomorrow 3pm_, _friday noon_ or _monday morning_\n"
                            "Or more specific like _january 2nd_ or even more specific "
                            "like _29.02.2020 13:00_. Just try and see what works best for you.\n"
                            "At the end the bot will ask you for a confirmation which can "
                            "be answered with `yes` or just `y` or `no`. "
                            "After that the bot will report if the action was successful or not.\n"
                            "*SORT CUT:*\n"
                            "It's also possible to short cut the whole Q/A and just issue the "
                            "action in one command:\n"
                            "`dt my-server ntp from now until tomorrow evening NTP update`\n"
                            "This will set a downtime for the service ntp on my-server "
                            "until 6pm the following day.\n"
                            "*STRUCTURE:*\n"
                            "`dt <host> <service> from <time> until <time> <comment>` or\n"
                            "`dt <host> from <time> until <time> <comment>` or\n"
                            "`dt <service> from <time> until <time> <comment>`\n",
        "command_handler": "chat_with_user"
    },
    {
        "name": "comment",
        "shortcut": "com",
        "short_description": "add a comment to hosts/services",
        "long_description": "This command will start a dialog to set a comment for "
                            "a service or host. This can be started with this command "
                            "and the bot will ask questions about the details on following order:\n"
                            "*1.* host/service filter\n"
                            "*2.* the comment which should be added\n"
                            "At the end the bot will ask you for a confirmation which can "
                            "be answered with `yes` or just `y` or `no`. "
                            "After that the bot will report if the action was successful or not.\n"
                            "*SORT CUT:*\n"
                            "It's also possible to short cut the whole Q/A and just issue the "
                            "action in one command:\n"
                            "`com my-server ntp with NTP source currently unavailable`\n"
                            "*STRUCTURE:*\n"
                            "`com <host> <service> with <comment>` or\n"
                            "`com <host> <host> with <comment>` or\n"
                            "`com <service> with <comment>`\n",
        "command_handler": "chat_with_user"
    },
    {
        "name": "reschedule",
        "shortcut": "rs",
        "short_description": "reschedule a host/service check",
        "long_description": "This command will start a dialog to reschedule "
                            "a service or host check. This can be started with this command "
                            "and the bot will ask for a host/service filter:\n"
                            "At the end the bot will ask you for a confirmation which can "
                            "be answered with `yes` or just `y` or `no`. "
                            "After that the bot will report if the action was successful or not.\n"
                            "*SORT CUT:*\n"
                            "It's also possible to short cut and just issue the "
                            "action in one command:\n"
                            "`rs my-server ntp`\n"
                            "*STRUCTURE:*\n"
                            "`rs <host> <service>` or\n"
                            "`rs <host> <host>` or\n"
                            "`rs <service>`\n",
        "command_handler": "chat_with_user"
    },
    {
        "name": "send notification",
        "shortcut": "sn",
        "short_description": "send a costum host/service notification",
        "long_description": "This command will start a dialog to send a custom "
                            "service or host notification. This can be started with this command "
                            "and the bot will ask questions about the details on following order:\n"
                            "*1.* host/service filter\n"
                            "*2.* the comment which should be sent\n"
                            "At the end the bot will ask you for a confirmation which can "
                            "be answered with `yes` or just `y` or `no`. "
                            "After that the bot will report if the action was successful or not.\n"
                            "*SORT CUT:*\n"
                            "It's also possible to short cut and just issue the "
                            "action in one command:\n"
                            "`sn my-server ntp with NTP source currently unavailable`\n"
                            "*STRUCTURE:*\n"
                            "`sn <host> <service> with <comment>` or\n"
                            "`sn <host> <host> with <comment>` or\n"
                            "`sn <service> with <comment>`\n",
        "command_handler": "chat_with_user"
    },
    {
        "name": "delay notification",
        "shortcut": "dn",
        "short_description": "delay host/service notifications",
        "long_description": "This command will start a dialog to delay "
                            "service or host notifications. This can be started with this command "
                            "and the bot will ask questions about the details on following order:\n"
                            "*1.* host/service filter\n"
                            "*2.* time until the notifications should be delayed to\n"
                            "At the end the bot will ask you for a confirmation which can "
                            "be answered with `yes` or just `y` or `no`. "
                            "After that the bot will report if the action was successful or not.\n"
                            "*SORT CUT:*\n"
                            "It's also possible to short cut and just issue the "
                            "action in one command:\n"
                            "`dn my-server ntp until tomorrow evening`\n"
                            "This will delay notifications for the service ntp on my-server "
                            "until 6pm the following day.\n"
                            "*STRUCTURE:*\n"
                            "`dn <host> <service> with <time>` or\n"
                            "`dn <host> <host> with <time>` or\n"
                            "`dn <service> with <time>`\n",
        "command_handler": "chat_with_user"
    },
    {
        "name": "remove",
        "shortcut": "rm",
        "short_description": "remove a comment/downtime/acknowledgement",
        "long_description": "This command will remove a comment/downtime/acknowledgement. "
                            "At the end the bot will ask you for a selection or a "
                            "confirmation which can be answered with `yes` or "
                            "just `y` or `no` or the item in the list comma separated.\n"
                            "After that the bot will report if the action was successful or not.\n"
                            "*SORT CUT:*\n"
                            "It's also possible to short cut and just issue the "
                            "action in one command:\n"
                            "`remove ack from ntp`\n"
                            "This will ask remove the acknowledgement from all hosts and service with ntp\n"
                            "*STRUCTURE:*\n"
                            "`remove <host> <service>` or\n"
                            "`remove <host> <host>` or\n"
                            "`remove <service>`\n",
        "command_handler": "chat_with_user",
        "sub_commands": remove_sub_commands
    },
    {
        "name": "reset",
        "shortcut": "abort",
        "short_description": "abort current action (ack/dt/ena/disa)",
        "long_description": "If you are performing an action and want to abort it, you can use this command\n"
                            "to stop the interaction/conversation with the bot.",
        "command_handler": "reset_conversation"
    },
    {
        "name": "icinga status",
        "shortcut": "is",
        "short_description": "print current Icinga status details",
        "long_description": "This command will print the status of the icinga daemon this bot is connected to.\n"
                            "It displays if core features are enabled like service and host checks "
                            "notifications or event handlers. In a clustered environment it will report "
                            "if all endpoints are connected.",
        "command_handler": "get_icinga_daemon_status"
    },
    {
        "name": "enable",
        "shortcut": "ena",
        "short_description": "enable an action",
        "long_description": "This command will enable active or passive checks, notifications or event handlers"
                            "globally, hosts or services.",
        "command_handler": "enable_disable_action",
        "sub_commands": enable_disable_sub_commands
    },
    {
        "name": "disable",
        "shortcut": "disa",
        "short_description": "disable an action",
        "long_description": "This command will disable active or passive checks, notifications or event handlers"
                            "globally, hosts or services.",
        "command_handler": "enable_disable_action",
        "sub_commands": enable_disable_sub_commands
    }
]


class BotCommands:
    """
    A class used to represent all implemented bot commands and
    will return all properties on each command if requested.

    This will represent the list 'implemented_commands' as
    a class and each command as a attribute.
    """

    class _SingleCommand:
        """
        This subclass meant to hold a single bot command
        and turns a command dict into an object with
        attributes defined in command dict keys
        """
        def __init__(self, dictionary: dict) -> None:
            """Constructor"""
            for key in dictionary:

                # parse sub_commands as own BotCommands
                if key == "sub_commands":
                    setattr(self, key, BotCommands(dictionary[key]))
                else:
                    setattr(self, key, dictionary[key])

        def __repr__(self) -> str:
            return str(self.__dict__)

        def split_message(self, slack_message: str) -> Tuple[Optional[str], Optional[str]]:
            """
            This method will split a Slack message into the command part
            and the rest of the message.

            "host status Web nginx" -> ("host status", "Web nginx")
            "hs" -> ("hs", "")

            Parameters
            ----------
            slack_message : string
                the Slack command which will be parsed

            Returns
            -------
            tuple: response with a tuple of two strings
                ("command parsed", "rest of slack_message")
            """

            command_string_identified = None
            slack_message_without_command = None

            command_starts_with = [self.name]

            if self.shortcut:
                if isinstance(self.shortcut, list):
                    command_starts_with.extend(self.shortcut)
                elif isinstance(self.shortcut, str):
                    command_starts_with.append(self.shortcut)
                else:
                    logging.error("Error parsing \"implemented_commands\". "
                                  "Command (%s) shortcut must be a string or a list" % self.name)

            # iterate over possible command starts and return if match was found
            for command_start in command_starts_with:
                if slack_message.lower() == command_start.lower() or \
                        slack_message.lower().startswith(command_start.lower() + " "):

                    command_string_identified = slack_message[0:len(command_start)]
                    slack_message_without_command = slack_message[len(command_start) + 1:]
                    break

            return command_string_identified, slack_message_without_command

        def strip_command(self, slack_message: str) -> str:
            """
            This method will return the message part of a Slack message
            without the command

            Parameters
            ----------
            slack_message : string
                the Slack command which will be parsed

            Returns
            -------
            str: the message without the command
            """

            _, message = self.split_message(slack_message)
            return message

        def get_command_handler(self) -> Callable:
            """
            This method will return the callable function for
            a bot command, if found.

            Returns
            -------
            Callable: command handler function
            """
            try:
                return globals()[self.command_handler]
            except KeyError:
                logging.error("command_handler function '%s' for command '%s' not found in global scope" %
                              (self.command_handler, self.name))
            except AttributeError:
                logging.error("command_handler for command '%s' not defined in command_definition.py" % self.name)

        def has_sub_commands(self) -> bool:
            """
            This method will return True or False depending
            if command has sub_commands or not.

            Returns
            -------
            Bool: True if sub_commands are defined
            """
            if self.__dict__.get("sub_commands"):
                return True

            return False

    def __init__(self, command_list: list = None) -> None:
        """
        Iterate over the list of dictionaries (implemented_commands)
        and set each command name as attribute with _SingleCommand as value
        """
        if command_list is None:
            command_list = implemented_commands
        for command in command_list:
            setattr(self, command.get("name").replace(" ", "_"), self._SingleCommand(command))

    def get_command_called(self, slack_message: str) -> _SingleCommand:
        """
        return the command object for a slack_message

        Parameters
        ----------
        slack_message : string
            the Slack command which will be parsed

        Returns
        -------
        dict: response with command object if found
        """
        for command in self:
            command_part, _ = command.split_message(slack_message)
            if command_part:
                return command

    def __repr__(self) -> str:
        return str(self.__dict__)

    def __iter__(self) -> _SingleCommand:
        for command in self.__dict__:
            yield getattr(self, command)
