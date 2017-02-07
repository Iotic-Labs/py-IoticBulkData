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

import json
import datetime
import requests

import logging
logger = logging.getLogger(__name__)

from IoticAgent import Datatypes
from IoticAgent.Core.compat import monotonic
from IoticAgent.Core.Const import R_FEED
from IoticAgent.Core.Validation import VALIDATION_META_LABEL, VALIDATION_META_COMMENT

from Ioticiser import SourceBase  # pylint: disable=import-error

logging.basicConfig(format='%(asctime)s,%(msecs)03d %(levelname)s [%(name)s] {%(threadName)s} %(message)s',
                    level=logging.INFO)


REFRESH_TIME = 60 * 30
LANG = 'en'


AQI_CATEGORIES = {
    0: 'Good',
    1: 'Good',
    2: 'Moderate',
    3: 'Unhealthy for Sensitive Groups',
    4: 'Unhealthy',
    5: 'Very Unhealthy',
    6: 'Hazardous'
}

POINT_LABELS = {
    'PM2.5': 'Particule matter 2.5',
    'PM10': 'Particule matter 10',
    'NO2': 'Nitrogen dioxide',
    'SO2': 'Sulfur dioxide',
    'CO': 'Carbon monoxide',
    'OZONE': 'Ozone'
}

UNIT = {
    'OZONE': 'http://purl.obolibrary.org/obo/UO_0000170',
    'PM2.5': 'http://purl.obolibrary.org/obo/UO_0000301',
    'PM10': 'http://purl.obolibrary.org/obo/UO_0000301',
    'NO2': 'http://purl.obolibrary.org/obo/UO_0000170',
    'SO2': 'http://purl.obolibrary.org/obo/UO_0000170',
    'CO': 'http://purl.obolibrary.org/obo/UO_0000170'
}


# CLASS Air Quality Stations ---------------------------------------------------------------------------------
class AQIStations(SourceBase):
    ''' Class to load all the air quality information from Airnow API
    '''
    __license_notice = ('Obtained via The Environmental Protection Agency\'s AirNow API (AirNowAPI.org).')
    __prefix = 'sf_AQI_'

    __airNow_base_url = 'http://www.airnowapi.org/aq/data/?'
    __airNow_init_date_param = "startDate={0}"
    __airNow_end_date_param = "endDate={0}"
    __airNow_parameters_param = "parameters=O3,PM25,PM10,CO,NO2,SO2"
    __airNow_bbox_param = "BBOX=-123.005371,36.907896,-121.467285,38.196905"
    __airNow_data_type_param = "dataType=B"
    __airNow_response_type_param = "format=application/json"
    __airNow_verbose_para = "verbose=1"
    __airNow_api_key_param = "API_KEY={0}"

    __datetime_format = "%Y-%m-%dT%H"

    def __init__(self, stash, config, stop):

        super(AQIStations, self).__init__(stash, config, stop)
        self.__limit = None
        self.__refresh_time = REFRESH_TIME
        self.__aqi_stations_dic = {}
        self.__validate_config()
        self.__create_url()

    def __validate_config(self):

        if 'app_key' not in self._config:
            msg = "Config requires app_key"
            logger.error(msg)
            raise ValueError(msg)
        if 'format_limit_things' in self._config:
            self.__limit = int(self._config['format_limit_things'])
        if 'refresh_time' in self._config:
            self.__refresh_time = float(self._config['refresh_time'])

    # Creates the url to get data from Airnow
    def __create_url(self):

        app_key = self._config['app_key']
        end_date = datetime.datetime.today()
        init_date = datetime.datetime.today() - datetime.timedelta(hours=1)

        full_url = self.__airNow_base_url
        full_url += self.__airNow_init_date_param.format(init_date.strftime(self.__datetime_format))
        full_url += "&" + self.__airNow_end_date_param.format(end_date.strftime(self.__datetime_format))
        full_url += "&" + self.__airNow_parameters_param
        full_url += "&" + self.__airNow_bbox_param
        full_url += "&" + self.__airNow_data_type_param
        full_url += "&" + self.__airNow_response_type_param
        full_url += "&" + self.__airNow_verbose_para
        full_url += "&" + self.__airNow_api_key_param.format(app_key)

        self.__full_url = full_url

    @classmethod
    def __call_api(cls, fname, apiurl):
        url = apiurl
        try:
            logger.info('Sending request')
            rls = requests.get(url)
            rls.raise_for_status()
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("__call_api error: %s", str(exc))
        logger.debug("__call_api name=%s url=%s, status_code=%s", fname, url, rls.status_code)
        if rls.ok:
            fdata = rls.text
            return json.loads(fdata)
        else:
            logger.error("__call_api error %i", rls.status_code)

# Thing basic information ----------------------------------

    # Sets basic thing information
    @classmethod
    def __set_thing_attributes(cls, station, thing):

        name = 'Air quality in ' + station['Name']
        label = name[:VALIDATION_META_LABEL].strip()  # todo? ensure length
        thing.set_label(label, LANG)
        thing.create_tag(['pollution', 'quality', 'AQI', 'air', 'san_francisco'])
        latitude = station['Latitude']
        longitude = station['Longitude']
        thing.set_location(float(latitude), float(longitude))
        thing.set_public(public=True)

    # Sets thing's description
    @classmethod
    def __set_thing_description(cls, station, thing):

        description = 'Site: ' + station['Name'] + " - "
        description += "Agency: " + station['Agency'] + ". "
        description += cls.__license_notice
        description = description[:VALIDATION_META_COMMENT].strip()  # todo? ensure length
        thing.set_description(description, LANG)

        logger.info(description)

# Set thing's points ---------------------------------------------------

    # Creates points for feed data
    @classmethod
    def __set_thing_points(cls, station, thing):
        # Points
        for parameter in station['Parameters']:

            parameter_info = station['Parameters'][parameter]
            value = parameter_info['Value']
            if parameter == 'PM10' or parameter == 'PM2.5':
                value = value / 1000

            point = thing.create_point(R_FEED, parameter)
            point.set_label(POINT_LABELS[parameter], LANG)
            point.set_description(POINT_LABELS[parameter] + ' quantity contained in the air', LANG)
            point.create_value('Air_quality_index',
                               vtype=Datatypes.INT,
                               description='Air quality index',
                               data=(parameter_info['AQI']))
            point.create_value('Value',
                               vtype=Datatypes.INT,
                               description='Parameter value',
                               data=value,
                               unit=UNIT[parameter])
            point.create_value('Category',
                               vtype=Datatypes.STRING,
                               description='AQI category',
                               data=AQI_CATEGORIES[parameter_info['Category']])
            point.create_value('Last_update',
                               vtype=Datatypes.DATETIME,
                               description='Last updated',
                               data=parameter_info['UTC'])

            point.set_recent_config(max_samples=24)
            point.share()

# Parse data ---------------------------------------------------

    # Gets data in JSON format
    def __get(self):

        self.__create_url()
        logger.info("URL: " + self.__full_url)

        data = self.__call_api('airnow_data', self.__full_url)
        logger.debug(data)
        if data is not None:
            self.__parse_airnow_data(data)

    # Parses all the data and creates a dictionary
    def __parse_airnow_data(self, data):

        logger.info('Parsing data')

        for _, station in enumerate(data):

            if station['SiteName'] not in self.__aqi_stations_dic.keys():
                self.__aqi_stations_dic[station['SiteName']] = {}
                self.__aqi_stations_dic[station['SiteName']]['Parameters'] = {}
                self.__aqi_stations_dic[station['SiteName']]['Agency'] = station['AgencyName']
                self.__aqi_stations_dic[station['SiteName']]['Name'] = station['SiteName']
                self.__aqi_stations_dic[station['SiteName']]['Longitude'] = station['Longitude']
                self.__aqi_stations_dic[station['SiteName']]['Latitude'] = station['Latitude']

            self.__aqi_stations_dic[station['SiteName']]['Parameters'][station['Parameter']] = station

# Public methods ------------------------------------------

    # Initialize air quality things and puts feeds data
    def initialize_aqi_station_thing(self):

        self.__get()

        logger.info('Creating things')

        for station_name in self.__aqi_stations_dic:
            station_info = self.__aqi_stations_dic[station_name]
            thing_name = self.__prefix + station_name

            with self._stash.create_thing(thing_name) as thing:

                self.__set_thing_attributes(station_info, thing)
                self.__set_thing_description(station_info, thing)
                self.__set_thing_points(station_info, thing)

    # Updates each feed with new data
    def update_info(self):
        self.__get()

        logger.info('Update things')

        for station_name in self.__aqi_stations_dic:
            station_info = self.__aqi_stations_dic[station_name]

            thing_name = self.__prefix + station_name
            with self._stash.create_thing(thing_name) as thing:
                self.__set_thing_points(station_info, thing)

# RUN ---------------------------------------------------------------------------------------------------

    def run(self):

        self.initialize_aqi_station_thing()
        lasttime = 0
        while not self._stop.is_set():
            nowtime = monotonic()
            if nowtime - lasttime > self.__refresh_time:
                lasttime = nowtime

                self.update_info()

            self._stop.wait(timeout=5)
