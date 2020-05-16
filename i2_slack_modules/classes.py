####
#
# Define commonly used classes
#

import json
import logging
from datetime import datetime
import i2_slack_modules
from i2_slack_modules.common import my_own_function_name
from slack import WebClient


class BotResponse:
    """
    A class used to represent a Slack Response

    Attributes
    ----------
    text : str
        a string which will be used in "text" attribute of the Slack Post
    blocks : str, list, dict
        holds all the Slack message blocks
    attachments : list, dict, SlackAttachment
        holds all the Slack message attachments

    Methods
    -------
    add_blocks(block)
        add a Slack message block. If 'block' is a string it will be converted into
        a block using method get_single_block()
    add_attachment(attachment)
        adds a new attachment to this response.
    dump_attachments()
        returns this.attachments as json blob
    get_single_block(text)
        return a slack message block
    """

    def __init__(self,
                 text=None,
                 blocks=None,
                 attachments=None):
        self.text = text
        self.blocks = []
        self.attachments = []

        if blocks:
            self.add_block(blocks)

        if attachments:
            self.add_attachment(attachments)

    def add_block(self, block):

        if block is None or len(block) == 0:
            return
        if isinstance(block, dict):
            self.blocks.append(block)
        elif isinstance(block, list):
            self.blocks.extend(block)
        else:
            # noinspection PyTypeChecker
            self.blocks.extend(self.get_single_block(block))

    def add_attachment(self, attachment):

        if attachment is None or len(attachment) == 0:
            return
        if isinstance(attachment, dict):
            self.attachments.append(attachment)
        elif isinstance(attachment, list):
            self.attachments.extend(attachment)
        elif isinstance(attachment, SlackAttachment):
            self.attachments.append(vars(attachment))

    def dump_attachments(self):

        if len(self.attachments) == 0:
            return None

        return json.dumps(self.attachments)

    @staticmethod
    def get_single_block(text):
        """return a slack message block

        Parameters
        ----------
        text : str
            text to add to slack message block
            obeys var slack_max_block_text_length

        Returns
        -------
        dict
            returns a slack message block dictionary
        """

        # limit text to 3000 characters
        if len(text) > i2_slack_modules.slack_max_block_text_length:
            text = "%s..." % text[:(i2_slack_modules.slack_max_block_text_length - 3)]

        return [
            {"type": "section", "text": {"type": "mrkdwn", "text": text}},
        ]


class SlackAttachment:
    """
    A simple placeholder class to manipulate attachments
    """

    def __init__(self):
        pass


class SlackConversation:
    command = None
    filter = None
    filter_result = None
    object_type = None
    start_date = None
    start_date_parsing_failed = None
    end_date = None
    end_date_parsing_failed = None
    description = None
    author = None
    user_id = None
    confirmed = False
    confirmation_sent = False
    canceled = False
    sub_command = None
    filter_used = None

    def __init__(self,
                 user_id=None):
        self.user_id = user_id

    def get_path(self):
        path_list = list()
        if self.command is not None:
            path_list.append(self.command.shortcut)
        if self.sub_command is not None:
            path_list.append(self.sub_command.shortcut)

        if len(path_list) > 0:
            return "`%s:` " % "/".join(path_list)
        else:
            return ""


class SlackUser:

    last_filter = None
    conversation = None
    id = None
    data = dict()
    data_last_updated = 0

    def __init__(self, data: dict = None):

        if data is not None:
            self.data = data

    def reset_conversation(self):
        if self.conversation is not None:
            self.conversation = None

    def start_conversation(self):

        if self.conversation is None:
            self.conversation = SlackConversation()

    def add_last_filter(self, filter_expression):
        self.last_filter = filter_expression

    def get_last_user_filter_if_requested(self, filter_expression):
        if len(filter_expression) == 1 and filter_expression[0] == "!!":
            if self.last_filter is None:
                filter_expression = list()
            else:
                filter_expression = self.last_filter
            logging.debug("Parsed '!!', using slack users previous filter: %s" % filter_expression)
        return filter_expression


class SlackUsers:
    """
    A class used to fetch and hold information about
    the slack user talking to this bot.
    """

    # user_data_cache_timeout defines after how many seconds
    # user date should be fetched again
    user_data_cache_timeout = 1800

    web_handle = None
    user_data = dict()
    users = dict()

    def get(self, user_id: str) -> SlackUser:
        """
        Returns a SlackUser object. Creates a new
        one if none for user_id exists.

        Parameters
        ----------
        user_id: Sl
            user id to return data for

        Returns
        -------
        SlackUser: returns SlackUser object
        """

        # create new user if user could not be found
        if self.users.get(user_id) is None:
            new_user = SlackUser()
            self.users[user_id] = new_user

        return self.users.get(user_id)

    def set_web_handle(self, web_handle: WebClient) -> None:
        """
        Set web handle to use for user data requests

        Parameters
        ----------
        web_handle: WebClient
            slack web handle object which is part of a slack message
        """

        if web_handle is None:
            logging.error("%: web_handle not provided.", my_own_function_name())
            return

        self.web_handle = web_handle

    def is_user_data_expired(self, user_id: str) -> (bool, None):
        """
        Returns True or False depending if seconds passed between
        last fetch of user data and now is greater then
        user_data_cache_timeout

        Parameters
        ----------
        user_id: str
            user id to return data for

        Returns
        -------
        bool, None: True if cache expired otherwise False
        """

        if user_id is None:
            logging.error("%: user_id not provided.", my_own_function_name())
            return

        this_user = self.get(user_id)

        if this_user is not None and \
                this_user.data_last_updated + self.user_data_cache_timeout >= datetime.now().timestamp():
            return False

        logging.debug("User data cache for user '%s' expired." % user_id)

        return True

    async def fetch_slack_user_info(self, user_id: str) -> None:
        """
        Fetch user data for user_id from Slack

        Parameters
        ----------
        user_id: str
            user id to return data for

        """

        if self.web_handle is None:
            logging.error("%: function called before attribute web_handle set.", my_own_function_name())
            return

        if user_id is None:
            logging.error("%: user_id not provided.", my_own_function_name())
            return

        if self.is_user_data_expired(user_id) is False:
            return

        logging.debug("No cached user data found. Fetching from Slack.")

        slack_user_data = await self.web_handle.users_info(user=user_id)

        if slack_user_data is not None and slack_user_data.get("user"):
            logging.debug("Successfully fetched user data.")

            user = self.get(user_id)
            user.data = slack_user_data.get("user")
            user.data_last_updated = datetime.now().timestamp()
        else:
            logging.error("Unable to fetched user data.")

# EOF
