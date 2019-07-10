# icinga-slack-bot
use slack to manage alarms in Icinga2

It can be used to interact with Icinga2 from your Slack client. It uses the
Icinga2 API to get Host/Service status details. Simple status filters can be
used to narrow down the returned status list.


## Requirements
* python >= 3.6
* python-slackclient >= 2.0.0
* certifi >= 2018
* icinga2api >= 0.6.0
* Icinga2 instance with API feature enabled

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

Change config options according your environment. After you entered the Slack tokens you should be able to start the bot.

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

Version: 0.1.0 (2019-07-03)

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
* status overview (so)
>display a summary of current host and service status numbers

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
* To display all host/service status just add the keyword **all** to your command

### Command name filter
You can add host names or services names to any status command.
Also just parts of host and service names can be used to search for objects

***Important:***
* when using the *service status* command only the **first two** names will be used as filter and all others are going to be ignored
* a command like `ss crit test web` will be converted into a filter like:
`
(service.state == 2) && ( match("*test*", host.name) && match("*web*", service.name) ) || ( match("*web*", host.name) && match("*test*", service.name) )
`

### Command examples
* ```hs down test``` will display all hosts in DOWN state which match "test" as host name like "testserver" or "devtest"
* ```hs all``` will return all hosts and their status
* ```hs``` will display all hosts which currently have a problem


* ```ss warn crit ntp``` will display all services which match "ntp" and are in state CRITICAL or WARNING
* ```ss``` will display all services which currently have a problem

***Important:***
* The [detailed](#all-problematic-services) view will only be used if there are **1 to 4** status results

#### Help
![help example](docs/bot_help_answer.png)

#### Detailed host status example
![detailed host answer](docs/bot_detailed_host_answer.png)

#### Detailed service status example
![detailed service answer](docs/bot_detailed_service_answer.png)

#### Service name filter examples
![detailed service answer](docs/bot_host_services_status.png)
![detailed service answer](docs/bot_service_command_example.png)

#### All problematic services
![detailed service answer](docs/bot_service_status.png)

#### Status overview
![status overview answer](docs/bot_status_overview.png)

### Startup messages
* once the bot starts it will report a short status to the configured default channel
![bot started successfully](docs/bot_start_success.png)
![bot had issues starting](docs/bot_start_failure.png)

## Alert notification
To get Slack notifications if something goes wrong you can check out the notification handlers in [contrib](contrib)

### Alert examples
![alert host down](docs/notification_host_down.png)
![alert host up](docs/notification_host_up.png)
![alert service problem](docs/notification_service_problem.png)

## License
>You can check out the full license [here](LICENSE.txt)

This project is licensed under the terms of the **MIT** license.
