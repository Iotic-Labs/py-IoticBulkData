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

from os.path import split as path_split, splitext, exists
from threading import Thread
import json

from IoticAgent.Core.compat import RLock, Event, monotonic, number_types, string_types

from .Thing import Thing
from .ThreadPool import ThreadPool
from .const import THINGS, DIFF, DIFFCOUNT
from .const import LID, PID, FOC, PUBLIC, TAGS, LOCATION, POINTS, LAT, LONG, VALUES
from .const import LABEL, LABELS, DESCRIPTION, DESCRIPTIONS, RECENT
from .const import VALUE, VTYPE, LANG, UNIT, SHAREDATA, SHARETIME


SAVETIME = 30


class Stash(object):  # pylint: disable=too-many-instance-attributes

    @classmethod
    def __fname_to_name(cls, fname):
        return splitext(path_split(fname)[-1])[0]

    def __init__(self, fname, iotclient, num_workers):
        self.__fname = fname
        self.__name = self.__fname_to_name(fname)
        self.__workers = ThreadPool(self.__name, num_workers=num_workers, iotclient=iotclient)
        self.__thread = Thread(target=self.__run, name=('stash-%s' % self.__name))

        self.__stash = None
        self.__stash_lock = RLock()
        self.__stop = Event()
        self.__pname = self.__fname.replace('.json', '_props.json')  # todo: hack?
        self.__properties = None

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

    def is_alive(self):
        return self.__thread.is_alive()

    def __load(self):
        if not exists(self.__fname):
            with open(self.__fname, 'w') as f:
                self.__stash = {THINGS: {},   # Current/last state of Things
                                DIFF: {},     # Diffs not yet updated in Iotic Space
                                DIFFCOUNT: 0  # Diff counter
                               }  # noqa (indent)
                f.write(json.dumps(self.__stash))
        else:
            with self.__stash_lock:
                with open(self.__fname, 'r') as f:
                    self.__stash = json.loads(f.read())
        if not exists(self.__pname):
            self.__properties = {}
        else:
            with self.__stash_lock:
                with open(self.__pname, 'r') as f:
                    self.__properties = json.loads(f.read())

    def __save(self):
        with self.__stash_lock:
            with open(self.__fname, 'w') as f:
                f.write(json.dumps(self.__stash))
            if len(self.__properties):
                with open(self.__pname, 'w') as f:
                    f.write(json.dumps(self.__properties))

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
                    self.__properties[key] = value
                else:
                    raise ValueError("value must be string or int")
            self.__save()

    def __run(self):
        logger.info("Started.")
        lasttime = monotonic()
        while not self.__stop.is_set():
            if monotonic() - lasttime > SAVETIME:
                self.__save()
                lasttime = monotonic()
            self.__stop.wait(timeout=0.25)
        self.__save()

    def create_thing(self, lid, apply_diff=True):
        if lid in self.__stash:
            thing = Thing(lid,
                          stash=self,
                          public=self.__stash[lid][PUBLIC],
                          labels=self.__stash[lid][LABELS],
                          descriptions=self.__stash[lid][DESCRIPTIONS],
                          tags=self.__stash[lid][TAGS],
                          points=self.__stash[lid][POINTS],
                          lat=self.__stash[lid][LAT],
                          long=self.__stash[lid][LONG])
            if apply_diff:
                pass
                # TODO: create_thing called again but diffs in stash, apply them ??
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
                    PUBLIC: thing.public,
                    TAGS: thing.tags,
                    LOCATION: thing.location,
                    LABELS: thing.labels,
                    DESCRIPTIONS: thing.descriptions,
                    POINTS: {}}
            for pid, point in thing.points.items():
                diff[POINTS][pid] = {PID: point.lid,
                                     FOC: point.foc,
                                     TAGS: point.tags,
                                     LABELS: point.labels,
                                     DESCRIPTIONS: point.descriptions,
                                     RECENT: point.recent_config,
                                     VALUES: {}}
                if point.sharetime is not None:
                    diff[POINTS][pid][SHARETIME] = point.sharetime
                if point.sharedata is not None:
                    diff[POINTS][pid][SHAREDATA] = point.sharedata

                for label, value in point.values.items():
                    diff[POINTS][pid][VALUES][label] = self.__calc_value(value)

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
            self.__stash[DIFF][self.__stash[DIFFCOUNT]] = diff
            ret = self.__stash[DIFFCOUNT]
            self.__stash[DIFFCOUNT] += 1
        return ret, diff

    def __calc_diff_point(self, point):
        ret = {PID: point.lid,
               FOC: point.foc,
               LABELS: {},
               DESCRIPTIONS: {},
               TAGS: [],
               VALUES: {}}
        for change in point.changes:
            if change == TAGS:
                ret[TAGS] = point.tags
            elif change.startswith(LABEL):
                lang = change.replace(LABEL, '')
                ret[LABELS][lang] = point.labels[lang]
            elif change.startswith(DESCRIPTION):
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
                thing.apply_changes()

    def __complete_cb(self, lid, idx):
        with self.__stash_lock:
            diff = self.__stash[DIFF][idx]
            if lid not in self.__stash:
                self.__stash[lid] = {PUBLIC: False,
                                     LABELS: {},
                                     DESCRIPTIONS: {},
                                     TAGS: [],
                                     POINTS: {},
                                     LAT: None,
                                     LONG: None}
            self.__stash[lid].update(diff)
            del self.__stash[DIFF][idx]

    @property
    def queue_empty(self):
        return self.__workers.queue_empty
