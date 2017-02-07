# Copyright (c) 2017 Iotic Labs Ltd. All rights reserved.
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

import logging
logger = logging.getLogger(__name__)

from IoticAgent.Core.Validation import Validation
from IoticAgent.Core.Const import R_FEED, R_CONTROL

from .ResourceBase import ResourceBase
from .Point import Point
from .const import PUBLIC, LOCATION
from .const import FOC, LABELS, DESCRIPTIONS, TAGS, VALUES


class Thing(ResourceBase):

    def __init__(self, lid, new=False, stash=None, public=None, labels=None,
                 descriptions=None, tags=None, points=None, lat=None, long=None):  # pylint: disable=redefined-builtin
        """
        # Note labels & descriptions: dict like {'en': 'blah', 'fr': 'chips'}
        # Note points dict = stash format
        """
        super(Thing, self).__init__(lid, new=new, labels=labels, descriptions=descriptions, tags=tags)
        self.__stash = stash
        self.__public = Validation.bool_check_convert('public', public)  # Note: bool(None) == False
        self.__lat = None
        self.__long = None
        if lat is not None and long is not None:
            Validation.location_check(lat, long)
            self.__lat = lat
            self.__long = long
        self.__points = {}
        if points is not None and len(points):
            for pid, pdata in points.items():
                self.__points[pid] = Point(pdata[FOC], pid,
                                           labels=pdata[LABELS],
                                           descriptions=pdata[DESCRIPTIONS],
                                           tags=pdata[TAGS],
                                           values=pdata[VALUES])

    def __enter__(self):
        self.lock.acquire()
        return self

    def __exit__(self, typ, value, traceback):
        self.lock.release()
        if self.__stash is not None:
            try:
                self.__stash._finalise_thing(self)
            except:
                logger.exception("BUG! Thing __exit__ crashed on finalise_thing attempt")

    def apply_changes(self):
        with self.lock:
            for pid in self.__points:
                self.__points[pid].apply_changes()
            self.__new = False
            self._changes = []

    def set_public(self, public=True):
        with self.lock:
            res = Validation.bool_check_convert('public', public)
            if res != self.__public and PUBLIC not in self._changes:
                self._changes.append(PUBLIC)
            self.__public = res

    @property
    def public(self):
        with self.lock:
            return self.__public

    def set_location(self, lat, long):  # pylint: disable=redefined-builtin
        with self.lock:
            Validation.location_check(lat, long)
            if self.__lat != lat or self.__long != long:
                if LOCATION not in self._changes:
                    self._changes.append(LOCATION)
            self.__lat = lat
            self.__long = long

    @property
    def location(self):
        with self.lock:
            return self.__lat, self.__long

    def create_point(self, foc, pid):
        with self.lock:
            if pid not in self.__points:
                self.__points[pid] = Point(foc, pid, new=True)
            return self.__points[pid]

    def create_feed(self, pid):
        return self.create_point(R_FEED, pid)

    def create_control(self, pid):
        return self.create_point(R_CONTROL, pid)

    @property
    def points(self):
        with self.lock:
            return self.__points
