
import json

slack_max_message_text_length = 40000
slack_max_block_text_length = 3000
slack_max_message_blocks = 50
slack_max_message_attachments = 100

plural = lambda x: "s" if x != 1 else ""
yes_no = lambda x: "Yes" if x > 0 else "No"
enabled_disabled = lambda x: "Enabled" if x else "Disabled"


def enum(*sequential, **named):
    """returns an enumerated type"""

    enums = dict(zip(sequential, range(len(sequential))), **named)
    reverse = dict((value, key) for key, value in enums.items())
    enums['reverse'] = reverse
    return type('Enum', (), enums)


# define states which use the enum function
host_states = enum("UP", "DOWN", "UNREACHABLE")
service_states = enum("OK", "WARNING", "CRITICAL", "UNKNOWN")


class SlackResponse:
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
        if len(text) > slack_max_block_text_length:
            text = "%s..." % text[:(slack_max_block_text_length - 3)]

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

    def __init__(self,
                 user_id=None):
        self.user_id = user_id

# EOF
