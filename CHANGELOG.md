# Changelog

[0.2.0](https://github.com/https://github.com/bb-Ricardo/icinga-slack-bot/tree/0.2.0) (2019-11-16) *Actions Arrived*

**Features:**
* Added action to acknowledge problematic hosts/services [#1](https://github.com/bb-Ricardo/icinga-slack-bot/issues/1)
* Added action to set a downtime for hosts/services [#4](https://github.com/bb-Ricardo/icinga-slack-bot/issues/4)
* Added a status overview command [#2](https://github.com/bb-Ricardo/icinga-slack-bot/issues/2)
* Added Dockerfile [#3](https://github.com/bb-Ricardo/icinga-slack-bot/issues/3)
* Added Icinga status command [#5](https://github.com/bb-Ricardo/icinga-slack-bot/issues/5)
* Added config option to limit max returned results [#7](https://github.com/bb-Ricardo/icinga-slack-bot/issues/7)
* Handled hosts/services are not displayed any longer with default host/service status command [#6](https://github.com/bb-Ricardo/icinga-slack-bot/issues/6)
* Added filter option to config file to limit results to single hosts or host groups [#8](https://github.com/bb-Ricardo/icinga-slack-bot/issues/8)
* Added a more detailed help, help can be called for each command [#9](https://github.com/bb-Ricardo/icinga-slack-bot/issues/9)

**Bug fixes:**
* host state not reporting hosts in NOT UP state while running default query [#15](https://github.com/bb-Ricardo/icinga-slack-bot/issues/15)

**Internal:**
* Splitted code into modules [#12](https://github.com/bb-Ricardo/icinga-slack-bot/issues/12)


[0.1.0](https://github.com/https://github.com/bb-Ricardo/icinga-slack-bot/tree/0.1.0) (2019-07-03) *Initial Release*

**Road to Initial Release**
* check icinga connection
* configure default channel to post after bot start
* proper message formatting
* add systemd unit file
* add README.md
* fix logging
* document functions
* add debug logging
* add description
* proper icinga2 error handling
* add all icinga2api connection options (ca, cert, key, timeout)
* add icingaweb2 url to bot responses and error handler
* circumvent *"[ERROR] block must be less than 3000 characters"*
* add state change time to host and service status messages (detailed view)
* add fallback text to slack messages to display push messages
* use attachments to display bot commands
