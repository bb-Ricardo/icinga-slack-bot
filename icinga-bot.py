#!/usr/bin/env python3

# This is mostly taken from:
# https://github.com/slackapi/python-slackclient/blob/master/tutorial/02-building-a-message.md

import os
import re
import logging
import asyncio
import ssl as ssl_lib

import certifi
import slack

# use while debugging
import pprint

__version__ = "0.0.1"
__author__ = "Ricardo Bartels <ricardo@bitchbrothers.com>"

SLACK_BOT_TOKEN = os.environ["SLACK_BOT_TOKEN"]

MENTION_REGEX = "^<@(|[WU].+?)>(.*)"


def enum(*sequential, **named):
    enums = dict(zip(sequential, range(len(sequential))), **named)
    reverse = dict((value, key) for key, value in enums.items())
    enums['reverse'] = reverse
    return type('Enum', (), enums)


HOST_STATE = enum("UP", "DOWN", "UNREACHABLE")
SERVICE_STATE = enum("OK", "WARNING", "CRITICAL", "UNKNWON")


async def handle_command(slack_message):
    global icinga2_client
    global HOST_STATE, SERVICE_STATE

    """DESCRIPTION
    """
    
    response_text = None
    default_response_text = "I didn't understand the command. Please use 'help' for more details."
    
    matches = re.search(MENTION_REGEX, slack_message)
    if matches:
        slack_message = matches.group(2).strip()

    if slack_message.startswith("help"):
        response_text = """Following commands are implemented:
        help:                   this help
        service status (ss):    display service status of all services in non OK state
        host status (hs):       display host status of all hosts in non UP state
        """

    elif slack_message.startswith("service status") or slack_message.startswith("ss"):
        response_text = "All services are OK"

    elif slack_message.startswith("host status") or slack_message.startswith("hs"):
        response_text = "All hosts are OK"

    pprint.pprint(slack_message)
    
    return response_text or default_response_text
    

@slack.RTMClient.run_on(event="message")
async def message(**payload):
    """DESCRIPTION
    """
    data = payload["data"]
    web_client = payload["web_client"]

    if data.get("text") != None:
        channel_id = data.get("channel")
        user_id = data.get("user")
        bot_id = data.get("bot_id")

        # don't answer if message was sent by a bot
        if bot_id != None:
            return

        # parse command
        response = await handle_command(data.get("text"))

        web_client.chat_postMessage(
            channel=channel_id,
            text=response
        )

    return

if __name__ == "__main__":
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    logger.addHandler(logging.StreamHandler())

    # set up slack
    slack_ssl_context = ssl_lib.create_default_context(cafile=certifi.where())
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    rtm_client = slack.RTMClient(
        token=SLACK_BOT_TOKEN, ssl=slack_ssl_context, run_async=True, loop=loop
    )
    loop.run_until_complete(rtm_client.start())

# EOF
