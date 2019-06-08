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
from typing import Optional, Iterator, Dict
from datetime import datetime

import pytz
from sqlalchemy import (Column, String, Integer, Text, DateTime, ForeignKey, Table, MetaData,
                        select, and_)
from sqlalchemy.engine.base import Engine

from mautrix.types import UserID

from .util import ReminderInfo


class ReminderDatabase:
    reminder: Table
    reminder_target: Table
    timezone: Table
    tz_cache: Dict[UserID, pytz.timezone]
    db: Engine

    def __init__(self, db: Engine) -> None:
        self.db = db

        meta = MetaData()
        meta.bind = db

        self.reminder = Table("reminder", meta,
                              Column("id", Integer, primary_key=True, autoincrement=True),
                              Column("date", DateTime, nullable=False),
                              Column("room_id", String(255), nullable=False),
                              Column("message", Text, nullable=False))
        self.reminder_target = Table("reminder_target", meta,
                                     Column("reminder_id", Integer,
                                            ForeignKey("reminder.id", ondelete="CASCADE"),
                                            primary_key=True),
                                     Column("user_id", String(255), primary_key=True))
        self.timezone = Table("timezone", meta,
                              Column("user_id", String(255), primary_key=True),
                              Column("timezone", String(255), primary_key=True))

        meta.create_all()

    def set_timezone(self, user_id: UserID, tz: pytz.timezone) -> None:
        self.db.execute(self.timezone.insert().values(user_id=user_id, timezone=tz.zone))
        self.tz_cache[user_id] = tz

    def get_timezone(self, user_id: UserID) -> Optional[pytz.timezone]:
        try:
            return self.tz_cache[user_id]
        except KeyError:
            rows = self.db.execute(self.timezone.select().where(self.timezone.c.user_id == user_id))
            try:
                self.tz_cache[user_id] = pytz.timezone(next(rows)[0])
            except (pytz.UnknownTimeZoneError, StopIteration, IndexError):
                self.tz_cache[user_id] = None
            return self.tz_cache[user_id]

    def all_for_user(self, user_id: UserID) -> Iterator[ReminderInfo]:
        rows = self.db.execute(select([self.reminder]).where(
            and_(self.reminder.c.id == self.reminder_target.c.reminder_id,
                 self.reminder_target.c.user_id == user_id,
                 self.reminder.c.date > datetime.now(tz=pytz.UTC))))
        for row in rows:
            yield ReminderInfo(id=row[0], date=row[1].replace(tzinfo=pytz.UTC), room_id=row[2],
                               message=row[3], users=[user_id])

    def get(self, id: int) -> Optional[ReminderInfo]:
        rows = self.db.execute(select([self.reminder, self.reminder_target.c.user_id]).where(
            and_(self.reminder.c.id == id,
                 self.reminder_target.c.reminder_id == self.reminder.c.id)))
        try:
            first_row = next(rows)
        except StopIteration:
            return None
        info = ReminderInfo(id=first_row[0], date=first_row[1].replace(tzinfo=pytz.UTC),
                            room_id=first_row[2], message=first_row[3], users=[first_row[4]])
        for row in rows:
            info.users.append(row[4])
        return info

    def _get_many(self, whereclause) -> Iterator[ReminderInfo]:
        rows = self.db.execute(select([self.reminder, self.reminder_target.c.user_id])
                               .where(whereclause)
                               .order_by(self.reminder.c.id, self.reminder.c.date))
        building_reminder = None
        for row in rows:
            if building_reminder is not None:
                if building_reminder.id == row[0]:
                    building_reminder.users.append(row[4])
                    continue
                yield building_reminder
            building_reminder = ReminderInfo(id=row[0], date=row[1].replace(tzinfo=pytz.UTC),
                                             room_id=row[2], message=row[3], users=[row[4]])
        if building_reminder is not None:
            yield building_reminder

    def all(self) -> Iterator[ReminderInfo]:
        yield from self._get_many(self.reminder_target.c.reminder_id == self.reminder.c.id)

    def all_in_range(self, after: datetime, before: datetime) -> Iterator[ReminderInfo]:
        yield from self._get_many(and_(self.reminder_target.c.reminder_id == self.reminder.c.id,
                                       after <= self.reminder.c.date,
                                       self.reminder.c.date < before))

    def insert(self, reminder: ReminderInfo) -> None:
        with self.db.begin() as tx:
            res = tx.execute(self.reminder.insert()
                             .values(date=reminder.date, room_id=reminder.room_id,
                                     message=reminder.message))
            reminder.id = res.inserted_primary_key[0]
            print([{"reminder_id": reminder.id, "user_id": user_id}
                   for user_id in reminder.users])
            tx.execute(self.reminder_target.insert(),
                       [{"reminder_id": reminder.id, "user_id": user_id}
                        for user_id in reminder.users])

    def add_user(self, reminder: ReminderInfo, user_id: UserID) -> None:
        if user_id in reminder.users:
            return
        self.db.execute(self.reminder_target.insert()
                        .values(reminder_id=reminder.id, user_id=user_id))
        reminder.users.append(user_id)

    def remove_user(self, reminder: ReminderInfo, user_id: UserID) -> None:
        if user_id not in reminder.users:
            return
        self.db.execute(self.reminder_target.delete().where(
            and_(self.reminder_target.c.reminder_id == reminder.id,
                 self.reminder_target.c.user_id == user_id)))
        reminder.users.remove(user_id)
