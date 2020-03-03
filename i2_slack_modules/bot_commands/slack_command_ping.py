
from i2_slack_modules.classes import BotResponse


# noinspection PyUnusedLocal
def slack_command_ping(*args, **kwargs):
    """
    Just respond with a simple pong

    Parameters
    ----------
    args, kwargs: None
        used to hold additional args which are just ignored

    Returns
    -------
    BotResponse: pong answer
    """
    return BotResponse(
            text="pong :table_tennis_paddle_and_ball:"
    )
