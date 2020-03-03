
from i2_slack_modules.slack_helper import *
from i2_slack_modules.icinga_connection import get_i2_status


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
