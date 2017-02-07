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

from threading import Thread
from datetime import datetime
import logging
logger = logging.getLogger(__name__)

from IoticAgent.Core.compat import Queue, Empty, Event, Lock, string_types
from IoticAgent.Core.Const import R_FEED, R_CONTROL
from IoticAgent.Core.Exceptions import LinkException

from .const import LID, FOC, PUBLIC, TAGS, LOCATION, POINTS, THING, RECENT
from .const import LABELS, DESCRIPTIONS, VALUES
from .const import DESCRIPTION, VTYPE, LANG, UNIT, SHAREDATA, SHARETIME
from .const import DIFF, IDX, COMPLETE_CB


DEBUG_ENABLED = logger.getEffectiveLevel() == logging.DEBUG


class ThreadPool(object):  # pylint: disable=too-many-instance-attributes

    __share_time_fmt = '%Y-%m-%dT%H:%M:%S.%fZ'

    def __init__(self, name, num_workers=1, iotclient=None, daemonic=False):
        self.__name = name
        self.__num_workers = num_workers
        self.__iotclient = iotclient
        self.__daemonic = daemonic
        #
        self.__queue = Queue()
        self.__stop = Event()
        self.__stop.set()
        self.__lock = Lock()
        self.__threads = []
        self.__cache = {}

    def start(self):
        if self.__stop.is_set():
            self.__stop.clear()
            for i in range(0, self.__num_workers):
                thread = Thread(target=self.__worker, name=('tp-%s-%d' % (self.__name, i)), args=(i,))
                thread.daemon = self.__daemonic
                self.__threads.append(thread)
            for thread in self.__threads:
                thread.start()

    def submit(self, lid, idx, diff, complete_cb=None):
        with self.__lock:
            self.__queue.put({LID: lid, IDX: idx, DIFF: diff, COMPLETE_CB: complete_cb})

    def stop(self):
        if not self.__stop.is_set():
            self.__stop.set()
            for thread in self.__threads:
                thread.join()
            del self.__threads[:]

    @property
    def queue_empty(self):
        return self.__queue.empty()

    def __worker(self, num):
        logger.info("Started.")
        stop_is_set = self.__stop.is_set
        queue_get = self.__queue.get
        queue_task_done = self.__queue.task_done

        while not stop_is_set():
            try:
                qmsg = queue_get(timeout=0.2)
            except Empty:
                continue  # queue.get timeout ignore

            try:
                lid = qmsg[LID]
                idx = qmsg[IDX]
                diff = qmsg[DIFF]
                complete_cb = qmsg[COMPLETE_CB]
            except:
                logger.warning("worker %i failed to get diff from queue!", num)
            finally:
                logger.debug("worker %i got thing lid %s idx %s", num, lid, idx)
                queue_task_done()

            complete = True
            try:
                self.__handle_thing_changes(lid, diff)
            except LinkException:
                logger.warning("Network error, resubmitting lid '%s' to the queue", lid)
                self.submit(lid, idx, diff, complete_cb=complete_cb)
                complete = False
            except:
                logger.exception("BUG! worker %i failed to process thing changes!", num)
                complete = False

            if complete:
                logger.info("worker %i completed thing %s", num, lid)
                if complete_cb is not None:
                    try:
                        complete_cb(lid, idx)
                    except:
                        logger.exception("BUG! worker %i complete_cb failed", num)

    def __handle_thing_changes(self, lid, diff):  # pylint: disable=too-many-branches
        if lid not in self.__cache:
            self.__cache[lid] = {
                THING: self.__iotclient.create_thing(lid),
                POINTS: {}
            }
        iotthing = self.__cache[lid][THING]
        thingmeta = None
        for chg, val in diff.items():
            if chg == PUBLIC:
                iotthing.set_public(val)
            elif chg == TAGS and len(val):
                iotthing.create_tag(val)
            elif chg == LABELS:
                if thingmeta is None:
                    thingmeta = iotthing.get_meta()
                for lang, label in val.items():
                    thingmeta.set_label(label, lang=lang)
            elif chg == DESCRIPTIONS:
                if thingmeta is None:
                    thingmeta = iotthing.get_meta()
                for lang, description in val.items():
                    thingmeta.set_description(description, lang=lang)
            elif chg == LOCATION and val[0] is not None:
                if thingmeta is None:
                    thingmeta = iotthing.get_meta()
                thingmeta.set_location(val[0], val[1])
        if thingmeta is not None:
            thingmeta.set()

        for pid, pdiff in diff[POINTS].items():
            self.__handle_point_changes(iotthing, lid, pid, pdiff)

    def __handle_point_changes(self, iotthing, lid, pid, pdiff):  # pylint: disable=too-many-branches
        if pid not in self.__cache[lid][POINTS]:
            if pdiff[FOC] == R_FEED:
                iotpoint = iotthing.create_feed(pid)
            elif pdiff[FOC] == R_CONTROL:
                iotpoint = iotthing.create_control(pid)
            self.__cache[lid][POINTS][pid] = iotpoint
        iotpoint = self.__cache[lid][POINTS][pid]
        pointmeta = None

        for chg, val in pdiff.items():
            if chg == TAGS and len(val):
                iotpoint.create_tag(val)
            elif chg == RECENT:
                iotpoint.set_recent_config(max_samples=pdiff[RECENT])
            elif chg == LABELS:
                if pointmeta is None:
                    pointmeta = iotpoint.get_meta()
                for lang, label in val.items():
                    pointmeta.set_label(label, lang=lang)
            elif chg == DESCRIPTIONS:
                if pointmeta is None:
                    pointmeta = iotpoint.get_meta()
                for lang, description in val.items():
                    pointmeta.set_description(description, lang=lang)
        if pointmeta is not None:
            pointmeta.set()

        sharedata = {}
        for label, vdiff in pdiff[VALUES].items():
            if SHAREDATA in vdiff:
                sharedata[label] = vdiff[SHAREDATA]
            self.__handle_value_changes(lid, pid, label, vdiff)

        sharetime = None
        if SHARETIME in pdiff:
            sharetime = pdiff[SHARETIME]
            if isinstance(sharetime, string_types):
                try:
                    sharetime = datetime.strptime(sharetime, self.__share_time_fmt)
                except:
                    logger.warning("Failed to make datetime from time string '%s' !Will use None!", sharetime)
                    sharetime = None

        if len(sharedata):
            iotpoint.share(data=sharedata, time=sharetime)

        if SHAREDATA in pdiff:
            iotpoint.share(data=pdiff[SHAREDATA], time=sharetime)

    def __handle_value_changes(self, lid, pid, label, vdiff):
        """
        Note: remove & add values if changed, share data if data
        """
        iotpoint = self.__cache[lid][POINTS][pid]
        if VTYPE in vdiff and vdiff[VTYPE] is not None:
            iotpoint.create_value(label,
                                  vdiff[VTYPE],
                                  lang=vdiff[LANG],
                                  description=vdiff[DESCRIPTION],
                                  unit=vdiff[UNIT])
