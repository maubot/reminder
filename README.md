# reminder
A [maubot](https://github.com/maubot/maubot) to remind you about things.

## Usage
Use `!remind <date> <message>` to set a reminder. To subscribe to a reminder set by someone else,
upvote the message with a 👍 reaction. To cancel a reminder, remove the message or reaction.

Note that subscribing to and cancelling reminders is only possible before the last minute.
Each minute reminders that are scheduled to go off during that minute are sent to the event loop,
at which point their target user list can no longer be updated.

To set the timezone for date parsing and output for your messages, use `!remind tz <timezone>`.
It's recommended to use a [TZ database name](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones),
but anything supported by Pytz will work.

To list your upcoming reminders, use `!remind list`
