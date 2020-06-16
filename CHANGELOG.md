# Changelog

[1.0.0](https://github.com/bb-Ricardo/icinga-slack-bot/tree/v1.0.0) (2020-05-17) *The Baby learned to walk*

I took quite some time but here it is: The first major release 🎉

This release adds most of the Icinga2 API actions which can be performed on objects.
Also handling comments, downtimes and acknowledgements are now fully supported.

**Features:**
* Reschedule host or service [#26](https://github.com/bb-Ricardo/icinga-slack-bot/issues/26)
* Implement enable/disable command to modify application features [#24](https://github.com/bb-Ricardo/icinga-slack-bot/issues/24)
* Add/display comments, acknowledgements and downtimes to host and service status results [#25](https://github.com/bb-Ricardo/icinga-slack-bot/issues/25)
* Add ability to remove acknowledgements/downtimes/comments [#29](https://github.com/bb-Ricardo/icinga-slack-bot/issues/29)
* Add command to display services/hosts which are ack/dt/com [#38](https://github.com/bb-Ricardo/icinga-slack-bot/issues/38)
* Allow to use previous command options with special option „!!“ [#37](https://github.com/bb-Ricardo/icinga-slack-bot/issues/37)
* Add action to delay notifications [#33](https://github.com/bb-Ricardo/icinga-slack-bot/issues/33)
* Add comments and downtime details to object details view [#31](https://github.com/bb-Ricardo/icinga-slack-bot/issues/31)
* Add “💬” to host and service title if these objects have comments [#30](https://github.com/bb-Ricardo/icinga-slack-bot/issues/30)
* Add „(handled)“ to host/service links [#28](https://github.com/bb-Ricardo/icinga-slack-bot/issues/28)
* Add command to send custom notification [#27](https://github.com/bb-Ricardo/icinga-slack-bot/issues/27)
* Query user details delayed [#23](https://github.com/bb-Ricardo/icinga-slack-bot/issues/23)
* Parse filters with quotes differently to allow for explicit names [#18](https://github.com/bb-Ricardo/icinga-slack-bot/issues/18)
* Tell user on error which command the user is using [#40](https://github.com/bb-Ricardo/icinga-slack-bot/issues/40)

**Bug fixes:**
* Take care of pending services without check result [#39](https://github.com/bb-Ricardo/icinga-slack-bot/issues/39)

**Documentation**
* Add description of slack bot creation to README [#35](https://github.com/bb-Ricardo/icinga-slack-bot/issues/35)

**Internal:**
* Refactor internal command parsing and create class with command methods [#19](https://github.com/bb-Ricardo/icinga-slack-bot/issues/19)

**Dependencies**
* Move to icinga2apic as dependency [#32](https://github.com/bb-Ricardo/icinga-slack-bot/issues/32)


[0.2.0](https://github.com/bb-Ricardo/icinga-slack-bot/tree/0.2.0) (2019-11-16) *Actions Arrived*

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


[0.1.0](https://github.com/bb-Ricardo/icinga-slack-bot/tree/0.1.0) (2019-07-03) *Initial Release*

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
