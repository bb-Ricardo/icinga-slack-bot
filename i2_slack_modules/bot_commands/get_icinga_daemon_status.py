
from i2_slack_modules import enabled_disabled
from i2_slack_modules.common import ts_to_date
from i2_slack_modules.slack_helper import BotResponse
from i2_slack_modules.icinga_connection import get_i2_status


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
