# icinga-slack-bot
use slack to manage alarms in Icinga2

It can be used to interact with Icinga2 from your Slack client. It uses the
Icinga2 API to get Host/Service status details. Simple status filters can be
used to narrow down the returned status list.

## Features

## ToDo
### This release
* ~check icinga connection~
* ~configure default channel to post after bot start~
* ~proper message formatting~
* ~add systemd unit file~
* ~add README.md~
* ~fix logging~
* ~document functions~
* add debug logging
* ~add description~
* ~proper icinga2 error handling~
* ~add all icinga2api connection options (ca, cert, key, timeout)~
* ~add icingaweb2 url to bot responses and error handler~
* circumvent *"[ERROR] block must be less than 3000 characters"*
* add state change time to host and service status messages
* ~add fallback text to slack messages to display push messages~
* ~use attachments to display bot commands~

### Next releases
* acknowledge problems
* add tactical overview (tac) command
* add docker file
* set downtimes
* handle slack connection problems
* add icinga status command
* implement a way to exclude handled problems in default status query
* add limit of max returned results

## Requirements
* python >= 3.6
* Icinga2 with API feature enabled

## Installation

### Setting up icinga-slack-bot
* on RedHat/CentOS you need to install python3.6 and virtualenv from EPEL first
```
yum install python36-virtualenv
```

* setting up the virtual env would be done like this
```virtualenv-3.6 .pyenv``` instead of ```virtualenv .pyenv```

* here we assume we install the bot in ```/opt```
```
cd /opt
git clone https://github.com/bb-Ricardo/icinga-slack-bot.git
cd icinga-slack-bot
virtualenv .pyenv
. .pyenv/bin/activate
pip install -r requirements.txt
```

Now you would be able to start the bot with
```.pyenv/bin/python3 icinga-bot.py```

Most likely the start will fail as the config is not fully set up.
>**It is recommended to create your own config**
>```cp icinga-bot.ini.sample icinga-bot.ini```

Change config options according your environment. Now you should be able to start the bot.

### Run as a service
* a [systemd unit file](icinga-slack-bot.service) is included but needs to be adopted if the installation path is changed

```
sudo cp icinga-slack-bot.service /etc/systemd/system
sudo systemctl daemon-reload
sudo systemctl start icinga-slack-bot
sudo systemctl enable icinga-slack-bot
```

### Icinga API permissions
* necessary API permissions
  * objects/query/Host
  * objects/query/Service
  * status/query

This would be an Icinga Slack bot API user
```
# vim /etc/icinga2/conf.d/api-users.conf

object ApiUser "icinga-bot" {
  password = "icinga"

  permissions = [ "objects/query/Host", "objects/query/Service", "status/query" ]
}
```

For further details check the [Icinga2 API documentation](https://icinga.com/docs/icinga2/latest/doc/12-icinga2-api)

### Get Slack Bot Token
[Here](https://www.fullstackpython.com/blog/build-first-slack-bot-python.html)
you can find a quick and helpful example on how to acquire a slack bot API token

## Configuration
icinga-slack-bot comes with a default [config file](icinga-bot.ini.sample)

## Run the bot
```
usage: icinga-bot.py [-h] [-c icinga-bot.ini] [-l {DEBUG,INFO,WARNING,ERROR}]
                     [-d]

This is an Icinga2 Slack bot.

It can be used to interact with Icinga2 from your Slack client. It uses the
Icinga2 API to get Host/Service status details. Simple status filters can be
used to narrow down the returned status list.

Version: 0.0.1 (2019-05-28)

optional arguments:
  -h, --help            show this help message and exit
  -c icinga-bot.ini, --config icinga-bot.ini
                        points to the config file to read config data from
                        which is not installed under the default path
                        './icinga-bot.ini'
  -l {DEBUG,INFO,WARNING,ERROR}, --log_level {DEBUG,INFO,WARNING,ERROR}
                        set log level (overrides config)
  -d, --daemon          define if the script is run as a systemd daemon
```

## Use the bot
Following commands are currently implemented:
* help
>display the bot help
* ping
>answers simply with pong if slack bot is running
* host status (hs)
>request a host status (or short "hs") of any or all hosts
* service status (ss)
>request a service status (or short "ss") of any or all services

### Command status filter
Following command filters are implemented
* host status
  * up
  * down
  * unreachable (unreach)
  * all
* service status
  * ok
  * warning (warn)
  * critical (crit)
  * unknown
  * all

command filter can be combined like "warn crit" which would return all services in WARNING and CRITICAL state

***Important:***
* The default host status filter will only display hosts which are **NOT** UP
* The default service status filter will only display services which are **NOT** OK

### Command name filter
You can add host names or services names to any status command.
Also just parts of host and service names can be used to search for objects

### Command examples
* ```hs down test``` will display all hosts in DOWN state which match "test" as host name like "testserver" or "devtest"
* ```hs all``` will return all hosts and their status
* ```hs``` will display all hosts which are currently have a problem


* ```ss warn crit ntp``` will display all services which match "ntp" and are in the state CRITICAL or WARNING
* ```ss``` will display all services which are currently have a problem

## Alert Notification
To get Slack notifications if something goes wrong you can check out the notification handlers in [contrib](contrib)

## License
>You can check out the full license [here](LICENSE.txt)

This project is licensed under the terms of the **MIT** license.
