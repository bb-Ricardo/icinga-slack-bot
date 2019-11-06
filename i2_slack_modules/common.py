####
#
# Some commonly used functions
#

import configparser
import logging
from argparse import ArgumentParser, RawDescriptionHelpFormatter
from datetime import datetime

import ctparse


# define valid log levels
valid_log_levels = ["DEBUG", "INFO", "WARNING", "ERROR"]


def parse_command_line(version=None,
                       self_description=None,
                       version_date=None,
                       default_config_file_path=None,
                       ):
    """parse command line arguments

    Also add current version and version date to description
    """

    # define command line options
    description = "%s\nVersion: %s (%s)" % (self_description, version, version_date)

    parser = ArgumentParser(
        description=description,
        formatter_class=RawDescriptionHelpFormatter)

    parser.add_argument("-c", "--config", default=default_config_file_path, dest="config_file",
                        help="points to the config file to read config data from " +
                             "which is not installed under the default path '" +
                             default_config_file_path + "'",
                        metavar="icinga-bot.ini")
    parser.add_argument("-l", "--log_level", choices=valid_log_levels, dest="log_level",
                        help="set log level (overrides config)")
    parser.add_argument("-d", "--daemon",  action='store_true', dest="daemon",
                        help="define if the script is run as a systemd daemon")

    return parser.parse_args()


def parse_own_config(args, default_log_level):
    """parsing and basic validation of own config file

    Parameters
    ----------
    args : ArgumentParser object

    default_log_level: str
        default log level if log level is not set in config

    Returns
    -------
    dict
        a dictionary with all config options parsed from the config file
    """

    config_dict = {}

    config_error = False

    config_file = args.config_file

    logging.debug("Parsing daemon config file: %s" % config_file)

    if config_file is None or config_file == "":
        do_error_exit("Config file not defined.")

    if default_log_level is None or default_log_level == "":
        do_error_exit("Default log level not set.")

    # setup config parser and read config
    config_handler = configparser.ConfigParser(strict=True, allow_no_value=True)

    # noinspection PyBroadException
    try:
        config_handler.read_file(open(config_file))
    except configparser.Error as e:
        do_error_exit("Error during config file parsing: %s" % e)
    # noinspection PyBroadException
    except Exception:
        do_error_exit("Unable to open file '%s'" % config_file)

    # read logging section
    this_section = "main"
    if this_section not in config_handler.sections():
        logging.warning("Section '%s' not found in '%s'" % (this_section, config_file))

    # read logging if present
    config_dict["log_level"] = config_handler.get(this_section, "log_level", fallback=default_log_level)

    # overwrite log level with command line argument
    if args.log_level is not None and args.log_level != "":
        config_dict["log_level"] = args.log_level
        logging.info("Config: overwriting log_level with command line arg: %s" % args.log_level)

    # set log level again
    if args.log_level is not config_dict["log_level"]:
        set_log_level(config_dict["log_level"])

    logging.debug("Config: %s = %s" % ("log_level", config_dict["log_level"]))

    # read common section
    this_section = "slack"
    if this_section not in config_handler.sections():
        do_error_exit("Section '%s' not found in '%s'" % (this_section, config_file))
    else:
        config_dict["slack.bot_token"] = config_handler.get(this_section, "bot_token", fallback="")
        logging.debug("Config: %s = %s***" % ("slack.bot_token", config_dict["slack.bot_token"][0:10]))
        config_dict["slack.default_channel"] = config_handler.get(this_section, "default_channel", fallback="")
        logging.debug("Config: %s = %s" % ("slack.default_channel", config_dict["slack.default_channel"]))

    # read paths section
    this_section = "icinga"
    if this_section not in config_handler.sections():
        do_error_exit("Section '%s' not found in '%s'" % (this_section, config_file))
    else:
        config_dict["icinga.hostname"] = config_handler.get(this_section, "hostname", fallback="")
        logging.debug("Config: %s = %s" % ("icinga.hostname", config_dict["icinga.hostname"]))
        config_dict["icinga.port"] = config_handler.get(this_section, "port", fallback="")
        logging.debug("Config: %s = %s" % ("icinga.port", config_dict["icinga.port"]))
        config_dict["icinga.username"] = config_handler.get(this_section, "username", fallback="")
        logging.debug("Config: %s = %s" % ("icinga.username", config_dict["icinga.username"]))
        config_dict["icinga.password"] = config_handler.get(this_section, "password", fallback="")
        logging.debug("Config: %s = %s***" % ("icinga.password", config_dict["icinga.password"][0:3]))
        config_dict["icinga.web2_url"] = config_handler.get(this_section, "web2_url", fallback="")
        logging.debug("Config: %s = %s" % ("icinga.web2_url", config_dict["icinga.web2_url"]))
        config_dict["icinga.certificate"] = config_handler.get(this_section, "certificate", fallback="")
        logging.debug("Config: %s = %s" % ("icinga.certificate", config_dict["icinga.certificate"]))
        config_dict["icinga.key"] = config_handler.get(this_section, "key", fallback="")
        logging.debug("Config: %s = %s" % ("icinga.key", config_dict["icinga.key"]))
        config_dict["icinga.ca_certificate"] = config_handler.get(this_section, "ca_certificate", fallback="")
        logging.debug("Config: %s = %s" % ("icinga.ca_certificate", config_dict["icinga.ca_certificate"]))
        config_dict["icinga.timeout"] = config_handler.get(this_section, "timeout", fallback="")
        logging.debug("Config: %s = %s" % ("icinga.timeout", config_dict["icinga.timeout"]))
        config_dict["icinga.filter"] = config_handler.get(this_section, "filter", fallback="")
        logging.debug("Config: %s = %s" % ("icinga.filter", config_dict["icinga.filter"]))
        config_dict["icinga.max_returned_results"] = \
            config_handler.get(this_section, "max_returned_results", fallback="")
        logging.debug("Config: %s = %s" % ("icinga.max_returned_results", config_dict["icinga.max_returned_results"]))

    for key, value in config_dict.items():
        if value is "":
            # if we use a certificate then don't care if user or password are defined
            if key in ["icinga.username", "icinga.password"] and config_dict["icinga.certificate"] != "":
                continue
            # these vars can be empty
            if key in ["icinga.key", "icinga.certificate", "icinga.web2_url", "icinga.ca_certificate",
                       "icinga.filter", "icinga.max_returned_results", "icinga.timeout"]:
                continue
            logging.error("Config: option '%s' undefined or empty!" % key)
            config_error = True

    if config_error:
        return False

    return config_dict


def do_error_exit(log_text):
    """log an error and exit with return code 1

    Parameters
    ----------
    log_text : str
        the text to log as error
    """

    logging.error(log_text)
    exit(1)


def set_log_level(log_level=None):
    """set or reset the log level

    Parameters
    ----------
    log_level : str
        Log level to set

    """

    # check set log level against self defined log level array
    if not log_level.upper() in valid_log_levels:
        do_error_exit('Invalid log level: %s' % log_level)

    # check the provided log level and bail out if something is wrong
    numeric_log_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_log_level, int):
        do_error_exit('Invalid log level: %s' % log_level)

    logging.info("Setting log level to: %s" % log_level)

    # unfortunately we have to manipulate the root logger
    if log_level == "DEBUG":
        logging.disable(logging.NOTSET)
    elif log_level == "INFO":
        logging.disable(logging.DEBUG)
    elif log_level == "WARNING":
        logging.disable(logging.INFO)
    elif log_level == "ERROR":
        logging.disable(logging.WARNING)


def setup_logging(args=None, default_log_level=None):
    """Setup logging

    Parameters
    ----------
    args : ArgumentParser object

    default_log_level: str
        default log level if args.log_level is not set

    """

    log_level = args.log_level

    if args.daemon:
        # omit time stamp if run in daemon mode
        logging.basicConfig(level="DEBUG", format='%(levelname)s: %(message)s')
    else:
        logging.basicConfig(level="DEBUG", format='%(asctime)s - %(levelname)s: %(message)s')

    if log_level is None or log_level == "":
        logging.debug("Configuring logging: No log level defined, using default level: %s" % default_log_level)
        log_level = default_log_level

    set_log_level(log_level)


def ts_to_date(ts, date_format="%Y-%m-%d %H:%M:%S"):
    """
    Return a formatted date/time string from a given time stamp

    Parameters
    ----------
    ts : int, float
        time stamp to convert
    date_format : string
        format to convert time stamp to

    Returns
    -------
    str: formatted date/time string
    """
    return datetime.fromtimestamp(ts).strftime(date_format)


def parse_relative_date(data_to_parse=None):
    """
    Return a ctparse.Time dict and a datetime object for a string of relative date and/or time to parse.

    Parameters
    ----------
    data_to_parse : string
        string with relative time information which should be parsed into absolute datetime object

    Returns
    -------
    dict: date/time data + datetime object

        example_output = {
            'mstart': 0,
            'mend': 8,
            'year': 2019,
            'month': 11,
            'day': 5,
            'hour': 17,
            'minute': 33,
            'DOW': None,
            'POD': None,
            'dt': datetime.datetime(2019, 11, 5, 17, 33)
        }
    """

    string_to_parse = None
    if isinstance(data_to_parse, list):
        string_to_parse = " ".join(data_to_parse)

    elif isinstance(data_to_parse, str):
        string_to_parse = data_to_parse

    if string_to_parse is None:
        logging.warning("Trying to parse date but submitted data is not a string or a list.")
        return None

    logging.debug("%s START ctparse %s" % ("*" * 10, "*" * 50))
    parsed_date = ctparse(string_to_parse)
    logging.debug("%s END ctparse %s" % ("*" * 10, "*" * 52))

    if parsed_date is None or parsed_date.resolution is None:
        logging.debug("Unable to parse a date from string: %s" % string_to_parse)
        return None

    data_parts = parsed_date.resolution

    # just do some own additional parsing
    time_string = string_to_parse[data_parts.mstart:data_parts.mend]

    if any(keyword in time_string for keyword in ["lunch", "noon", "mittag"]):
        data_parts.hour = 12

    if "morning" in time_string:
        data_parts.hour = 9

    if "afternoon" in time_string:
        data_parts.hour = 15

    if "evening" in time_string:
        data_parts.hour = 18

    # unable to determine time of the day
    # use current time
    if data_parts.hour is None:
        now = datetime.today()
        data_parts.hour = now.hour
        data_parts.minute = now.minute

    # if minute returned None set to full hour
    if data_parts.minute is None:
        data_parts.minute = 0

    dt = None
    try:
        dt = datetime(year=data_parts.year,
                      month=data_parts.month,
                      day=data_parts.day,
                      hour=data_parts.hour,
                      minute=data_parts.minute)
    except TypeError:
        pass

    if data_parts:
        logging.debug("Parsed date from string (%s): %s" %
                      (string_to_parse[data_parts.mstart:data_parts.mend], parsed_date))
    else:
        logging.debug("Unable to parse a date from string: %s" % string_to_parse)

    return_data = data_parts.__dict__
    return_data["dt"] = dt

    return return_data
