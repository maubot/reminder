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
from typing import Optional, Iterator, Dict
from datetime import datetime

import pytz
from sqlalchemy import (Column, String, Integer, Text, DateTime, ForeignKey, Table, MetaData,
                        select, and_)
from sqlalchemy.engine.base import Engine

from mautrix.types import UserID, EventID, RoomID

from .util import ReminderInfo


class ReminderDatabase:
    reminder: Table
    reminder_target: Table
    timezone: Table
    tz_cache: Dict[UserID, pytz.timezone]
    db: Engine

    def __init__(self, db: Engine) -> None:
        self.db = db
        self.tz_cache = {}

        meta = MetaData()
        meta.bind = db

        self.reminder = Table("reminder", meta,
                              Column("id", Integer, primary_key=True, autoincrement=True),
                              Column("date", DateTime, nullable=False),
                              Column("room_id", String(255), nullable=False),
                              Column("event_id", String(255), nullable=False),
                              Column("message", Text, nullable=False),
                              Column("reply_to", String(255), nullable=True))
        self.reminder_target = Table("reminder_target", meta,
                                     Column("reminder_id", Integer,
                                            ForeignKey("reminder.id", ondelete="CASCADE"),
                                            primary_key=True),
                                     Column("user_id", String(255), primary_key=True),
                                     Column("event_id", String(255), nullable=False))
        self.timezone = Table("timezone", meta,
                              Column("user_id", String(255), primary_key=True),
                              Column("timezone", String(255), primary_key=True))

        meta.create_all()

    def set_timezone(self, user_id: UserID, tz: pytz.timezone) -> None:
        with self.db.begin() as tx:
            tx.execute(self.timezone.delete().where(self.timezone.c.user_id == user_id))
            tx.execute(self.timezone.insert().values(user_id=user_id, timezone=tz.zone))
        self.tz_cache[user_id] = tz

    def get_timezone(self, user_id: UserID) -> Optional[pytz.timezone]:
        try:
            return self.tz_cache[user_id]
        except KeyError:
            rows = self.db.execute(select([self.timezone.c.timezone])
                                   .where(self.timezone.c.user_id == user_id))
            try:
                self.tz_cache[user_id] = pytz.timezone(next(rows)[0])
            except (pytz.UnknownTimeZoneError, StopIteration, IndexError):
                self.tz_cache[user_id] = pytz.UTC
            return self.tz_cache[user_id]

    def all_for_user(self, user_id: UserID, room_id: Optional[RoomID] = None
                     ) -> Iterator[ReminderInfo]:
        where = [self.reminder.c.id == self.reminder_target.c.reminder_id,
                 self.reminder_target.c.user_id == user_id,
                 self.reminder.c.date > datetime.now(tz=pytz.UTC)]
        if room_id:
            where.append(self.reminder.c.room_id == room_id)
        rows = self.db.execute(select([self.reminder]).where(and_(*where)))
        for row in rows:
            yield ReminderInfo(id=row[0], date=row[1].replace(tzinfo=pytz.UTC), room_id=row[2],
                               event_id=row[3], message=row[4], reply_to=row[5], users=[user_id])

    def get(self, id: int) -> Optional[ReminderInfo]:
        return self._get_one(self.reminder.c.id == id)

    def get_by_event_id(self, event_id: EventID) -> Optional[ReminderInfo]:
        reminder = self._get_one(self.reminder.c.event_id == event_id)
        if reminder:
            return reminder
        rows = self.db.execute(select([self.reminder_target.c.reminder_id])
                               .where(self.reminder_target.c.event_id == event_id))
        try:
            reminder_id = int(next(rows)[0])
            return self.get(reminder_id)
        except (StopIteration, IndexError, ValueError):
            return None

    def _get_one(self, whereclause) -> Optional[ReminderInfo]:
        rows = self.db.execute(select([self.reminder, self.reminder_target.c.user_id,
                                       self.reminder_target.c.event_id]).where(
            and_(whereclause, self.reminder_target.c.reminder_id == self.reminder.c.id)))
        try:
            first_row = next(rows)
        except StopIteration:
            return None
        info = ReminderInfo(id=first_row[0], date=first_row[1].replace(tzinfo=pytz.UTC),
                            room_id=first_row[2], event_id=first_row[3], message=first_row[4],
                            reply_to=first_row[5], users={first_row[6]: first_row[7]})
        for row in rows:
            info.users[row[6]] = row[7]
        return info

    def _get_many(self, whereclause) -> Iterator[ReminderInfo]:
        rows = self.db.execute(select([self.reminder, self.reminder_target.c.user_id,
                                       self.reminder_target.c.event_id])
                               .where(whereclause)
                               .order_by(self.reminder.c.id, self.reminder.c.date))
        building_reminder = None
        for row in rows:
            if building_reminder is not None:
                if building_reminder.id == row[0]:
                    building_reminder.users[row[5]] = row[6]
                    continue
                yield building_reminder
            building_reminder = ReminderInfo(id=row[0], date=row[1].replace(tzinfo=pytz.UTC),
                                             room_id=row[2], event_id=row[3], message=row[4],
                                             reply_to=row[5], users={row[6]: row[7]})
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
                                     event_id=reminder.event_id, message=reminder.message,
                                     reply_to=reminder.reply_to))
            reminder.id = res.inserted_primary_key[0]
            tx.execute(self.reminder_target.insert(),
                       [{"reminder_id": reminder.id, "user_id": user_id,
                         "event_id": event_id}
                        for user_id, event_id in reminder.users.items()])

    def update_room_id(self, old: RoomID, new: RoomID) -> None:
        self.db.execute(self.reminder.update()
                        .where(self.reminder.c.room_id == old)
                        .values(room_id=new))

    def redact_event(self, event_id: EventID) -> None:
        self.db.execute(self.reminder_target.delete()
                        .where(self.reminder_target.c.event_id == event_id))

    def add_user(self, reminder: ReminderInfo, user_id: UserID, event_id: EventID) -> bool:
        if user_id in reminder.users:
            return False
        self.db.execute(self.reminder_target.insert()
                        .values(reminder_id=reminder.id, user_id=user_id, event_id=event_id))
        reminder.users.append(user_id)
        return True

    def remove_user(self, reminder: ReminderInfo, user_id: UserID) -> bool:
        if user_id not in reminder.users:
            return False
        self.db.execute(self.reminder_target.delete().where(
            and_(self.reminder_target.c.reminder_id == reminder.id,
                 self.reminder_target.c.user_id == user_id)))
        reminder.users.remove(user_id)
        return True
