# reminder - A maubot plugin to remind you about things.
# Copyright (C) 2020 Tulir Asokan
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
from typing import Type, Tuple, List
from datetime import datetime, timedelta
from html import escape
import asyncio

import pytz

from mautrix.types import (EventType, RedactionEvent, StateEvent, Format, MessageType,
                           TextMessageEventContent, ReactionEvent, UserID)
from mautrix.util.config import BaseProxyConfig
from maubot import Plugin, MessageEvent
from maubot.handlers import command, event

from .db import ReminderDatabase
from .util import Config, ReminderInfo, DateArgument, parse_timezone, format_time
from .locales import locales


class ReminderBot(Plugin):
    db: ReminderDatabase
    reminder_loop_task: asyncio.Future
    base_command: str
    base_aliases: Tuple[str, ...]
    default_timezone: pytz.timezone

    @classmethod
    def get_config_class(cls) -> Type[BaseProxyConfig]:
        return Config

    async def start(self) -> None:
        self.on_external_config_update()
        self.db = ReminderDatabase(self.database)
        self.reminder_loop_task = asyncio.ensure_future(self.reminder_loop(), loop=self.loop)

    def on_external_config_update(self) -> None:
        self.config.load_and_update()
        bc = self.config["base_command"]
        self.base_command = bc[0] if isinstance(bc, list) else bc
        self.base_aliases = tuple(bc) if isinstance(bc, list) else (bc,)
        raw_timezone = self.config["default_timezone"]
        try:
            self.default_timezone = pytz.timezone(raw_timezone)
        except pytz.UnknownTimeZoneError:
            self.log.warning(f"Unknown default timezone {raw_timezone}")
            self.default_timezone = pytz.UTC

    async def stop(self) -> None:
        self.reminder_loop_task.cancel()

    async def reminder_loop(self) -> None:
        try:
            self.log.debug("Reminder loop started")
            while True:
                now = datetime.now(tz=pytz.UTC)
                next_minute = (now + timedelta(minutes=1)).replace(second=0, microsecond=0)
                await asyncio.sleep((next_minute - now).total_seconds())
                await self.schedule_nearby_reminders(next_minute)
        except asyncio.CancelledError:
            self.log.debug("Reminder loop stopped")
        except Exception:
            self.log.exception("Exception in reminder loop")

    async def schedule_nearby_reminders(self, now: datetime) -> None:
        until = now + timedelta(minutes=1)
        for reminder in self.db.all_in_range(now, until):
            asyncio.ensure_future(self.send_reminder(reminder), loop=self.loop)

    async def send_reminder(self, reminder: ReminderInfo) -> None:
        try:
            await self._send_reminder(reminder)
        except Exception:
            self.log.exception("Failed to send reminder")

    async def _send_reminder(self, reminder: ReminderInfo) -> None:
        if len(reminder.users) == 0:
            self.log.debug(f"Cancelling reminder {reminder}, no users left to remind")
            return
        wait = (reminder.date - datetime.now(tz=pytz.UTC)).total_seconds()
        if wait > 0:
            self.log.debug(f"Waiting {wait} seconds to send {reminder}")
            await asyncio.sleep(wait)
        else:
            self.log.debug(f"Sending {reminder} immediately")
        users = " ".join(reminder.users)
        users_html = " ".join(f"<a href='https://matrix.to/#/{user_id}'>{user_id}</a>"
                              for user_id in reminder.users)
        content = TextMessageEventContent(
            msgtype=MessageType.TEXT, body=f"{users}: {reminder.message}", format=Format.HTML,
            formatted_body=f"{users_html}: {escape(reminder.message)}")
        content["xyz.maubot.reminder"] = {
            "id": reminder.id,
            "message": reminder.message,
            "targets": list(reminder.users),
            "reply_to": reminder.reply_to,
        }
        if reminder.reply_to:
            content.set_reply(await self.client.get_event(reminder.room_id, reminder.reply_to))
        await self.client.send_message(reminder.room_id, content)

    @command.new(name=lambda self: self.base_command,
                 aliases=lambda self, alias: alias in self.base_aliases,
                 help="Create a reminder", require_subcommand=False, arg_fallthrough=False)
    @DateArgument("date", required=True)
    @command.argument("message", pass_raw=True, required=False)
    async def remind(self, evt: MessageEvent, date: datetime, message: str) -> None:
        date = date.replace(microsecond=0)
        now = datetime.now(tz=pytz.UTC).replace(microsecond=0)
        if date < now:
            await evt.reply(f"Sorry, {date} is in the past and I don't have a time machine :(")
            return
        rem = ReminderInfo(date=date, room_id=evt.room_id, message=message,
                           reply_to=evt.content.get_reply_to(), users={evt.sender: evt.event_id})
        await self._remind(evt, rem, now)

    @remind.subcommand("reschedule", help="Reschedule a reminder you got", aliases=("again",))
    @DateArgument("date", required=True)
    async def reschedule(self, evt: MessageEvent, date: datetime) -> None:
        reply_to_id = evt.content.get_reply_to()
        if not reply_to_id:
            await evt.reply("You must reply to a reminder event to reschedule it.")
            return
        date = date.replace(microsecond=0)
        now = datetime.now(tz=pytz.UTC).replace(microsecond=0)
        if date < now:
            await evt.reply(f"Sorry, {date} is in the past and I don't have a time machine :(")
            return
        reply_to = await self.client.get_event(evt.room_id, reply_to_id)
        try:
            reminder_info = reply_to.content["xyz.maubot.reminder"]
            rem = ReminderInfo(date=date, room_id=evt.room_id, message=reminder_info["message"],
                               reply_to=reminder_info["reply_to"], users={evt.sender: evt.event_id})
        except KeyError:
            await evt.reply("That doesn't look like a valid reminder event.")
            return
        await self._remind(evt, rem, now, again=True)

    async def _remind(self, evt: MessageEvent, rem: ReminderInfo, now: datetime, again: bool = False
                      ) -> None:
        if rem.date == now:
            await self.send_reminder(rem)
            return
        remind_type = "remind you "
        if rem.reply_to:
            evt_link = f"[event](https://matrix.to/#/{rem.room_id}/{rem.reply_to})"
            if rem.message:
                remind_type += f"to {rem.message} (replying to that {evt_link})"
            else:
                remind_type += f"about that {evt_link}"
        elif rem.message:
            remind_type += f"to {rem.message}"
        else:
            remind_type = "ping you"
            rem.message = "ping"
        if again:
            remind_type += " again"
        msg = (f"I'll {remind_type} {self.format_time(evt.sender, rem)}.\n\n"
               f"(others can \U0001F44D this message to get pinged too)")
        rem.event_id = await evt.reply(msg)
        self.db.insert(rem)
        now = datetime.now(tz=pytz.UTC)
        if (rem.date - now).total_seconds() < 60 and now.minute == rem.date.minute:
            self.log.debug(f"Reminder {rem} is in less than a minute, scheduling now...")
            asyncio.ensure_future(self.send_reminder(rem), loop=self.loop)

    @remind.subcommand("help", help="Usage instructions")
    async def help(self, evt: MessageEvent) -> None:
        await evt.reply(f"Maubot [Reminder](https://github.com/maubot/reminder) plugin.\n\n"
                        f"* !{self.base_command} <date> <message> - Add a reminder\n"
                        f"* !{self.base_command} again <date> - Reply to a reminder to reschedule it\n"
                        f"* !{self.base_command} list - Get a list of your reminders\n"
                        f"* !{self.base_command} tz <timezone> - Set your time zone\n"
                        f"* !{self.base_command} locale <locale> - Set your locale\n"
                        f"* !{self.base_command} locales - List available locales\n\n"
                        "<date> can be a time delta (e.g. `2 days 1.5 hours` or `friday at 15:00`) "
                        "or an absolute date (e.g. `2020-03-27 15:00`)\n\n"
                        "To get mentioned by a reminder added by someone else, upvote the message "
                        "by reacting with \U0001F44D.\n\n"
                        "To cancel a reminder, remove the message or reaction.")

    @remind.subcommand("list", help="List your reminders")
    @command.argument("all", required=False)
    async def list(self, evt: MessageEvent, all: str) -> None:
        room_id = evt.room_id
        if "all" in all:
            room_id = None

        def format_rem(rem: ReminderInfo) -> str:
            if rem.reply_to:
                evt_link = f"[event](https://matrix.to/#/{rem.room_id}/{rem.reply_to})"
                if rem.message:
                    return f'"{rem.message}" (replying to {evt_link})'
                else:
                    return evt_link
            else:
                return f'"{rem.message}"'

        reminders_str = "\n".join(f"* {format_rem(reminder)} {self.format_time(evt.sender, reminder)}"
                                  for reminder in self.db.all_for_user(evt.sender, room_id=room_id))
        message = "upcoming reminders"
        if room_id:
            message += " in this room"
        if len(reminders_str) == 0:
            await evt.reply(f"You have no {message} :(")
        else:
            await evt.reply(f"Your {message}:\n\n{reminders_str}")

    def format_time(self, sender: UserID, reminder: ReminderInfo) -> str:
        return format_time(reminder.date.astimezone(self.db.get_timezone(sender)))

    @remind.subcommand("locales", help="List available locales")
    async def locales(self, evt: MessageEvent) -> None:
        def _format_key(key: str) -> str:
            language, country = key.split("_")
            return f"{language.lower()}_{country.upper()}"

        await evt.reply("Available locales:\n\n" +
                        "\n".join(f"* `{_format_key(key)}` - {locale.name}"
                                  for key, locale in locales.items()))

    @staticmethod
    def _fmt_locales(locale_ids: List[str]) -> str:
        locale_names = [locales[id].name for id in locale_ids]
        if len(locale_names) == 0:
            return "unset"
        elif len(locale_names) == 1:
            return locale_names[0]
        else:
            return ", ".join(locale_names[:-1]) + " and " + locale_names[-1]

    @remind.subcommand("locale", help="Set your locale")
    @command.argument("locale", required=False, pass_raw=True)
    async def locale(self, evt: MessageEvent, locale: str) -> None:
        if not locale:
            await evt.reply(f"Your locale is {self._fmt_locales(self.db.get_locales(evt.sender))}")
            return
        locale_ids = [part.strip() for part in locale.lower().split(" ")]
        for locale_id in locale_ids:
            if locale_id not in locales:
                await evt.reply(f"Locale `{locale_id}` is not supported")
                return
        self.db.set_locales(evt.sender, locale_ids)
        await evt.reply(f"Set your locale to {self._fmt_locales(locale_ids)}")

    @remind.subcommand("timezone", help="Set your timezone", aliases=("tz",))
    @command.argument("timezone", parser=parse_timezone, required=False)
    async def timezone(self, evt: MessageEvent, timezone: pytz.timezone) -> None:
        if not timezone:
            await evt.reply(f"Your time zone is {self.db.get_timezone(evt.sender).zone}")
            return
        self.db.set_timezone(evt.sender, timezone)
        await evt.reply(f"Set your timezone to {timezone.zone}")

    @command.passive(regex=r"(?:\U0001F44D[\U0001F3FB-\U0001F3FF]?)",
                     field=lambda evt: evt.content.relates_to.key,
                     event_type=EventType.REACTION, msgtypes=None)
    async def subscribe_react(self, evt: ReactionEvent, _: Tuple[str]) -> None:
        reminder = self.db.get_by_event_id(evt.content.relates_to.event_id)
        if reminder:
            self.db.add_user(reminder, evt.sender, evt.event_id)

    @event.on(EventType.ROOM_REDACTION)
    async def redact(self, evt: RedactionEvent) -> None:
        self.db.redact_event(evt.redacts)

    @event.on(EventType.ROOM_TOMBSTONE)
    async def tombstone(self, evt: StateEvent) -> None:
        if not evt.content.replacement_room:
            return
        self.db.update_room_id(evt.room_id, evt.content.replacement_room)
