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
from dateutil.relativedelta import MO, TU, WE, TH, FR, SA, SU

from .locale_util import (Locales, Locale, RegexMatcher,
                          WeekdayMatcher, TimeMatcher, ShortYearMatcher)

locales: Locales = {}

td_sep_en = r"(?:[\s,]{1,3}(?:and\s)?)"
locales["en_iso"] = Locale(
    name="English (ISO)",
    timedelta=RegexMatcher(r"(?:(?:in|after)\s)?"
                           rf"(?:(?P<years>[-+]?\d+)\s?y(?:r|ears?)?{td_sep_en})?"
                           rf"(?:(?P<months>[-+]?\d+)\s?mo(?:nths?)?{td_sep_en})?"
                           rf"(?:(?P<weeks>[-+]?\d+)\s?w(?:k|eeks?)?{td_sep_en})?"
                           rf"(?:(?P<days>[-+]?\d+)\s?d(?:ays?)?{td_sep_en})?"
                           rf"(?:(?P<hours>[-+]?\d+)\s?h(?:(?:r|our)?s?){td_sep_en})?"
                           rf"(?:(?P<minutes>[-+]?\d+)\s?m(?:in(?:ute)?s?)?{td_sep_en})?"
                           r"(?:(?P<seconds>[-+]?\d+)\s?s(?:ec(?:ond)?s?)?)?"
                           r"(?:\s|$)"),
    date=RegexMatcher(r"(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})\s"),
    weekday=WeekdayMatcher(pattern=r"(?:today"
                                   r"|tomorrow"
                                   r"|mon(?:day)?"
                                   r"|tues?(?:day)?"
                                   r"|wed(?:nesday)?"
                                   r"|thu(?:rs(?:day)?)?"
                                   r"|fri(?:day)?"
                                   r"|sat(?:urday)?"
                                   r"|sun(?:day)?)"
                                   r"(?:\s|$)",
                           map={
                               "tod": +0, "tom": +1, "mon": MO, "tue": TU, "wed": WE, "thu": TH,
                               "fri": FR, "sat": SA, "sun": SU,
                           }, substr=3),
    time=RegexMatcher(r"\s?(?:at\s)?"
                      r"(?P<hour>\d{2})"
                      r"[:.](?P<minute>\d{2})"
                      r"(?:[:.](?P<second>\d{2}))?"
                      r"(?:\s|$)"),
)

time_12_en = TimeMatcher(r"\s?(?:at\s)?"
                         r"(?P<hour>\d{2})"
                         r"(?:[:.](?P<minute>\d{2}))?"
                         r"(?:[:.](?P<second>\d{2}))?"
                         r"(?:\s(?P<meridiem>a\.?m|p\.?m)\.?)?"
                         r"(?:\s|$)")

locales["en_us"] = locales["en_iso"].replace(
    name="English (US)", time=time_12_en, date=ShortYearMatcher(
        r"(?P<month>\d{1,2})/(?P<day>\d{1,2})(?:/(?P<year>\d{2}(?:\d{2})?))?(?:\s|$)"))

locales["en_uk"] = locales["en_iso"].replace(
    name="English (UK)", time=time_12_en, date=ShortYearMatcher(
        r"(?P<day>\d{1,2})/(?P<month>\d{1,2})(?:/(?P<year>\d{2}(?:\d{2})?))?(?:\s|$)"))

td_sep_fi = r"(?:[\s,]{1,3}(?:ja\s)?)"
locales["fi_fi"] = Locale(
    name="Finnish",
    timedelta=RegexMatcher(rf"(?:(?P<years>[-+]?\d+)\s?v(?:uo(?:tta|den))?{td_sep_fi})?"
                           rf"(?:(?P<months>[-+]?\d+)\s?k(?:k|uukau(?:si|tta|den))?{td_sep_fi})?"
                           rf"(?:(?P<weeks>[-+]?\d+)\s?v(?:k|iikk?o[an]?){td_sep_fi})?"
                           rf"(?:(?P<days>[-+]?\d+)\s?p(?:v|äivä[än]?){td_sep_fi})?"
                           rf"(?:(?P<hours>[-+]?\d+)\s?t(?:un(?:nin?|tia))?{td_sep_fi})?"
                           rf"(?:(?P<minutes>[-+]?\d+)\s?m(?:in(?:uut(?:in?|tia))?)?{td_sep_fi})?"
                           r"(?:(?P<seconds>[-+]?\d+)\s?s(?:ek(?:un(?:nin?|tia))?)?)?"
                           r"(?:\s(?:kuluttua|päästä?))?"
                           r"(?:\s|$)"),
    date=ShortYearMatcher(r"(?P<day>\d{1,2})\.(?P<month>\d{1,2})\.(?P<year>\d{2}(?:\d{2})?)\s"),
    weekday=WeekdayMatcher(pattern=r"(?:tänään"
                                   r"|(?:yli)?huomen"
                                   r"|ma(?:aanantai)?"
                                   r"|ti(?:iistai)?"
                                   r"|ke(?:skiviikko)?"
                                   r"|to(?:rstai)?"
                                   r"|pe(?:rjantai)?"
                                   r"|la(?:uantai)?"
                                   r"|su(?:nnuntai)?)"
                                   r"(?:na)?"
                                   r"(?:\s|$)",
                           map={
                               "tä": +0, "hu": +1, "yl": +2,
                               "ma": MO, "ti": TU, "ke": WE, "to": TH, "pe": FR, "la": SA, "su": SU,
                           }, substr=2),
    time=RegexMatcher(r"\s?(?:ke?ll?o\.?\s)?"
                      r"(?P<hour>\d{2})"
                      r"[:.](?P<minute>\d{2})"
                      r"(?:[:.](?P<second>\d{2}))?"
                      r"(?:\s|$)"),
)

td_sep_de = r"(?:[\s,]{1,3}(?:und\s)?)"
locales["de_de"] = Locale(
    name="German",
    timedelta=RegexMatcher(rf"(?:in\s)?"
                           rf"(?:(?P<years>[-+]?\d+)\s?jahr(?:en)?{td_sep_de})?"
                           rf"(?:(?P<months>[-+]?\d+)\s?monat(?:en)?{td_sep_de})?"
                           rf"(?:(?P<weeks>[-+]?\d+)\s?wochen?{td_sep_de})?"
                           rf"(?:(?P<days>[-+]?\d+)\s?tag(?:en)?{td_sep_de})?"
                           rf"(?:(?P<hours>[-+]?\d+)\s?stunden?{td_sep_de})?"
                           rf"(?:(?P<minutes>[-+]?\d+)\s?minuten?{td_sep_de})?"
                           r"(?:(?P<seconds>[-+]?\d+)\s?sekunden?)?"),
    date=ShortYearMatcher(
        r"(?P<day>\d{1,2})\.(?P<month>\d{1,2})\.(?P<year>\d{2}(?:\d{2})?)(?:\s|$)"),
    weekday=WeekdayMatcher(pattern=r"(?:heute"
                                   r"|(?:über)?morgen"
                                   r"|mo(?:ntag)?"
                                   r"|di(?:enstag)?"
                                   r"|mi(?:ttwoch)?"
                                   r"|do(?:nnerstag)?"
                                   r"|fr(?:eitag)?"
                                   r"|sa(?:mstag)?"
                                   r"|so(?:nntag)?)"
                                   r"(?:\s|$)",
                           map={
                               "heu": +0, "mor": +1, "übe": +2, "mon": MO, "die": TU, "mit": WE,
                               "don": TH, "fre": FR, "sam": SA, "son": SU,
                           }, substr=3),
    time=RegexMatcher(r"\s?(?:um\s)?"
                      r"(?P<hour>\d{2})"
                      r"[:.](?P<minute>\d{2})"
                      r"(?:[:.](?P<second>\d{2}))?"
                      r"(?:\s|$)"),
)
