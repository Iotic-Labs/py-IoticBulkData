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

from os import getpid, kill
from threading import Thread, local as thread_local
from datetime import datetime
from collections import namedtuple, deque
import logging
logger = logging.getLogger(__name__)

from IoticAgent.Core.compat import Queue, Empty, Event, Lock, string_types
from IoticAgent.Core.Const import R_FEED, R_CONTROL
from IoticAgent.Core.Exceptions import LinkException
from IoticAgent.IOT.Exceptions import IOTAccessDenied

from ..compat import SIGUSR1
from .const import FOC, PUBLIC, TAGS, LOCATION, POINTS, THING, RECENT
from .const import LABELS, DESCRIPTIONS, VALUES
from .const import DESCRIPTION, VTYPE, LANG, UNIT, SHAREDATA, SHARETIME


DEBUG_ENABLED = logger.getEffectiveLevel() == logging.DEBUG


class Message(namedtuple('nt_Message', 'lid idx diff complete_cb')):
    """Represent an individual queue message to handle"""
    pass


class LidSerialisedQueue(object):
    """Thread-safe queue which ensures enqueued Messages for the same lid are not handled by multiple threads at the
    same time."""

    def __init__(self):
        self.__queue = Queue()
        self.__lock = Lock()
        # Mapping of LID to deque (so can serialise messages for same LID). Appended to right, removed from left.
        self.__lid_mapping = {}
        self.__local = thread_local()
        self.__new_msg = Event()

    def thread_init(self):
        """Must be called in each thread which is to use this instance, before using get()!"""
        # LID which is being processed by this thread, if any
        self.__local.own_lid = None

    @property
    def empty(self):
        return not self.__lid_mapping and self.__queue.empty()

    def put(self, qmsg):
        if not isinstance(qmsg, Message):
            raise ValueError
        self.__queue.put(qmsg)
        self.__new_msg.set()

    def __get_for_current_lid(self):
        """Returns next message for same LID as previous message, if available. None otherwise. MUST be called within
        lock!
        """
        local = self.__local
        try:
            return self.__lid_mapping[local.own_lid].popleft()
        # No messages left for this LID (deque.popleft), remove LID association
        except IndexError:
            del self.__lid_mapping[local.own_lid]
            local.own_lid = None
        # No LIDs being processed (mapping)
        except KeyError:
            pass

        return None

    def get(self, timeout=None):
        """Raises queue.Empty exception if no messages are available after timeout"""
        with self.__lock:
            msg = self.__get_for_current_lid()

            if not msg:
                queue = self.__queue
                lid_mapping = self.__lid_mapping

                while True:
                    # Instead of blocking on get(), release lock so other threads have a chance to request existing lid
                    # messages (above, via __get_for_current_lid).
                    if not queue.qsize() and timeout:
                        self.__new_msg.clear()
                        try:
                            self.__lock.release()
                            self.__new_msg.wait(timeout)
                        finally:
                            self.__lock.acquire()
                    msg = queue.get_nowait()
                    # Enqueue message with LID already being dealt with in LID-specific queue, otherwise can process
                    # oneself.
                    if msg.lid in lid_mapping:
                        lid_mapping[msg.lid].append(msg)
                    else:
                        # Currently nobody else is processing messages with this LID, so can use oneself
                        self.__local.own_lid = msg.lid
                        lid_mapping[msg.lid] = deque()
                        break

        return msg


class ThreadPool(object):  # pylint: disable=too-many-instance-attributes

    __share_time_fmt = '%Y-%m-%dT%H:%M:%S.%fZ'

    def __init__(self, name, num_workers=1, iotclient=None, daemonic=False):
        self.__name = name
        self.__num_workers = num_workers
        self.__iotclient = iotclient
        self.__daemonic = daemonic
        #
        self.__queue = LidSerialisedQueue()
        self.__stop = Event()
        self.__stop.set()
        self.__threads = []
        self.__cache = {}

    def start(self):
        if self.__stop.is_set():
            self.__stop.clear()
            for i in range(0, self.__num_workers):
                thread = Thread(target=self.__worker, name=('tp-%s-%d' % (self.__name, i)))
                thread.daemon = self.__daemonic
                self.__threads.append(thread)
            for thread in self.__threads:
                thread.start()

    def submit(self, lid, idx, diff, complete_cb=None):
        self.__queue.put(Message(lid, idx, diff, complete_cb))

    def stop(self):
        if not self.__stop.is_set():
            self.__stop.set()
            for thread in self.__threads:
                thread.join()
            del self.__threads[:]

    @property
    def queue_empty(self):
        return self.__queue.empty

    def __worker(self):
        logger.debug("Starting")
        self.__queue.thread_init()
        stop_is_set = self.__stop.is_set
        queue_get = self.__queue.get
        handle_thing_changes = self.__handle_thing_changes

        while not stop_is_set():
            try:
                qmsg = queue_get(timeout=.25)
            except Empty:
                continue  # queue.get timeout ignore

            while True:
                try:
                    handle_thing_changes(qmsg.lid, qmsg.diff)
                except LinkException:
                    logger.warning("Network error, will retry lid '%s'", qmsg.lid)
                    self.__stop.wait(timeout=1)
                    continue
                except IOTAccessDenied:
                    logger.critical("IOTAccessDenied - Local limit exceeded - Aborting")
                    kill(getpid(), SIGUSR1)
                    return
                except:
                    logger.error("Failed to process thing changes (Uncaught exception)  - Aborting",
                                 exc_info=DEBUG_ENABLED)
                    kill(getpid(), SIGUSR1)
                    return
                break

            logger.debug("completed thing %s", qmsg.lid)
            if qmsg.complete_cb:
                try:
                    qmsg.complete_cb(qmsg.lid, qmsg.idx)
                except:
                    logger.error("complete_cb failed for %s", qmsg.lid, exc_info=DEBUG_ENABLED)
                    kill(getpid(), SIGUSR1)
                    return

    @classmethod
    def __lang_convert(cls, lang):
        if lang == '':
            return None
        return lang

    def __handle_thing_changes(self, lid, diff):  # pylint: disable=too-many-branches
        if lid not in self.__cache:
            self.__cache[lid] = {
                THING: self.__iotclient.create_thing(lid),
                POINTS: {}
            }
        iotthing = self.__cache[lid][THING]

        if PUBLIC in diff and diff[PUBLIC] is False:
            iotthing.set_public(False)

        thingmeta = None
        for chg, val in diff.items():
            if chg == TAGS and len(val):
                iotthing.create_tag(val)
            elif chg == LABELS and val:
                if thingmeta is None:
                    thingmeta = iotthing.get_meta()
                for lang, label in val.items():
                    thingmeta.set_label(label, lang=self.__lang_convert(lang))
            elif chg == DESCRIPTIONS and val:
                if thingmeta is None:
                    thingmeta = iotthing.get_meta()
                for lang, description in val.items():
                    thingmeta.set_description(description, lang=self.__lang_convert(lang))
            elif chg == LOCATION and val[0] is not None:
                if thingmeta is None:
                    thingmeta = iotthing.get_meta()
                thingmeta.set_location(val[0], val[1])
        if thingmeta is not None:
            thingmeta.set()

        for pid, pdiff in diff[POINTS].items():
            self.__handle_point_changes(iotthing, lid, pid, pdiff)

        if PUBLIC in diff and diff[PUBLIC] is True:
            iotthing.set_public(True)

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
            elif chg == LABELS and val:
                if pointmeta is None:
                    pointmeta = iotpoint.get_meta()
                for lang, label in val.items():
                    pointmeta.set_label(label, lang=self.__lang_convert(lang))
            elif chg == DESCRIPTIONS and val:
                if pointmeta is None:
                    pointmeta = iotpoint.get_meta()
                for lang, description in val.items():
                    pointmeta.set_description(description, lang=self.__lang_convert(lang))
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
