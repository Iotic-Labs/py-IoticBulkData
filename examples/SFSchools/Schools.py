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

# Iotic imports ---------------------------

from IoticAgent import Datatypes
from IoticAgent.Core.compat import monotonic
from IoticAgent.Core.Const import R_FEED
from IoticAgent.Core.Validation import VALIDATION_META_LABEL, VALIDATION_META_COMMENT

from Ioticiser import SourceBase


REFRESH_TIME = 60 * 30
LANG = 'en'


# CLASS APIRequester --------------------------------------------------------------------------------------

class APIRequester(object):
    '''
        This class manages the calls to any API
    '''

    @classmethod
    def call_api(cls, fname, apiurl):
        url = apiurl
        try:
            rls = requests.get(url)
            rls.raise_for_status()
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning("__call_api failed: %s", str(exc))
        logger.debug("__call_api name=%s url=%s, status_code=%s", fname, url, rls.status_code)
        if rls.ok:
            fdata = rls.text
            return json.loads(fdata)

        logger.debug("__call_api status_code %i", rls.status_code)
        return None


# CLASS School ---------------------------------------------------------------------------------------------

class School(object):  # pylint: disable=too-many-instance-attributes
    """
        Stores school's entity information.
        This class also contains all the needed keys for parsing the JSON file.
    """

    # Basic info
    __key_campus_name = 'campus_name'
    __key_ccsf_entity = 'ccsf_entity'
    __key_category = 'category'
    __key_campus_address = 'campus_address'
    __key_county_name = 'county_name'
    __key_location_1 = 'location_1'
    __key_coordinates = 'coordinates'

    # Feeds
    __key_grade_range = 'grade_range'
    __key_lower_age = 'lower_age'
    __key_upper_age = 'upper_age'

    def __init__(self, json_file):

        # School's info
        self.campus_name = str(json_file[self.__key_campus_name])
        self.ccsf_entity = str(json_file[self.__key_ccsf_entity])
        self.category = str(json_file[self.__key_category])
        self.campus_address = str(json_file[self.__key_campus_address])
        self.county_name = str(json_file[self.__key_county_name])
        self.location = json_file[self.__key_location_1][self.__key_coordinates]

        # School's Feeds
        self.grade_range = str(json_file[self.__key_grade_range])
        self.lower_age = int(json_file[self.__key_lower_age])
        self.upper_age = int(json_file[self.__key_upper_age])

        # Compose a school abbreviation
        trimmed_name = self.campus_name.strip()
        trimmed_name = trimmed_name.translate({ord(c): "_" for c in r"!@#$%^&*()[]{};:,./<>?\|`~-=_+ "})
        max_length = 48
        formatted_name = (trimmed_name[:max_length] + '..') if len(trimmed_name) > max_length else trimmed_name
        self.abbr = formatted_name


# CLASS SchoolsPublisher ---------------------------------------------------------------------------------------------

class SchoolsPublisher(SourceBase):
    """
        Creates and publish San Francisco's schools data
        This class transform each school object into Iotic Thing.
    """

    __license_notice = ('Obtained via San Francisco Open Data API.'
                        ' Open Data Commons Public Domain Dedication and License.')
    __sfopendata_schools_url = 'https://data.sfgov.org/resource/mmsr-vumy.json'
    __prefix = 'sfsch_'
    __user_app_key = True

    def __init__(self, stash, config, stop):

        super(SchoolsPublisher, self).__init__(stash, config, stop)
        self.__limit = None
        self.__refresh_time = REFRESH_TIME
        self.__validate_config()

    def __validate_config(self):

        if 'app_key' not in self._config:
            msg = "No app_key set, the conexion will be limited by SF open data"
            logger.warning(msg)
            self.__use_app_key = False
        if 'format_limit_things' in self._config:
            self.__limit = int(self._config['format_limit_things'])
        if 'refresh_time' in self._config:
            self.__refresh_time = float(self._config['refresh_time'])

    def get_schools_from_API(self):
        full_sfopendata_schools_url = self.__sfopendata_schools_url
        if self.__use_app_key is True:
            full_sfopendata_schools_url += "?$$app_token=" + self._config['app_key']
        data = APIRequester.call_api('sfopendata_schools', full_sfopendata_schools_url)
        if data is not None:
            self.__parse_sfopendata_schools_format(data)

    # PARSE DATA ------------------------------------------------------------------------------------------------

    @classmethod
    def _set_thing_attributes(cls, school, thing):
        """
            Sets Thing's label, name and location (longitude, latitude)
            Makes Thing public
        """
        trimmed_name = school.campus_name.translate({ord(c): " " for c in r"!@#$%^&*()[]{};:,./<>?\|`~-=_+"})
        trimmed_name = trimmed_name.replace('\n', ' ').replace('\r', '')
        label = trimmed_name[:VALIDATION_META_LABEL].strip()  # todo? ensure length
        thing.set_label(label, LANG)
        thing.create_tag(['School', 'SanFrancisco', 'OpenData', 'cat_school'])
        latitude = school.location[1]
        longitude = school.location[0]
        thing.set_location(float(latitude), float(longitude))
        thing.set_public(public=True)

    def _set_thing_description(self, school, thing):

        description = school.campus_name + ". "
        description += "CCSF Entity: " + school.ccsf_entity + ". "
        description += "Grade Range: " + school.grade_range + ". "
        description += "Category: " + school.category + ". "
        description += "Address: " + school.campus_address + ". "
        description += "County: " + school.county_name + ". "

        description += self.__license_notice
        description = description[:VALIDATION_META_COMMENT].strip()  # todo? ensure length
        thing.set_description(description, LANG)

    @classmethod
    def _set_thing_points(cls, school, thing):
        """
            Creates, defines and publish thing's feed
            Uses three school's values as feed: Grade range, Lower age and Upper age
        """
        point = thing.create_point(R_FEED, school.abbr)
        point.set_label(school.abbr + ' Age', LANG)
        point.set_description('Generic age of the site\'s programs', LANG)
        point.create_value('grade_range',
                           vtype=Datatypes.STRING,
                           description='Grade Range',
                           data=school.grade_range)
        point.create_value('lower_age',
                           vtype=Datatypes.INT,
                           description='Corresponding to grades as below Grade Age Identifier',
                           data=school.lower_age)
        point.create_value('upper_age',
                           vtype=Datatypes.INT,
                           description='Upper Age',
                           data=school.upper_age)

        point.set_recent_config(max_samples=-1)

    def __parse_sfopendata_schools_format(self, data):
        """
            Uses json data to create school objects.
            Builds school's thing with the information they have
        """

        for json_school in data:

            school = School(json_school)

            # We need a unique name for the thing
            thing_name = self.__prefix + school.abbr

            with self._stash.create_thing(thing_name) as thing:

                self._set_thing_attributes(school, thing)
                self._set_thing_description(school, thing)
                self._set_thing_points(school, thing)

            logger.info('Created %s', thing_name)

    # RUN ---------------------------------------------------------------------------------------------------

    def run(self):
        lasttime = 0
        while not self._stop.is_set():
            nowtime = monotonic()
            if nowtime - lasttime > self.__refresh_time:
                lasttime = nowtime
                self.get_schools_from_API()
            self._stop.wait(timeout=5)
