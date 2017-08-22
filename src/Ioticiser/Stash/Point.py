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

from IoticAgent.Core.Validation import Validation

from .ResourceBase import ResourceBase
from .const import VALUE, VALUESHARE, VTYPE, LANG, DESCRIPTION, UNIT, SHARETIME, SHAREDATA, RECENT


class Point(ResourceBase):

    __share_time_fmt = '%Y-%m-%dT%H:%M:%S.%fZ'

    def __init__(self, foc, pid, new=False, labels=None, descriptions=None, tags=None, values=None, max_samples=0):
        super(Point, self).__init__(pid, new=new, labels=labels, descriptions=descriptions, tags=tags)
        self.__foc = foc
        self.__pid = pid
        self.__values = {} if values is None else values
        self.__sharetime = None
        self.__sharedata = None
        self.__max_samples = max_samples

    def clear_changes(self):
        with self.lock:
            self._changes = []
            self._set_not_new()

    @property
    def foc(self):
        with self.lock:
            return self.__foc

    def create_value(self, label, vtype=None, lang=None, description=None, unit=None, data=None):
        """
        If vtype is not specified then the value (lang, description & unit are ignored)
        data can be specified on it's own
        """
        label = Validation.label_check_convert(label)
        if vtype is not None:
            vtype = Validation.value_type_check_convert(vtype)
            lang = Validation.lang_check_convert(lang, allow_none=True)
            description = Validation.comment_check_convert(description, allow_none=True)
            unit = unit
        if vtype is None and data is None:
            raise AttributeError("create_value with no vtype and no data!")
        with self.lock:
            try:
                value = self.__values[label]
            except KeyError:
                value = self.__values[label] = {}

            if vtype is not None:
                new_value = {VTYPE: vtype,
                             LANG: lang,
                             DESCRIPTION: description,
                             UNIT: unit}
                if new_value != value:
                    value.update(new_value)
                    if VALUE + label not in self._changes:
                        logger.debug('Value %s has changed', label)
                        self._changes.append(VALUE + label)

            if data is not None:
                value[SHAREDATA] = data
                if VALUESHARE + label not in self._changes:
                    logger.debug('Sharing value data for %s', label)
                    self._changes.append(VALUESHARE + label)

    @property
    def values(self):
        with self.lock:
            return self.__values

    def share(self, data=None, time=None):
        if data is None and time is None:
            raise ValueError("kwarg data or time required.")
        with self.lock:
            if time is not None:
                self.__sharetime = Validation.datetime_check_convert(time, allow_none=True)
                if SHARETIME not in self._changes:
                    self._changes.append(SHARETIME)
            if data is not None:
                self.__sharedata = data
                if SHAREDATA not in self._changes:
                    self._changes.append(SHAREDATA)

    @property
    def sharetime(self):
        with self.lock:
            return self.__sharetime

    @property
    def sharedata(self):
        with self.lock:
            return self.__sharedata

    def set_recent_config(self, max_samples=0):
        with self.lock:
            if max_samples != self.__max_samples:
                self.__max_samples = max_samples
                if RECENT not in self._changes:
                    self._changes.append(RECENT)

    @property
    def recent_config(self):
        with self.lock:
            return self.__max_samples
