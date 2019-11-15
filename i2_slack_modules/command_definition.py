####
#
# define and describe implemented commands
#

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
                            "`ack <service> until <time> <comment>` or\n",
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
                            "`dt <service> from <time> until <time> <comment>` or\n",
        "command_handler": "chat_with_user"
    },
    {
        "name": "reset",
        "shortcut": "abort",
        "short_description": "abort current action (ack/dt)",
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
    }
]
