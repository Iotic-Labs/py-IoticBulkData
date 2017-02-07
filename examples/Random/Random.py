# Copyright (c) 2017 Iotic Labs Ltd. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://github.com/Iotic-Labs/py-application-examples/blob/master/LICENSE
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Simple Test Feed Generator, example source for Ioticiser
"""

from __future__ import unicode_literals

from datetime import datetime
import logging
import math
import string
import random

logging.basicConfig(format='%(asctime)s,%(msecs)03d %(levelname)s [%(name)s] {%(threadName)s} %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

from IoticAgent import Datatypes
from IoticAgent.Core.compat import monotonic

from Ioticiser import SourceBase


LANG = 'en'

HOURLY_SINE_SLEEP_SECS = 60  # 360 minutes in an hour, 360 degrees in a circle
SAW_TOOTH_SLEEP_SECS = 10
ALPHA_LOWER_SLEEP_SECS = 10
ALPHA_UPPER_SLEEP_SECS = 10
ALPHA_RANDOM_SLEEP_SECS = 10
RANDOM_NUMBER_SLEEP_SECS = 10

RANDOM_NUMBER = "random number"
RANDOM_ALPHA = "alphabet random"
ALPHA_LOWER = "alphabet lower"
ALPHA_UPPER = "alphabet upper"
SAW_TOOTH = "saw tooth"
HOURLY_SINE = "hourly sine"


class Random(SourceBase):  # pylint: disable=too-many-instance-attributes

    def __init__(self, stash, config, stop):
        super(Random, self).__init__(stash, config, stop)
        self.__thing = None
        self.__number_start = 0
        self.__alpha_start = 0
        self.__alpha_idx = 0
        self.__alpha_list = list(string.ascii_lowercase)
        self.__lower_start = 0
        self.__lower_idx = 0
        self.__upper_start = 0
        self.__upper_list = list(string.ascii_uppercase)
        self.__upper_idx = 0
        self.__saw_start = 0
        self.__saw_count_up = True
        self.__saw_value = 0
        self.__sine_start = 0
        self.__sine_degrees = 0

    def run(self):
        self.__thing = self.__create_thing()

        self.__create_hourly_sine()
        self.__create_saw_tooth()
        self.__create_alphabet_lower()
        self.__create_alphabet_upper()
        self.__create_alphabet_random()
        self.__create_random_number()

        self.__thing.set_public(public=True)

        while not self._stop.is_set():
            with self.__thing:
                self.__run_hourly_sine()
                self.__run_saw_tooth()
                self.__run_alphabet_lower()
                self.__run_alphabet_upper()
                self.__run_alphabet_random()
                self.__run_random_number()

            self._stop.wait(timeout=1)

        logger.info("Finished")

    def __create_thing(self):
        t_feed_generator = self._stash.create_thing("Test feed generator")
        t_feed_generator.set_label("Test feed generator", lang=LANG)
        t_feed_generator.set_description("Generates Wave forms for testing", lang=LANG)
        t_feed_generator.create_tag(["test", "feed", "generator"])
        return t_feed_generator

    def __create_random_number(self):
        f_alphabet = self.__thing.create_feed(RANDOM_NUMBER)
        f_alphabet.set_recent_config(max_samples=1)
        f_alphabet.set_label("Random number generator", lang=LANG)
        f_alphabet.set_description("Generates a random number from 0 - 10", lang=LANG)

    def __run_random_number(self):
        if monotonic() - self.__number_start >= RANDOM_NUMBER_SLEEP_SECS:
            feed = self.__thing.create_feed(RANDOM_NUMBER)
            feed.create_value("value",
                              Datatypes.INTEGER,
                              "en",
                              "random number",
                              data=random.randint(0, 10))
            feed.share(time=datetime.utcnow())

            self.__number_start = monotonic()

    def __create_alphabet_random(self):
        f_alphabet = self.__thing.create_feed(RANDOM_ALPHA)
        f_alphabet.set_recent_config(max_samples=1)
        f_alphabet.set_label("Alphabet generator - random letter", lang=LANG)
        f_alphabet.set_description("generates a random letter from the alphabet", lang=LANG)

    def __run_alphabet_random(self):
        if monotonic() - self.__alpha_start >= ALPHA_LOWER_SLEEP_SECS:
            feed = self.__thing.create_feed(RANDOM_ALPHA)
            feed.create_value("value",
                              Datatypes.STRING,
                              "en",
                              "random letter",
                              data=random.choice(self.__alpha_list))
            feed.share(time=datetime.utcnow())

            self.__alpha_idx += 1
            if self.__alpha_idx >= len(self.__alpha_list):
                self.__alpha_idx = 0

            self.__alpha_start = monotonic()

    def __create_alphabet_lower(self):
        f_alphabet = self.__thing.create_feed(ALPHA_LOWER)
        f_alphabet.set_recent_config(max_samples=1)
        f_alphabet.set_label("Alphabet generator - lower case", lang=LANG)
        f_alphabet.set_description("Cycles Through a-z and then starts at a again", lang=LANG)

    def __run_alphabet_lower(self):
        if monotonic() - self.__lower_start >= ALPHA_LOWER_SLEEP_SECS:
            feed = self.__thing.create_feed(ALPHA_LOWER)
            feed.create_value("value",
                              Datatypes.STRING, "en", "value of letter",
                              data=self.__alpha_list[self.__lower_idx])
            feed.share(time=datetime.utcnow())

            self.__lower_idx += 1
            if self.__lower_idx >= len(self.__alpha_list):
                self.__lower_idx = 0

            self.__lower_start = monotonic()

    def __create_alphabet_upper(self):
        f_alphabet = self.__thing.create_feed(ALPHA_UPPER)
        f_alphabet.set_recent_config(max_samples=1)
        f_alphabet.set_label("Alphabet generator - upper case", lang=LANG)
        f_alphabet.set_description("Cycles Through A-Z and then starts at A again", lang=LANG)

    def __run_alphabet_upper(self):
        if monotonic() - self.__upper_start >= ALPHA_UPPER_SLEEP_SECS:
            feed = self.__thing.create_feed(ALPHA_UPPER)
            feed.create_value("value",
                              Datatypes.STRING,
                              "en",
                              "value of letter",
                              data=self.__upper_list[self.__upper_idx])
            feed.share(time=datetime.utcnow())

            self.__upper_idx += 1
            if self.__upper_idx >= len(self.__upper_list):
                self.__upper_idx = 0

            self.__upper_start = monotonic()

    def __create_saw_tooth(self):
        f_saw_tooth = self.__thing.create_feed(SAW_TOOTH)
        f_saw_tooth.set_recent_config(max_samples=1)
        f_saw_tooth.set_label("Saw tooth wave", lang=LANG)
        f_saw_tooth.set_description("Cycles from 0 to 10 and back down again", lang=LANG)

    def __run_saw_tooth(self):
        if monotonic() - self.__saw_start >= SAW_TOOTH_SLEEP_SECS:
            feed = self.__thing.create_feed(SAW_TOOTH)
            feed.create_value("value",
                              Datatypes.DECIMAL,
                              "en",
                              "value of sawtooth",
                              data=self.__saw_value)
            feed.share(time=datetime.utcnow())

            if self.__saw_count_up:
                self.__saw_value += 1
            else:
                self.__saw_value -= 1

            if self.__saw_value > 10:
                self.__saw_value = 9
                self.__saw_count_up = False
            elif self.__saw_value < 0:
                self.__saw_value = 1
                self.__saw_count_up = True

            self.__saw_start = monotonic()

    def __create_hourly_sine(self):
        f_hourly_sine = self.__thing.create_feed(HOURLY_SINE)
        f_hourly_sine.set_recent_config(max_samples=1)
        f_hourly_sine.set_label("Sine wave", lang=LANG)
        f_hourly_sine.set_description("Cycles through 360 degrees of a sine wave in one hour", lang=LANG)

    def __run_hourly_sine(self):
        if monotonic() - self.__sine_start >= HOURLY_SINE_SLEEP_SECS:
            radians = self.__sine_degrees * (math.pi / 180)
            feed = self.__thing.create_feed(HOURLY_SINE)
            feed.create_value("value", Datatypes.DECIMAL, "en", "value of sine function", data=math.sin(radians))
            feed.share(time=datetime.utcnow())

            self.__sine_degrees += 1
            if self.__sine_degrees >= 360:
                self.__sine_degrees = 0

            self.__sine_start = monotonic()
