#!/usr/bin/env bash

SLACK_BOTNAME="icinga2"
DEFAULT_CONFIG="icinga-bot.ini"

DATE=$(which date 2>/dev/null)
CURL=$(which curl 2>/dev/null)
GREP=$(which grep 2>/dev/null)
SED=$(which sed 2>/dev/null)

[[ -z "$DATE" ]] && echo "command 'date' not found." >&2 && exit 1
[[ -z "$CURL" ]] && echo "command 'curl' not found." >&2 && exit 1
[[ -z "$GREP" ]] && echo "command 'grep' not found." >&2 && exit 1
[[ -z "$SED" ]] && echo "command 'sed' not found." >&2 && exit 1

CONFIG_FILE=""
if [[ ! -z "$NOTIFICATION_CONFIG" && -r "$NOTIFICATION_CONFIG" ]]; then
    CONFIG_FILE="$NOTIFICATION_CONFIG"
elif [[ ! -z "$DEFAULT_CONFIG" && -r "$DEFAULT_CONFIG" ]]; then
    CONFIG_FILE="$DEFAULT_CONFIG"
else
    echo "unable to read config file" >&2
    exit 1
fi

SLACK_WEBHOOK_URL=$(${GREP} "\s*webhook_url" "${CONFIG_FILE}" | ${SED} 's/\s*webhook_url\s*=\s*//')
SLACK_DEFAULT_CHANNEL=$(${GREP} "\s*default_channel" "${CONFIG_FILE}" | ${SED} 's/\s*default_channel\s*=\s*//')
ICINGAWEB2_URL=$(${GREP} "\s*web2_url" "${CONFIG_FILE}" | ${SED} 's/\s*web2_url\s*=\s*//')

if [[ ${OBJECTTYPE} == "HOST" ]]; then
    #Set the message icon based on ICINGA Host state
    if [[ "$HOSTSTATE" == "DOWN" ]]; then
        ICON=":bomb:"
        COLOR="danger"
    elif [[ "$HOSTSTATE" == "UP" ]]; then
        ICON=":beer:"
        COLOR="good"
    else
        ICON=":white_medium_square:"
        COLOR="#439FE0"
    fi
    PLUGINOUTPUT=${HOSTOUTPUT//\"/\'}
    FALLBACK_TEXT="${ICON} Host ${HOSTDISPLAYNAME} is ${HOSTSTATE}"
    MESSAGE_TEXT="${ICON} HOST: <${ICINGAWEB2_URL}/monitoring/host/show?host=${HOSTNAME}|${HOSTDISPLAYNAME}>: ${HOSTSTATE}\n\n ${PLUGINOUTPUT}"
else
    #Set the message icon based on ICINGA Service state
    if [[ "$SERVICESTATE" == "CRITICAL" ]];then
        ICON=":bomb:"
        COLOR="danger"
    elif [[ "$SERVICESTATE" == "WARNING" ]]; then
        ICON=":warning:"
        COLOR="warning"
    elif [[ "$SERVICESTATE" == "OK" ]]; then
        ICON=":beer:"
        COLOR="good"
    elif [[ "$SERVICESTATE" == "UNKNOWN" ]]; then
        ICON=":question:"
        COLOR="#E066FF"
    else
        ICON=":white_medium_square:"
        COLOR="#439FE0"
    fi
    PLUGINOUTPUT=${SERVICEOUTPUT//\"/\'}
    FALLBACK_TEXT="${ICON} ${HOSTDISPLAYNAME}:${SERVICEDESC} is ${SERVICESTATE}"
    MESSAGE_TEXT="${ICON} SERVICE: <${ICINGAWEB2_URL}/monitoring/service/show?host=${HOSTNAME}&service=${SERVICEDESC}|${HOSTDISPLAYNAME} : ${SERVICEDISPLAYNAME}>: ${SERVICESTATE}\n\n ${PLUGINOUTPUT}"
fi


TS=$(${DATE} +%s)

#Send message to Slack
PAYLOAD="payload="$(cat <<-END
	{
		"channel": "${SLACK_DEFAULT_CHANNEL}",
		"username": "${SLACK_BOTNAME}",
		"attachments" : [
			{
				"fallback" : "${FALLBACK_TEXT}",
				"color": "${COLOR}",
				"text": "${MESSAGE_TEXT}",
				"ts" : "${TS}"
			}
		]
	}
END
)

${CURL} --connect-timeout 30 --max-time 60 -s -S -X POST --data-urlencode "${PAYLOAD}" "${SLACK_WEBHOOK_URL}"

exit $?
