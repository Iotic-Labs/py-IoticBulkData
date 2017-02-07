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
from datetime import datetime
from collections import namedtuple
import requests

import logging
logging.basicConfig(format='%(asctime)s,%(msecs)03d %(levelname)s [%(name)s] {%(threadName)s} %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

from IoticAgent import Datatypes
from IoticAgent.Core.compat import monotonic
from IoticAgent.Core.Const import R_FEED
from IoticAgent.Core.Validation import VALIDATION_META_LABEL, VALIDATION_META_COMMENT

from Ioticiser import SourceBase


AdditionalProperties = namedtuple('AdditionalProperties',
                                  'time_stamp'
                                  ' terminal_id'
                                  ' install_date'
                                  ' temporary'
                                  ' available_bikes'
                                  ' empty_docks, '
                                  ' total_docks')


REFRESH_TIME = 60 * 30
LANG = 'en'


class Bikes(SourceBase):

    __prefix = 'tflbk_'
    __timeFmt = '%Y-%m-%dT%H:%M:%SZ'
    __timeFmtFractional = '%Y-%m-%dT%H:%M:%S.%fZ'
    __boris_bikes_url = 'https://api.tfl.gov.uk/BikePoint?'

    def __init__(self, stash, config, stop):
        super(Bikes, self).__init__(stash, config, stop)
        self.__limit = None
        self.__refresh_time = REFRESH_TIME
        self.__make_public = False
        self.__validate_config()

    def __validate_config(self):
        if 'app_id' not in self._config:
            msg = "Config requires app_id"
            logger.error(msg)
            raise ValueError(msg)
        if 'app_key' not in self._config:
            msg = "Config requires app_key"
            logger.error(msg)
            raise ValueError(msg)
        if 'limit_things' in self._config:
            try:
                self.__limit = int(self._config['limit_things'])
            except ValueError:
                msg = "Limit things should be numeric"
                logger.error(msg)
                raise ValueError(msg)
        logger.info("limit things %s", str(self.__limit))

        if 'refresh_time' in self._config:
            try:
                self.__refresh_time = float(self._config['refresh_time'])
            except ValueError:
                msg = "Refresh time should be numeric"
                logger.error(msg)
                raise ValueError(msg)
        logger.info("refresh time %s", str(self.__refresh_time))

        if 'make_public' in self._config:
            self.__make_public = True if self._config['make_public'] == "True" else False
        logger.info("make public %s", str(self.__make_public))

    def run(self):
        lasttime = 0
        while not self._stop.is_set():
            nowtime = monotonic()
            if nowtime - lasttime > self.__refresh_time:
                lasttime = nowtime
                self.get()
            self._stop.wait(timeout=5)

    def get(self):
        full_boris_bikes_url = self.__boris_bikes_url
        full_boris_bikes_url += "app_id=" + self._config['app_id']
        full_boris_bikes_url += "&app_key=" + self._config['app_key']
        data = self.__call_api('boris_bikes', full_boris_bikes_url)
        if data is not None:
            self._parse_boris_bikes_format(data, "Santander Cycles Station")

    @classmethod
    def __call_api(cls, fname, apiurl):
        url = apiurl
        try:
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

    @classmethod
    def _parse_boris_bikes_additional(cls, additional_properties):

        time_stamp = terminal_id = install_date = temporary = available_bikes = empty_docks = total_docks = None

        for prop in additional_properties:
            if prop["key"] == "TerminalName":
                terminal_id = prop["value"]
            elif prop["key"] == "InstallDate":
                if len(prop["value"]) > 0:
                    install_date = datetime.fromtimestamp(int(prop["value"][:-3])).strftime('%Y-%m-%d %H:%M:%S')
                else:
                    install_date = "Unknown"
            elif prop["key"] == "Temporary":
                temporary = "Permanent" if prop["value"] == "false" else "Temporary"
            elif prop["key"] == "NbBikes":
                available_bikes = int(prop["value"])
                # unclear whether might have no microsecond part sometimes
                time_stamp = datetime.strptime(prop["modified"],
                                               cls.__timeFmtFractional if '.' in prop["modified"] else cls.__timeFmt)
            elif prop["key"] == "NbEmptyDocks":
                empty_docks = int(prop["value"])
            elif prop["key"] == "NbDocks":
                total_docks = int(prop["value"])
            elif prop["key"] == "NbDocks":
                total_docks = int(prop["value"])

        ap_tuple = AdditionalProperties(time_stamp, terminal_id, install_date, temporary, available_bikes, empty_docks,
                                        total_docks)
        return ap_tuple

    def _parse_boris_bikes_format(self, data, label):
        # Don't forget to add "Powered by TfL Open Data" to the description - part of the T's&C's
        count = 0
        for _, site in enumerate(data):
            if self.__limit is not None and count > self.__limit:
                break
            count += 1
            if self._stop.is_set():
                break
            logger.debug("Parsing: " + site["commonName"])

            # "Additional Properties"
            ap_tuple = self._parse_boris_bikes_additional(site["additionalProperties"])

            # Site name
            site_name = self.__prefix + str(site['id'])
            with self._stash.create_thing(site_name) as thing:
                label = site_name[:VALIDATION_META_LABEL].strip()  # todo? ensure length
                thing.set_label(label, LANG)
                thing.create_tag(['TFL', 'Bike', 'Boris'])  # todo: more/different tags?
                thing.set_location(float(site['lat']), float(site['lon']))

                # Description
                description = label + " "
                description += "Powered by TfL Open Data " + str(site['id']) + " "
                description += str(site['commonName']) + ". "
                description += "Site number: " + ap_tuple.terminal_id + ". "
                description += "Installed: " + ap_tuple.install_date + ". "
                description += ap_tuple.temporary + ". "
                description = description[:VALIDATION_META_COMMENT].strip()  # todo? ensure length
                thing.set_description(description, LANG)

                # Set public using config setting
                thing.set_public(public=self.__make_public)

                # Points
                point = thing.create_point(R_FEED, 'bikes')
                point.set_label('Bike numbers', LANG)
                point.set_description('Bike availablity and site statistics', LANG)
                point.create_value('available',
                                   vtype=Datatypes.INT,
                                   description='Count of available bikes',
                                   data=ap_tuple.available_bikes)
                point.create_value('empty',
                                   vtype=Datatypes.INT,
                                   description='Number of empty slots',
                                   data=ap_tuple.empty_docks)
                point.create_value('total',
                                   vtype=Datatypes.INT,
                                   description='Total bike slots',
                                   data=ap_tuple.total_docks)
                point.share(time=ap_tuple.time_stamp)
