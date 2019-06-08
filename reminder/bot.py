# reminder - A maubot plugin to remind you about things.
# Copyright (C) 2019 Tulir Asokan
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
from typing import Type
from datetime import datetime, timedelta
from html import escape
import asyncio

import pytz

from mautrix.util.config import BaseProxyConfig
from maubot import Plugin, MessageEvent
from maubot.handlers import command

from .db import ReminderDatabase
from .util import Config, ReminderInfo, DateArgument


class ReminderBot(Plugin):
    db: ReminderDatabase
    reminder_loop_task: asyncio.Future

    @classmethod
    def get_config_class(cls) -> Type[BaseProxyConfig]:
        return Config

    async def start(self) -> None:
        await super().start()
        self.config.load_and_update()
        self.db = ReminderDatabase(self.database)
        self.reminder_loop_task = asyncio.ensure_future(self.reminder_loop(), loop=self.loop)

    async def stop(self) -> None:
        await super().stop()
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
        text = f"{users}: {reminder.message}"
        html = f"{users_html}: {escape(reminder.message)}"
        await self.client.send_text(reminder.room_id, text=text, html=html)

    @command.new(name=lambda self: self.config["base_command"],
                 help="Create a reminder", require_subcommand=False, arg_fallthrough=False)
    @DateArgument("date", required=True)
    @command.argument("message", pass_raw=True, required=True)
    async def remind(self, evt: MessageEvent, date: datetime, message: str) -> None:
        date = date.replace(microsecond=0)
        if date < datetime.now(tz=pytz.UTC):
            await evt.reply(f"Sorry, {date} is in the past and I don't have a time machine :(")
            return
        rem = ReminderInfo(date=date, room_id=evt.room_id, message=message, users=[evt.sender])
        self.db.insert(rem)
        await evt.reply(f"Reminder #{rem.id} will remind you for {rem.message} at {rem.date}.")
        now = datetime.now(tz=pytz.UTC)
        if (date - now).total_seconds() < 60 and now.minute == date.minute:
            self.log.debug(f"Reminder {rem} is in less than a minute, scheduling now...")
            asyncio.ensure_future(self.send_reminder(rem), loop=self.loop)

    @remind.subcommand("list", help="List your reminders")
    async def list(self, evt: MessageEvent) -> None:
        reminders_str = "\n".join(f"* {reminder.message} at {reminder.date}"
                                  for reminder in self.db.all_for_user(evt.sender))
        if len(reminders_str) == 0:
            await evt.reply("You have no upcoming reminders :(")
        else:
            await evt.reply(f"List of reminders:\n\n{reminders_str}")

    @remind.subcommand("cancel", help="Cancel a reminder", aliases=("delete", "remove", "rm"))
    @command.argument("id", parser=lambda val: int(val) if val else None, required=True)
    async def cancel(self, evt: MessageEvent, id: int) -> None:
        reminder = self.db.get(id)
        self.db.remove_user(reminder, evt.sender)
        await evt.reply(f"Reminder #{reminder.id}: {reminder.message} at {reminder.date} cancelled")

    @remind.subcommand("tz", help="Set your timezone", aliases=("timezone"))
    @command.argument("timezone", parser=pytz.timezone, required=True)
    async def timezone(self, evt: MessageEvent, timezone: pytz.timezone) -> None:
        self.db.set_timezone(evt.sender, timezone)
        await evt.reply(f"Set your timezone to {timezone.zone}")
