
from i2_slack_modules.classes import BotResponse


# noinspection PyUnusedLocal
def reset_conversation(slack_user=None, *args, **kwargs):
    """
    reset a conversation

    Parameters
    ----------
    slack_user : SlackUser
        SlackUser object
    args, kwargs: None
        used to hold additional args which are just ignored

    Returns
    -------
    BotResponse: response if action was successful
    """

    if slack_user is not None:
        slack_user.reset_conversation()
        return BotResponse(text="Your conversation has been reset.")

    return None
