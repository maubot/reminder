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
from typing import Optional, Dict, List, Union, Tuple, TYPE_CHECKING
from datetime import datetime, timedelta
from attr import dataclass
import re

import pytz
from dateutil.relativedelta import relativedelta

from mautrix.types import UserID, RoomID, EventID
from mautrix.util.config import BaseProxyConfig, ConfigUpdateHelper
from maubot import MessageEvent
from maubot.handlers.command import Argument, ArgumentSyntaxError

from .locales import locales

if TYPE_CHECKING:
    from .bot import ReminderBot


class Config(BaseProxyConfig):
    def do_update(self, helper: ConfigUpdateHelper) -> None:
        helper.copy("default_timezone")
        helper.copy("base_command")


class DateArgument(Argument):
    def __init__(self, name: str, label: str = None, *, required: bool = False):
        super().__init__(name, label=label, required=required, pass_raw=True)

    def match(self, val: str, evt: MessageEvent = None, instance: 'ReminderBot' = None
              ) -> Tuple[str, Optional[datetime]]:
        tz = pytz.UTC
        use_locales = [locales["en_iso"]]
        if instance:
            tz = instance.db.get_timezone(evt.sender, instance.default_timezone)
            locale_ids = instance.db.get_locales(evt.sender)
            use_locales = [locales[id] for id in locale_ids if id in locales]

        for locale in use_locales:
            match = locale.match(val)
            if match:
                date = (datetime.now(tz=tz) + relativedelta(**match.params)).astimezone(pytz.UTC)
                return match.unconsumed, date
        return val, None


def parse_timezone(val: str) -> Optional[pytz.timezone]:
    if not val:
        return None
    try:
        return pytz.timezone(val)
    except pytz.UnknownTimeZoneError as e:
        raise ArgumentSyntaxError(f"{val} is not a valid time zone.", show_usage=False) from e


def pluralize(val: int, unit: str) -> str:
    if val == 1:
        return f"{val} {unit}"
    return f"{val} {unit}s"


def format_time(time: datetime) -> str:
    now = datetime.now(tz=pytz.UTC).replace(microsecond=0)
    if time - now <= timedelta(days=7):
        delta = time - now
        parts = []
        if delta.days > 0:
            parts.append(pluralize(delta.days, "day"))
        hours, seconds = divmod(delta.seconds, 60)
        hours, minutes = divmod(hours, 60)
        if hours > 0:
            parts.append(pluralize(hours, "hour"))
        if minutes > 0:
            parts.append(pluralize(minutes, "minute"))
        if seconds > 0:
            parts.append(pluralize(seconds, "second"))
        if len(parts) == 1:
            return "in " + parts[0]
        return "in " + ", ".join(parts[:-1]) + f" and {parts[-1]}"
    return time.strftime("at %H:%M:%S %Z on %A, %B %-d %Y")


@dataclass
class ReminderInfo:
    id: int = None
    date: datetime = None
    room_id: RoomID = None
    event_id: EventID = None
    message: str = None
    reply_to: EventID = None
    users: Union[Dict[UserID, EventID], List[UserID]] = None
