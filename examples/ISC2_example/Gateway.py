# Copyright (c) 2017 Iotic Labs Ltd. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://github.com/Iotic-Labs/py-IoticBulkData/blob/master/LICENSE
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import unicode_literals

import json
import requests
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(format='%(asctime)s,%(msecs)03d %(levelname)s [%(name)s] {%(threadName)s} %(message)s',
                    level=logging.INFO)
logging.getLogger('IoticAgent.Core.Client').setLevel(logging.WARNING)
# Iotic imports ---------------------------

from IoticAgent import Datatypes, Units
from IoticAgent.Core.compat import monotonic

from Ioticiser import SourceBase  # pylint: disable=import-error


LANG = 'en'

# Keys
# Reading
KEY_ID = 'id'
KEY_TEMP = 'temp'
KEY_POWER = 'power_consumption'
# HVAC list
KEY_NAME = 'name'
# config
KEY_URL = 'hvac_url'
KEY_REFRESH = 'refresh_time'

# CLASS APIRequester --------------------------------------------------------------------------------------


class APIRequester(object):
    '''
        This class manages the calls to any API
    '''

    @classmethod
    def call_api(cls, desc, apiurl):
        try:
            rls = requests.get(apiurl)
            rls.raise_for_status()
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("__call_api %s error: %s", desc, exc)
            return []
        else:
            fdata = rls.text
            return json.loads(fdata)


# CLASS GatewayPublisher ----------------------------------------------------------------------------------------------

class GatewayPublisher(SourceBase):
    """
        Creates and publishes dummy HVAC data
        This class transforms each hvac json-object into an Iotic Thing.
    """
    # Housekeeping   --------------------------------------------------------------------------------------------------

    def __init__(self, stash, config, stop):

        super(GatewayPublisher, self).__init__(stash, config, stop)
        self.__refresh_time = None
        self.__hvac_url = None
        self.__validate_config()
        self.__hvac_list = []
        self.__things = {}

    def __validate_config(self):

        if KEY_REFRESH in self._config:
            try:
                self.__refresh_time = float(self._config[KEY_REFRESH])
            except ValueError:
                raise ValueError("refresh_time not numeric")
        else:
            raise ValueError("refresh_time should be in the config")

        if 'hvac_url' in self._config:
            self.__hvac_url = self._config[KEY_URL]
        else:
            raise ValueError("hvac_url should be in the config")

    # Get data from API  ----------------------------------------------------------------------------------------------

    def __get_hvac_list_from_API(self):
        data = APIRequester.call_api('Dummy HVAC List API', self.__hvac_url + "list")
        if data is not None:
            self.__parse_hvac_list_format(data)
            return data

    def __get_hvac_reading_from_API(self, hvac_id):
        data = APIRequester.call_api('Dummy HVAC Reading API', self.__hvac_url + "reading/" + str(hvac_id))
        if data is not None:
            self.__parse_hvac_reading_format(data)

    # PARSE data from the API and convert into Iotic Things and Feeds  ------------------------------------------------

    def __parse_hvac_list_format(self, data):
        """
            Builds list of ids and names for later
        """
        for json_hvac in data:
            # We need a unique name for the thing
            thing_name = json_hvac[KEY_NAME]
            # store this thing in a dict with its id as key
            self.__things[json_hvac[KEY_ID]] = thing_name

            logger.info('Stored %s', thing_name)

    def __parse_hvac_reading_format(self, reading):
        """
            Uses reading to create data for the feed and shares
        """
        try:
            thing_name = self.__things[reading[KEY_ID]]
        except KeyError:
            logger.error("HVAC id %s not found in list ", reading[KEY_ID])  # don't have a thing for this Id
        else:
            self.__share_thing_feed(reading, thing_name)
            logger.info('Shared reading for thing %s', reading[KEY_ID])

    # Setup meta data for thing and feeds -----------------------------------------------------------------------------

    def __share_thing_feed(self, reading, thing_name):
        """
            Sets Thing's label & description
            Creates point and values and shares in background
            Keeps Thing private
        """
        # create a thing in the stash and fill in metadata
        with self._stash.create_thing(thing_name) as thing:
            thing.set_label(thing_name, LANG)
            thing.set_description("Heating ventilation and air conditioning system " + thing_name, LANG)
            thing.create_tag(['hvac', 'heating', 'ventilation', 'aircon'])

            thing.set_public(public=False)

            feed = thing.create_feed("Readings")
            feed.set_label("Readings from HVAC " + str(reading[KEY_ID]), LANG)
            feed.create_value(KEY_ID,
                              vtype=Datatypes.INT,
                              description='Id number of HVAC',
                              data=reading[KEY_ID])
            feed.create_value(KEY_POWER,
                              vtype=Datatypes.INT,
                              description='Power consumption in Watts',
                              unit=Units.WATT,
                              data=reading[KEY_POWER])
            feed.create_value(KEY_TEMP,
                              vtype=Datatypes.INT,
                              description='Temperature in Celsius',
                              unit=Units.CELSIUS,
                              data=reading[KEY_TEMP])

            feed.set_recent_config(max_samples=0)  # don't store recent data as it updates every 15 seconds
            # feed.share()

    # RUN public method  ----------------------------------------------------------------------------------------------

    def run(self):
        # get the list of hvacs
        self.__hvac_list = self.__get_hvac_list_from_API()
        if len(self.__hvac_list) > 0:
            lasttime = 0
            while not self._stop.is_set():
                nowtime = monotonic()
                if nowtime - lasttime > self.__refresh_time:
                    lasttime = nowtime
                    # hit the api for the readings for each hvac in list
                    for hvac in self.__hvac_list:
                        self.__get_hvac_reading_from_API(hvac[KEY_ID])
                self._stop.wait(timeout=5)
        else:
            logger.critical("no HVACs found - is the REST API running?")
