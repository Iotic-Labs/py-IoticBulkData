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


import xml.etree.ElementTree
import requests

import logging
logger = logging.getLogger(__name__)

logging.basicConfig(format='%(asctime)s,%(msecs)03d %(levelname)s [%(name)s] {%(threadName)s} %(message)s',
                    level=logging.INFO)


from IoticAgent import Datatypes
from IoticAgent.Core.compat import monotonic
from IoticAgent.Core.Const import R_FEED
from IoticAgent.Core.Validation import VALIDATION_META_LABEL, VALIDATION_META_COMMENT

from Ioticiser import SourceBase  # pylint: disable=import-error

REFRESH_TIME = 60 * 30
LANG = 'en'

THING_PREFIX = 'BART Station '


# CLASS API_Requester --------------------------------------------------------------------------------------

class API_Requester(object):
    '''Made for calling any API
    '''

    @classmethod
    def call_api(cls, fname, apiurl, target_name):
        url = apiurl
        try:
            rls = requests.get(url)
            rls.raise_for_status()
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("__call_api error: %s", str(exc))
        logger.debug("__call_api name=%s url=%s, status_code=%s", fname, url, rls.status_code)
        if rls.ok:
            fdata = rls.text
            elements = xml.etree.ElementTree.fromstring(fdata)
            target = elements.find(target_name)
            return target
        else:
            logger.error("__call_api error %i", rls.status_code)


# CLASS StationInfo -----------------------------------------------------------------------------------------

class StationInfo(object):
    '''Contains the extra information of one station, tt defines the feed out of the thing
    '''
    __xml_destination = 'destination'
    __xml_abbreviation = 'abbreviation'
    __xml_estimate = 'estimate'
    __xml_minutes = 'minutes'
    __xml_platform = 'platform'
    __xml_direction = 'direction'
    __xml_color = 'color'

    def __init__(self, xml_file):
        self.destination = xml_file.find(self.__xml_destination).text
        self.abbreviation = xml_file.find(self.__xml_abbreviation).text
        self.estimate = xml_file.find(self.__xml_estimate)
        self.minutes = self.estimate.find(self.__xml_minutes).text
        self.platform = self.estimate.find(self.__xml_platform).text
        self.direction = self.estimate.find(self.__xml_direction).text
        self.color = self.estimate.find(self.__xml_color).text


# CLASS Station ---------------------------------------------------------------------------------------------

class Station(object):  # pylint: disable=too-many-instance-attributes
    '''Contains the basic information of one station
    '''
    __xml_name = 'name'
    __xml_abbr = 'abbr'
    __xml_gtfs_latitude = 'gtfs_latitude'
    __xml_gtfs_longitude = 'gtfs_longitude'
    __xml_address = 'address'
    __xml_city = 'city'
    __xml_county = 'county'
    __xml_state = 'state'
    __xml_zipcode = 'zipcode'

    __bart_station_url = 'http://api.bart.gov/api/etd.aspx?cmd=etd'

    def __init__(self, xml_file, app_key):
        self.name = xml_file.find(self.__xml_name).text
        self.abbr = xml_file.find(self.__xml_abbr).text
        self.gtfs_latitude = xml_file.find(self.__xml_gtfs_latitude).text
        self.gtfs_longitude = xml_file.find(self.__xml_gtfs_longitude).text
        self.address = xml_file.find(self.__xml_address).text
        self.city = xml_file.find(self.__xml_city).text
        self.state = xml_file.find(self.__xml_state).text
        self.county = xml_file.find(self.__xml_city).text
        self.zipcode = xml_file.find(self.__xml_zipcode).text

        # Get all the destinations from this station
        full_bart_station_url = self.__bart_station_url + '&orig=' + self.abbr
        full_bart_station_url += "&key=" + app_key
        xml_destinations = API_Requester.call_api('bart_station', full_bart_station_url, 'station').findall('etd')

        self.info = []
        for xml_station_info in xml_destinations:
            self.info.append(StationInfo(xml_station_info))


# CLASS Stations ---------------------------------------------------------------------------------------------

class Stations(SourceBase):
    '''Runs and performs the creation of the things using the external data
    '''

    __license_notice = ('Obtained via San Francisco BART API.'
                        ' Copyright 2016 Bay Area Rapid Transit District.')
    __prefix = 'bartstns_'
    __bart_stations_url = 'http://api.bart.gov/api/stn.aspx?cmd=stns'

    def __init__(self, stash, config, stop):

        super(Stations, self).__init__(stash, config, stop)
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
        full_bart_stations_url = self.__bart_stations_url
        full_bart_stations_url += "&key=" + self._config['app_key']
        data = API_Requester.call_api('bart_stations', full_bart_stations_url, 'stations')
        if data is not None:
            self._parse_bart_stations_format(data)

    # PARSE DATA ------------------------------------------------------------------------------------------------

    @classmethod
    def _set_thing_attributes(cls, station, thing):

        name = station.name
        label = THING_PREFIX + name[:VALIDATION_META_LABEL].strip()  # todo? ensure length
        thing.set_label(label, LANG)
        thing.create_tag(['Station', 'BART'])
        latitude = station.gtfs_latitude
        longitude = station.gtfs_longitude
        thing.set_location(float(latitude), float(longitude))
        thing.set_public(public=True)

    def _set_thing_description(self, station, thing):

        description = station.abbr + " " + station.name + " "
        description += "Address: " + station.address + ". "
        description += "ZipCode: " + station.zipcode + ". "
        description += "City: " + station.city + ". "
        description += "Country: " + station.county + ". "
        description += "State: " + station.state + ". "
        description += self.__license_notice
        description = description[:VALIDATION_META_COMMENT].strip()  # todo? ensure length
        thing.set_description(description, LANG)

        logger.info(description)

    @classmethod
    def _set_thing_points(cls, station, thing):

        # Points
        for info in station.info:

            point = thing.create_point(R_FEED, station.abbr + "_" + info.abbreviation)
            point.set_label(info.destination, LANG)
            point.set_description('Departure to ' + info.destination, LANG)
            point.create_value('minutes',
                               vtype=Datatypes.INT,
                               description='Minutes left for the departure',
                               data=info.minutes)
            point.create_value('platform',
                               vtype=Datatypes.INT,
                               description='Platform number',
                               data=info.platform)
            point.create_value('direction',
                               vtype=Datatypes.STRING,
                               description='Train direction',
                               data=info.direction)
            point.create_value('color',
                               vtype=Datatypes.STRING,
                               description='The colour of the line',
                               data=info.color)

            point.set_recent_config(max_samples=3)
            point.share()

    # Parses data from XML file and creates iotic-things
    def _parse_bart_stations_format(self, data):

        for station_xml in data:

            station = Station(station_xml, self._config['app_key'])

            thing_name = self.__prefix + station.abbr
            with self._stash.create_thing(thing_name) as thing:

                self._set_thing_attributes(station, thing)
                self._set_thing_description(station, thing)
                self._set_thing_points(station, thing)

    # RUN ---------------------------------------------------------------------------------------------------

    def run(self):
        lasttime = 0
        while not self._stop.is_set():
            nowtime = monotonic()
            if nowtime - lasttime > self.__refresh_time:
                lasttime = nowtime

                logger.info('Refreshing data')
                self.get()

            self._stop.wait(timeout=5)
