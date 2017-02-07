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

from __future__ import unicode_literals

from datetime import datetime


import logging

logger = logging.getLogger(__name__)
logging.basicConfig(format='%(asctime)s,%(msecs)03d %(levelname)s [%(name)s] {%(threadName)s} %(message)s',
                    level=logging.INFO)

# Iotic imports ---------------------------

from IoticAgent import Datatypes, Units
from IoticAgent.Core.compat import monotonic
from IoticAgent.Core.Const import R_FEED
from IoticAgent.Core.Validation import VALIDATION_META_LABEL, VALIDATION_META_COMMENT

from Ioticiser import SourceBase  # pylint: disable = import-error


from .Formatter import Formatter
from .AirportEntities import AirportsBuilder

REFRESH_TIME = 60 * 60  # 1 hour
LANG = 'en'


# CLASS AirportsPublisher ---------------------------------------------------------------------------------------------

class AirportsPublisher(SourceBase):

    __prefix = 'usap_'
    __license_notice = "http://faa.gov/web_policies/"

    def __init__(self, stash, config, stop):

        super(AirportsPublisher, self).__init__(stash, config, stop)
        self.__limit = None
        self.__refresh_time = REFRESH_TIME
        self.__validate_config()

    def __validate_config(self):

        if 'app_key' not in self._config:
            msg = "Config requires app_key"
            logger.error(msg)
            raise ValueError(msg)
        if 'format_limit_things' in self._config:
            self.__limit = int(self._config['format_limit_things'])
        if 'refresh_time' in self._config:
            self.__refresh_time = float(self._config['refresh_time'])

    def get(self):

        airportsBuilder = AirportsBuilder('usfaa_airports/airports.csv')
        self.convert_objects_to_things(airportsBuilder.get_airports())

    # PARSE DATA ------------------------------------------------------------------------------------------------
    @classmethod
    def __set_thing_attributes(cls, airport, thing):

        trimmed_name = airport.name.translate({ord(c): " " for c in r"!@#$%^&*()[]{};:,./<>?\|`~-=_+"})
        trimmed_name = trimmed_name.replace('\n', ' ').replace('\r', '')
        label = trimmed_name[:VALIDATION_META_LABEL].strip()  # todo? ensure length
        thing.set_label(label, LANG)
        thing.create_tag(['airport', 'usfaa', 'airports', 'weather'])
        latitude = airport.latitude
        longitude = airport.longitude
        thing.set_location(float(latitude), float(longitude))
        thing.set_public(public=True)

    # Sets thing's description
    @classmethod
    def __set_thing_description(cls, airport, iata_code, thing):

        description = 'US FAA Airport {0} {1} {2} USA. Information about Dealys and Weather. {3}'

        description = description.format(
            iata_code,
            airport.name,
            airport.details.state,
            cls.__license_notice)

        description = description[:VALIDATION_META_COMMENT].strip()  # todo? ensure length
        thing.set_description(description, LANG)

        logger.info(description)

    @classmethod
    def __set_weather_point(cls, airport, iata_code, thing):

        weather = airport.details.weather
        if weather is not None:

            wind = airport.details.wind
            if wind is not None:

                logger.debug(wind)
                wind_direction, wind_speed = Formatter.get_wind(wind)

            weather_time = Formatter.get_local_time(airport.details.last_updated, airport.timezone)

            point = thing.create_point(R_FEED, iata_code + '_weather')
            point.set_label('Weather', LANG)
            point.set_description('Airport weather', LANG)
            point.create_value('Time',
                               vtype=Datatypes.DATETIME,
                               description='observation time',
                               data=weather_time.isoformat())

            temperature = Formatter.get_temperature(airport.details.temperature)

            point.create_value('Temperature',
                               vtype=Datatypes.DECIMAL,
                               description='temperature in celsius',
                               unit=Units.CELSIUS,
                               data=temperature)
            point.create_value('Wind_speed',
                               vtype=Datatypes.DECIMAL,
                               description='windspeed in mph',
                               data=wind_speed)
            point.create_value('Wind_direction',
                               vtype=Datatypes.STRING,
                               description='wind direction in compass point: North, Northeast',
                               data=wind_direction)
            point.create_value('Weather',
                               vtype=Datatypes.STRING,
                               description='description of weather',
                               data=weather)
            point.create_value('Visibility',
                               vtype=Datatypes.DECIMAL,
                               description='visibility in miles',
                               data=airport.details.visibility)

            point.set_recent_config(max_samples=1)
            point.share()

    @classmethod
    def __set_delay_point(cls, airport, iata_code, thing):

        time = datetime.utcnow()

        delay_seconds = Formatter.get_delay_seconds(airport.details.average_delay)
        delay_seconds = delay_seconds if airport.details.delay is True else 0

        delay_type = airport.details.delay_type if airport.details.delay is True else 'No delay'

        point = thing.create_point(R_FEED, iata_code + '_delay')
        point.set_label('Delays', LANG)
        point.set_description('Delay info, reason, type and duration', LANG)
        point.create_value('Time',
                           vtype=Datatypes.DATETIME,
                           description='publish time',
                           data=time.isoformat())
        point.create_value('Delay',
                           vtype=Datatypes.BOOLEAN,
                           description='presence of delay',
                           data=airport.details.delay)
        point.create_value('Reason',
                           vtype=Datatypes.STRING,
                           description='AQI reason for delay',
                           data=airport.details.delay_reason)
        point.create_value('Type',
                           vtype=Datatypes.STRING,
                           description='type of delay',
                           data=delay_type)
        point.create_value('Average_delay',
                           vtype=Datatypes.INTEGER,
                           description='lengh of delay in seconds',
                           unit=Units.SECOND,
                           data=delay_seconds)

        point.set_recent_config(max_samples=1)
        point.share()

    # Transform airport object to things
    def convert_objects_to_things(self, airports):

        for iata_code in airports:

            # We need a unique name for the thing
            thing_name = self.__prefix + iata_code

            airport = airports[iata_code]

            with self._stash.create_thing(thing_name) as thing:

                self.__set_thing_attributes(airport, thing)
                self.__set_thing_description(airport, iata_code, thing)
                self.__set_delay_point(airport, iata_code, thing)
                self.__set_weather_point(airport, iata_code, thing)

            # logger.info('Created ' + thing_name)

    # RUN ---------------------------------------------------------------------------------------------------
    def run(self):
        lasttime = 0

        while not self._stop.is_set():
            nowtime = monotonic()
            if nowtime - lasttime > self.__refresh_time:
                lasttime = nowtime
                self.get()
                logger.info('Updating data')

            self._stop.wait(timeout=5)
