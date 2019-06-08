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
from typing import Optional, List, Tuple, TYPE_CHECKING
from collections import deque
from datetime import datetime
from attr import dataclass

import pytz
import dateparser

from mautrix.types import UserID, RoomID
from mautrix.util.config import BaseProxyConfig, ConfigUpdateHelper
from maubot import MessageEvent
from maubot.handlers.command import Argument

if TYPE_CHECKING:
    from .bot import ReminderBot


class Config(BaseProxyConfig):
    def do_update(self, helper: ConfigUpdateHelper) -> None:
        helper.copy("base_command")


class DateArgument(Argument):
    def __init__(self, name: str, label: str = None, *, required: bool = False):
        super().__init__(name, label=label, required=required, pass_raw=True)

    def match(self, val: str, evt: MessageEvent = None, instance: 'ReminderBot' = None
              ) -> Tuple[str, Optional[datetime]]:
        parser_settings = {
            "PREFER_DATES_FROM": "future",
            "TIMEZONE": "UTC",
            "TO_TIMEZONE": "UTC",
            "RETURN_AS_TIMEZONE_AWARE": True,
        }

        if instance:
            tz = instance.db.get_timezone(evt.sender)
            if tz:
                parser_settings["TIMEZONE"] = tz.zone

        time = None
        parts = [part for part in val.split(" ") if len(part) > 0] + [""]
        rem = deque()
        while not time:
            if len(parts) == 0:
                return val, None
            rem.appendleft(parts.pop())
            time = dateparser.parse(" ".join(parts), settings=parser_settings)
        if time < datetime.now(tz=pytz.UTC) and parts[0] != "in":
            parts.insert(0, "in")
            in_time = dateparser.parse(" ".join(parts), settings=parser_settings)
            if in_time:
                time = in_time
        return " ".join(rem), time


@dataclass
class ReminderInfo:
    id: int = None
    date: datetime = None
    message: str = None
    room_id: RoomID = None
    users: List[UserID] = None
