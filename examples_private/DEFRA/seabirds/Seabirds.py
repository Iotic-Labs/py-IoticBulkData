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
"""Import DEFRA Seabirds data in Ioticiser style
Designed to be run occassionally (perhaps scheduled with cron) to collect new seabird data from DEFRA
Runs once and then stops as the data is static.
"""

from __future__ import unicode_literals

from datetime import datetime
import logging

logging.basicConfig(format='%(asctime)s,%(msecs)03d %(levelname)s [%(name)s] {%(threadName)s} %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

# handle python2/3 file not found error
try:
    from exceptions import IOError as FileNotFoundError  # pylint: disable=redefined-builtin
except ImportError:
    pass

import os
import sys
import requests

import shapefile
from zipfile import ZipFile


from IoticAgent import Datatypes
from IoticAgent.Core.Validation import Validation
from IoticAgent.Core.Validation import VALIDATION_LID_LEN, VALIDATION_META_LABEL, VALIDATION_META_COMMENT
from IoticAgent.Core.Validation import VALIDATION_TIME_FMT as DATE_ISO_FORMAT

from Ioticiser import SourceBase
from .GeoConvert import OSGB36toWGS84

LANG = 'en'
URL = "http://magic.defra.gov.uk/Datasets/Zip_files/magseabirds_shp.zip"
ZIPFILE_NAME = "seabirds.zip"
SHAPE_BASENAME = "magseabirds"
DATE_FORMAT = "%a, %d %b %Y %H:%M:%S %Z"
# unpack their abbreviations, e.g. "ARKSKUA": "Artic Skua"
BIRD_LOOKUP = {
    'ARCSKUA': "Arctic Skua",
    'ARCTERN': "Arctic Tern",
    'BLACKGUIL': "Black Guillemot",
    'BLKHDGULL': "Black headed Gull",
    'COMICTERN': "Comic Tern",
    'COMMNTERN': "Common Tern",
    'COMMONGUL': "Common Gull",
    'CORMORANT': "Cormorant",
    'FULMAR': "Fulmar",
    'GANNET': "Gannet",
    'GBBGULL': "Greater Black backed Gull",
    'GREATSKUA': "Great Skua",
    'GUILLEMOT': "Guillemot",
    'HERRINGGU': "Herring Gull",
    'KITTIWAKE': "Kittiwake",
    'LBBGULL': "Lesser Black backed Gull",
    'LEACHPETR': "Leach's Petrel",
    'LITTLTERN': "Little Tern",
    'MANXSHEAR': "Manx Shearwater",
    'MEDGULL': "Mediterranean Gull",
    'PUFFIN': "Puffin",
    'RAZORBILL': "Razorbill",
    'ROSTERN': "Roseate Tern",
    'SANDWTERN': "Sandwich Tern",
    'SHAG': "Shag",
    'STORMPETR': "Storm Petrel"
}
FEED_DESCRIPTION = " ".join(BIRD_LOOKUP.values()).split(" ")  # get a list of bird names
FEED_DESCRIPTION = " ".join(list(set(FEED_DESCRIPTION)))  # get a de-duped list of key words for search to find
FEED_DESCRIPTION = FEED_DESCRIPTION[:VALIDATION_META_COMMENT].rstrip()
THING_DESCRIPTION = """
 DEFRA Seabird number counts.  Available under UK Open Government Licence:
 http://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/
""".strip()
FEED_LID = "seabird_numbers"


class Seabirds(SourceBase):

    def __init__(self, stash, config, stop):
        super(Seabirds, self).__init__(stash, config, stop)
        self.__make_public = False
        self.__validate_config()
        self.__thing_limit = self.__get_thing_limit()
        self.__last_mod_get = None

    def run(self):
        """Check all's ok and then only run something if the data from DEFRA is newer than last time
        """
        if self.__get_seabirds_zip():
            self.__run_seabirds()
        else:
            logger.info("Nothing to do - new seabirds data not available")

        logger.info("Finished")

    def __run_seabirds(self):
        """Read through the shapefile treating each new record as a new Iotic Thing
        """
        sf_basename = os.path.join(self._config["datapath"], SHAPE_BASENAME)
        try:
            sf = shapefile.Reader(sf_basename)
        except (FileNotFoundError) as e:
            msg = "Shapefile load failed"
            logger.critical(msg + ": " + str(e))
            return

        fields = sf.fields  # fields are the key names for the data
        shapes = sf.shapes()  # shapes are the geo-location for the records, in this case only a single point

        record_no = 0
        for record in sf.records():
            lid = str(record_no) + ":" + record[0] + "-" + record[1]
            lid = lid[:VALIDATION_LID_LEN].rstrip()
            with self._stash.create_thing(lid) as thing:
                points = shapes[record_no].points  # shapefile points, not Iotic
                self.__update_thing_meta(thing, record, points)
                feed = self.__create_feed(thing)
                self.__share_data(feed, fields, record)
                thing.set_public(public=self.__make_public)
            # check debug limit and stop if exceeded
            record_no += 1
            if record_no >= self.__thing_limit:
                break
            # stop if told to
            if self._stop.is_set():
                break

    def __get_thing_limit(self):
        thing_limit = sys.maxsize
        try:
            thing_limit = int(self._config["limit_things"])
        except KeyError:
            pass  # no limit because not set

        logger.info("thing limit = %s", str(thing_limit))
        return thing_limit

    def __get_seabirds_zip(self):
        """Try to get the zip of the seabirds shapefile and unzip it into the data sub-directory
        """
        try:
            zfile = requests.get(URL)
            zfile.raise_for_status()
        except Exception as e:  # pylint: disable=broad-except
            msg = "Get Seabirds URL failed"
            logger.error(msg + ": " + str(e))
            return False

        try:
            self.__last_mod_get = datetime.strptime(zfile.headers["Last-Modified"], DATE_FORMAT)
        except:
            msg = "Seabirds data unknown last-modified date!  Using epoch!"
            logger.error(msg)
            self.__last_mod_get = datetime(1970, 1, 1)

        logger.debug("Seabirds data found.  Using last modified date of: %s", str(self.__last_mod_get))

        last_mod_stash = None
        try:
            last_mod_str = self._stash.get_property("Last-Modified")
            if last_mod_str is not None:
                last_mod_stash = datetime.strptime(last_mod_str, DATE_ISO_FORMAT)
        except ValueError:  # must be the first time or we would have stashed it before
            pass

        if last_mod_stash is not None:
            # convert to datetime
            if last_mod_stash <= self.__last_mod_get:
                msg = "Seabirds data not changed since last fetch"
                logger.info(msg)
                return False

        #  by here we should have the zip file and be sure it's newer than before
        self._stash.set_property("Last-Modified",
                                 Validation.datetime_check_convert(self.__last_mod_get, to_iso8601=True))

        filename = os.path.join(self._config["datapath"], ZIPFILE_NAME)
        with open(filename, 'wb') as fobj:
            for chunk in zfile.iter_content(1024):
                fobj.write(chunk)

        zipf = ZipFile(filename)
        zipf.extractall(self._config["datapath"])
        return True

    def __validate_config(self):
        if 'datapath' not in self._config:
            msg = "Config requires datapath"
            logger.error(msg)
            raise ValueError(msg)
        if not os.path.exists(self._config["datapath"]):
            msg = "Config datapath does not exist"
            logger.error(msg)
            raise ValueError(msg)

        if 'limit_things' in self._config:
            try:
                _ = int(self._config['limit_things'])  # noqa
            except ValueError:
                msg = "Config limit_things should be an integer"
                logger.error(msg)
                raise ValueError(msg)

        if 'make_public' in self._config:
            self.__make_public = True if self._config['make_public'] == "True" else False

        logger.info("make public %s", self.__make_public)

    def __share_data(self, feed, fields, record):
        """Share data from record using the fields as the keys
        """
        # create all the values
        for i in range(1, len(fields)):
            if fields[i][0] in BIRD_LOOKUP:
                self.__create_bird_value(feed, fields[i][0], record[i - 1])
        # share the feed with the time of last modified
        logger.debug("sharing with time type %s, time %s", type(self.__last_mod_get), self.__last_mod_get)
        feed.share(time=self.__last_mod_get)

    @staticmethod
    def __update_thing_meta(thing, record, points):
        """Fill in the extra metadata for our thing from the shape file details
        """
        # label
        label = "seabird numbers for: " + record[0] + "-" + record[1]
        label = label[:VALIDATION_META_LABEL].rstrip()
        thing.set_label(label, lang=LANG)
        # description
        thing.set_description(THING_DESCRIPTION, lang=LANG)
        # lat, lon
        x1, y1 = points[0]
        lat, lon = OSGB36toWGS84(x1, y1)
        thing.set_location(lat, lon)
        # tags
        coast_inland = record[2]  # coastal or inland site
        thing.create_tag(["seabird", "bird", "defra", coast_inland.lower()])

    @staticmethod
    def __create_feed(thing):
        """Create the seabird numbers feed on the thing.
           Set the metadata for the feed.
           Ask to store 1 recent share
        """
        f_birds = thing.create_feed(FEED_LID)
        f_birds.set_recent_config(max_samples=1)
        f_birds.set_label("Seabird numbers", lang=LANG)
        f_birds.set_description(FEED_DESCRIPTION, lang=LANG)

        return f_birds

    @staticmethod
    def __create_bird_value(feed, name, number):
        """Create the individual values for each bird"""
        feed.create_value(name.lower(), Datatypes.INTEGER, "en", "count of " + BIRD_LOOKUP[name], data=number)
