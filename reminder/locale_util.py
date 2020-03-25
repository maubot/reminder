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
from typing import NamedTuple, Union, Pattern, Dict, Type, Optional, TYPE_CHECKING
from datetime import datetime
from abc import ABC, abstractmethod
import re

from dateutil.relativedelta import MO

WeekdayType = type(MO)

if TYPE_CHECKING:
    from typing import TypedDict


    class RelativeDeltaParams(TypedDict):
        year: int
        month: int
        day: int
        hour: int
        minute: int
        second: int
        microsecond: int

        years: Union[int, float]
        months: Union[int, float]
        weeks: Union[int, float]
        days: Union[int, float]
        hours: Union[int, float]
        minutes: Union[int, float]
        seconds: Union[int, float]
        microseconds: Union[int, float]

        weekday: Union[int, WeekdayType]

        leapdays: int
        yearday: int
        nlyearday: int


class MatcherReturn(NamedTuple):
    params: 'RelativeDeltaParams'
    end: int


class Matcher(ABC):
    @abstractmethod
    def match(self, val: str, start: int = 0) -> Optional[MatcherReturn]:
        pass


class RegexMatcher(Matcher):
    regex: Pattern
    value_type: Type

    def __init__(self, pattern: str, value_type: Type = int) -> None:
        self.regex = re.compile(pattern, re.IGNORECASE)
        self.value_type = value_type

    def match(self, val: str, start: int = 0) -> Optional[MatcherReturn]:
        match = self.regex.match(val, pos=start)
        if match and match.end() > 0:
            return MatcherReturn(params={key: self.value_type(value)
                                         for key, value in match.groupdict().items() if value},
                                 end=match.end())
        return None


class WeekdayMatcher(Matcher):
    regex: Pattern
    map: Dict[str, Union[int, WeekdayType]]
    substr: int

    def __init__(self, pattern: str, map: Dict[str, Union[int, WeekdayType]], substr: int) -> None:
        self.regex = re.compile(pattern, re.IGNORECASE)
        self.map = map
        self.substr = substr

    def match(self, val: str, start: int = 0) -> Optional[MatcherReturn]:
        match = self.regex.match(val, pos=start)
        if match and match.end() > 0:
            weekday = self.map[match.string[:self.substr].lower()]
            if isinstance(weekday, int):
                weekday = (datetime.now().weekday() + weekday) % 7
            return MatcherReturn(params={"weekday": weekday}, end=match.end())
        return None


class Locale(Matcher):
    name: str
    timedelta: Matcher
    date: Matcher
    weekday: Matcher
    time: Matcher

    def __init__(self, name: str, timedelta: Matcher, date: Matcher, weekday: Matcher,
                 time: Matcher) -> None:
        self.name = name
        self.timedelta = timedelta
        self.date = date
        self.weekday = weekday
        self.time = time

    def replace(self, name: str, timedelta: Matcher = None, date: Matcher = None,
                weekday: Matcher = None, time: Matcher = None) -> 'Locale':
        return Locale(name=name, timedelta=timedelta or self.timedelta, date=date or self.date,
                      weekday=weekday or self.weekday, time=time or self.time)

    def match(self, val: str, start: int = 0) -> Optional[MatcherReturn]:
        end = start
        found_delta = self.timedelta.match(val, start=end)
        if found_delta:
            params, end = found_delta
        else:
            params = {}
            found_day = self.weekday.match(val, start=end)
            if found_day:
                params, end = found_day
            else:
                found_date = self.date.match(val, start=end)
                if found_date:
                    params, end = found_date

            found_time = self.time.match(val, start=end)
            if found_time:
                params = {**params, **found_time.params}
                end = found_time.end
        return MatcherReturn(params, end) if len(params) > 0 else None


Locales = Dict[str, Locale]
