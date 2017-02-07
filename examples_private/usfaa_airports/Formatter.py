# Copyright (c) 2016 Iotic Labs Ltd. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://github.com/Iotic-Labs/py-IoticAgent/blob/master/LICENSE
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import logging
logger = logging.getLogger(__name__)

import re

from datetime import datetime, timedelta


# CLASS Formatter ---------------------------------------------------------------------------------------------
class Formatter(object):

    def __init__(self):
        pass

    @staticmethod
    def get_local_time(local, tzone):

        # local time looks like this "11:56 PM Local"

        __pattern_time = re.compile(r'(\d+?):(\d+?) ([a-zA-Z]+?) ')

        if local is None or tzone is None:
            return None
        else:
            # find all the matches (there will only be one)
            matches = __pattern_time.findall(local)
            hours, mins, ampm = matches[0]
            try:
                hours = int(hours)
                mins = int(mins)
                tzone = int(tzone)
            except ValueError:
                return None
            else:
                if ampm.lower() == "pm":
                    hours = hours + 12
                # build a timestamp using UTC and our hours and mins and subtract the time delta
                time_tuple = datetime.utcnow().timetuple()
                tzone_delta = timedelta(hours=tzone)
                dt_utc = datetime(time_tuple.tm_year, time_tuple.tm_mon, time_tuple.tm_mday,
                                  hours, mins, 0) - tzone_delta
                return dt_utc

    @staticmethod
    def get_delay_seconds(delay):

        # delays look like this "3 hours and 6 minutes" - convert to seconds

        __pattern_digits = re.compile(r'\d+')

        if len(delay) == 0:
            return None
        else:
            # find all the numbers
            matches = __pattern_digits.findall(delay)
            try:
                # TODO - splits on character not matches
                hours, mins = matches[0]
                return int(hours) * 3600 + int(mins) * 60
            except ValueError:
                logger.error("value error in delaysecs get %s, %s", str(matches[0]), delay)
                return None

    @staticmethod
    def get_temperature(temp):

        # temps look like this "62.0 F (16.7 C)" - extract celsius as float

        __pattern_temp = re.compile(r'(\d+?).(\d+?)')

        if len(temp) == 0:
            return None
        else:
            # find all the numbers
            matches = __pattern_temp.findall(temp)
            c_intpart, c_decpart = matches[1]  # second match contains celsius
            try:
                return float(c_intpart) + (float(c_decpart) / (len(c_decpart) * 10))
            except ValueError:
                return None

    @staticmethod
    def get_wind(wind):

        # wind look like this "Southeast at 5.8mph" - return direction and speed

        __pattern_wind = re.compile(r'([a-zA-Z]+?) at (\d+?).(\d+?)mph')

        if len(wind) == 0:
            return (None, None)
        else:
            # find all the numbers
            matches = __pattern_wind.findall(wind)
            direction, s_intpart, s_decpart = matches[0]
            try:
                return (direction, float(s_intpart) + (float(s_decpart) / (len(s_decpart) * 10)))
            except ValueError:
                return (None, None)
