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

import logging
logger = logging.getLogger(__name__)

from os import rename
from os.path import split as path_split, splitext, exists
from threading import Thread
from copy import deepcopy
from hashlib import md5
from gzip import open as gzip_open
import json
import ubjson

from IoticAgent.Core.compat import RLock, Event, number_types, string_types

from .Thing import Thing
from .ThreadPool import ThreadPool
from .const import THINGS, DIFF, DIFFCOUNT
from .const import LID, PID, FOC, PUBLIC, TAGS, LOCATION, POINTS, LAT, LONG, VALUES
from .const import LABEL, LABELS, DESCRIPTION, DESCRIPTIONS, RECENT
from .const import VALUE, VALUESHARE, VTYPE, LANG, UNIT, SHAREDATA, SHARETIME


SAVETIME = 120


class Stash(object):  # pylint: disable=too-many-instance-attributes

    @classmethod
    def __fname_to_name(cls, fname):
        return splitext(path_split(fname)[-1])[0]

    def __init__(self, fname, iotclient, num_workers):
        self.__fname = fname
        self.__name = self.__fname_to_name(fname)
        self.__workers = ThreadPool(self.__name, num_workers=num_workers, iotclient=iotclient)
        self.__thread = Thread(target=self.__run, name=('stash-%s' % self.__name))
        self.__stop = Event()

        self.__stash = None
        self.__stash_lock = RLock()
        self.__stash_hash = None

        self.__pname = splitext(self.__fname)[0] + '_props.json'
        self.__properties = None
        self.__properties_changed = False

        self.__load()

    def start(self):
        self.__workers.start()
        self.__submit_diffs()
        self.__thread.start()

    def stop(self):
        if not self.__stop.is_set():
            self.__stop.set()
            self.__thread.join()
            self.__workers.stop()
            self.__save()

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, typ, value, traceback):
        self.stop()

    def is_alive(self):
        return self.__thread.is_alive()

    def __load(self):  # pylint: disable=too-many-branches
        fsplit = splitext(self.__fname)
        if fsplit[1] == '.json':
            if exists(self.__fname):
                # Migrate from json to ubjson
                with self.__stash_lock:
                    with open(self.__fname, 'r') as f:
                        self.__stash = json.loads(f.read())
                    rename(self.__fname, self.__fname + '.old')

        if fsplit[1] != '.ubjz':
            self.__fname = fsplit[0] + '.ubjz'

        if exists(self.__fname):
            with self.__stash_lock:
                with gzip_open(self.__fname, 'rb') as f:
                    self.__stash = ubjson.loadb(f.read())
        elif self.__stash is None:
            self.__stash = {THINGS: {},    # Current/last state of Things
                            DIFF: {},      # Diffs not yet updated in Iotic Space
                            DIFFCOUNT: 0}  # Diff counter

        if not exists(self.__pname):
            self.__properties = {}
        else:
            with self.__stash_lock:
                with open(self.__pname, 'r') as f:
                    self.__properties = json.loads(f.read())

        with self.__stash_lock:
            stash_copy = deepcopy(self.__stash)
            self.__stash = {}
            # Migrate built-in keys
            for key, value in stash_copy.items():
                if key in [THINGS, DIFF, DIFFCOUNT]:
                    logger.debug("--> Migrating built-in %s", key)
                    self.__stash[key] = stash_copy[key]
            # Migrate bad keys
            for key, value in stash_copy.items():
                if key not in [THINGS, DIFF, DIFFCOUNT]:
                    if key not in stash_copy[THINGS]:
                        logger.info("--> Migrating key to THINGS %s", key)
                        self.__stash[THINGS][key] = value
                        self.__stash.pop(key, None)
            # Remove redundant LAT/LONG (LOCATION used instead)
            for el, et in self.__stash[THINGS].items():  # pylint: disable=unused-variable
                et.pop(LAT, None)
                et.pop(LONG, None)

        self.__save()

    def __calc_stashdump(self):
        with self.__stash_lock:
            stashdump = ubjson.dumpb(self.__stash)
            m = md5()
            m.update(stashdump)
            stashhash = m.hexdigest()
            if self.__stash_hash != stashhash:
                self.__stash_hash = stashhash
                return stashdump
            return None

    def __save(self):
        stashdump = self.__calc_stashdump()
        if stashdump is not None:
            with gzip_open(self.__fname, 'wb') as f:
                f.write(stashdump)

        if len(self.__properties) and self.__properties_changed:
            with self.__stash_lock:
                with open(self.__pname, 'w') as f:
                    json.dump(self.__properties, f)

    def get_property(self, key):
        with self.__stash_lock:
            if not isinstance(key, string_types):
                raise ValueError("key must be string")
            if key in self.__properties:
                return self.__properties[key]
            return None

    def set_property(self, key, value=None):
        with self.__stash_lock:
            if not isinstance(key, string_types):
                raise ValueError("key must be string")
            if value is None and key in self.__properties:
                del self.__properties[key]
            if value is not None:
                if isinstance(value, string_types) or isinstance(value, number_types):
                    if key not in self.__properties or self.__properties[key] != value:
                        self.__properties_changed = True
                        self.__properties[key] = value
                else:
                    raise ValueError("value must be string or int")

    def __run(self):
        logger.info("Started.")
        while not self.__stop.is_set():
            self.__save()
            self.__stop.wait(timeout=SAVETIME)

    def create_thing(self, lid):
        if lid in self.__stash[THINGS]:
            thing = Thing(lid,
                          stash=self,
                          public=self.__stash[THINGS][lid][PUBLIC],
                          labels=self.__stash[THINGS][lid][LABELS],
                          descriptions=self.__stash[THINGS][lid][DESCRIPTIONS],
                          tags=self.__stash[THINGS][lid][TAGS],
                          points=self.__stash[THINGS][lid][POINTS],
                          lat=self.__stash[THINGS][lid][LOCATION][0],
                          long=self.__stash[THINGS][lid][LOCATION][1])
            return thing
        return Thing(lid, new=True, stash=self)

    def __calc_diff(self, thing):  # pylint: disable=too-many-branches
        if not len(thing.changes):
            changes = 0
            for pid, point in thing.points.items():
                changes += len(point.changes)
            if changes == 0:
                return None, None

        ret = 0
        diff = {}
        if thing.new:
            # Note: thing is new so no need to calculate diff.
            #  This shows the diff dict full layout
            diff = {LID: thing.lid,
                    TAGS: thing.tags,
                    LOCATION: thing.location,
                    LABELS: thing.labels,
                    DESCRIPTIONS: thing.descriptions,
                    POINTS: {}}
            # Prevent public setting to always be performed for new things
            if PUBLIC in thing.changes:
                diff[PUBLIC] = thing.public

            for pid, point in thing.points.items():
                diff[POINTS][pid] = self.__calc_diff_point(point)

        else:
            diff[LID] = thing.lid
            diff[POINTS] = {}
            for change in thing.changes:
                if change == PUBLIC:
                    diff[PUBLIC] = thing.public
                elif change == TAGS:
                    diff[TAGS] = thing.tags
                elif change.startswith(LABEL):
                    if LABELS not in diff:
                        diff[LABELS] = {}
                    lang = change.replace(LABEL, '')
                    diff[LABELS][lang] = thing.labels[lang]
                elif change.startswith(DESCRIPTION):
                    if DESCRIPTIONS not in diff:
                        diff[DESCRIPTIONS] = {}
                    lang = change.replace(DESCRIPTION, '')
                    diff[DESCRIPTIONS][lang] = thing.descriptions[lang]
                elif change == LOCATION:
                    diff[LOCATION] = thing.location
            for pid, point in thing.points.items():
                diff[POINTS][pid] = self.__calc_diff_point(point)

        with self.__stash_lock:
            self.__stash[DIFF][str(self.__stash[DIFFCOUNT])] = diff
            ret = self.__stash[DIFFCOUNT]
            self.__stash[DIFFCOUNT] += 1
        return ret, diff

    def __calc_diff_point(self, point):
        ret = {PID: point.lid,
               FOC: point.foc,
               VALUES: {}}
        if point.new:
            ret.update({LABELS: {},
                        DESCRIPTIONS: {},
                        RECENT: 0,
                        TAGS: []})
        for change in point.changes:
            if change == TAGS:
                ret[TAGS] = point.tags
            elif change.startswith(LABEL):
                if LABELS not in ret:
                    ret[LABELS] = {}
                lang = change.replace(LABEL, '')
                ret[LABELS][lang] = point.labels[lang]
            elif change.startswith(DESCRIPTION):
                if DESCRIPTIONS not in ret:
                    ret[DESCRIPTIONS] = {}
                lang = change.replace(DESCRIPTION, '')
                ret[DESCRIPTIONS][lang] = point.descriptions[lang]
            elif change == RECENT:
                ret[RECENT] = point.recent_config
            elif change == SHAREDATA:
                ret[SHAREDATA] = point.sharedata
            elif change == SHARETIME:
                ret[SHARETIME] = point.sharetime
            elif change.startswith(VALUE):
                label = change.replace(VALUE, '')
                ret[VALUES][label] = self.__calc_value(point.values[label])
            # applicable only if no value attributes have changed (share only)
            elif change.startswith(VALUESHARE):
                label = change.replace(VALUESHARE, '')
                if label not in ret[VALUES]:
                    ret[VALUES][label] = {}
                ret[VALUES][label].update({SHAREDATA: point.values[label].pop(SHAREDATA)})
        return ret

    @classmethod
    def __calc_value(cls, value):
        ret = {}
        if VTYPE in value:
            ret = {VTYPE: value[VTYPE],
                   LANG: value[LANG],
                   DESCRIPTION: value[DESCRIPTION],
                   UNIT: value[UNIT]}
        if SHAREDATA in value:
            ret[SHAREDATA] = value[SHAREDATA]
        return ret

    def __submit_diffs(self):
        """On start resubmit any diffs in the stash
        """
        with self.__stash_lock:
            for idx, diff in self.__stash[DIFF].items():
                logger.info("Resubmitting diff for thing %s", diff[LID])
                self.__workers.submit(diff[LID], idx, diff, self.__complete_cb)

    def _finalise_thing(self, thing):
        with thing.lock:
            idx, diff = self.__calc_diff(thing)
            if idx is not None:
                self.__workers.submit(diff[LID], idx, diff, self.__complete_cb)
                thing.clear_changes()

    def __complete_cb(self, lid, idx):
        with self.__stash_lock:
            idx = str(idx)
            diff = self.__stash[DIFF][idx]
            try:
                thing = self.__stash[THINGS][lid]
            except KeyError:
                thing = self.__stash[THINGS][lid] = {PUBLIC: False,
                                                     LABELS: {},
                                                     DESCRIPTIONS: {},
                                                     TAGS: [],
                                                     POINTS: {},
                                                     LOCATION: (None, None)}

            empty = {}
            # Updated later separately
            points = diff.pop(POINTS, empty)
            # Have to be merged since update only affects subset of all labels/descriptions
            for item in (LABELS, DESCRIPTIONS):
                thing[item].update(diff.pop(item, empty))
            # Rest should be OK to replace (public, tags, location)
            thing.update(diff)

            # Points
            for pid, pdiff in points.items():
                try:
                    point = thing[POINTS][pid]
                except KeyError:
                    thing[POINTS][pid] = point = {PID: pid,
                                                  VALUES: {},
                                                  LABELS: {},
                                                  DESCRIPTIONS: {},
                                                  TAGS: []}
                # Updated later separately
                values = pdiff.pop(VALUES, empty)
                # Remove sharedata, sharetime before applying to stash
                for item in (SHAREDATA, SHARETIME):
                    pdiff.pop(item, None)
                # Have to be merged since update only affects subset of all labels/descriptions
                for item in (LABELS, DESCRIPTIONS):
                    point[item].update(pdiff.pop(item, empty))
                # Rest should be OK to replace (tags, foc, recent, share time, data)
                point.update(pdiff)

                # Values
                for label, value in values.items():
                    # Don't remember value share data
                    value.pop(SHAREDATA, None)
                    try:
                        # Might only have data set so must merge
                        point[VALUES][label].update(value)
                    except KeyError:
                        point[VALUES][label] = value

            del self.__stash[DIFF][idx]

    @property
    def queue_empty(self):
        return self.__workers.queue_empty
