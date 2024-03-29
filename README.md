# reminder
A [maubot](https://github.com/maubot/maubot) to remind you about things.

## Hosted instances
* maunium.net: [@reminder:maunium.net](https://matrix.to/#/@reminder:maunium.net).
* t2bot.io: https://t2bot.io/reminderbot/

## Usage
Use `!remind <date> <message>` to set a reminder. To subscribe to a reminder set by someone else,
upvote the message with a 👍 reaction. To cancel a reminder, remove the message or reaction.
After the reminder fires, you can re-schedule it with `!reminder again <date>`.

`<date>` can be a time delta (e.g. `2 days 1.5 hours` or `friday at 15:00`)
or an absolute date (e.g. `2020-03-27 15:00`).

Note that subscribing to and cancelling reminders is only possible before the last minute.
Each minute reminders that are scheduled to go off during that minute are sent to the event loop,
at which point their target user list can no longer be updated.

To set the timezone for date parsing and output for your messages, use `!remind tz <timezone>`.
It's recommended to use a [TZ database name](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones),
but anything supported by Pytz will work.

Similarly, you can set the locale for date parsing with `!remind locale <list of locales>`. If you
provide multiple locales, each one will be tried for parsing your input until one matches. Unlike
the timezone, the locale only affects input, not output. You can view available locales using
`!remind locales`. You can also contribute new locales by making a pull request
(see [locales.py](reminder/locales.py), content warning: long regexes).

To list your upcoming reminders, use `!remind list`
