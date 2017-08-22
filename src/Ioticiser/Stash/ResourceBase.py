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
"""Wrapper object for Iotic resources
"""

from __future__ import unicode_literals

from IoticAgent.Core.Validation import Validation
from IoticAgent.Core.compat import RLock

from .const import LABEL, DESCRIPTION, TAGS


class ResourceBase(object):

    def __init__(self, lid, new=False, labels=None, descriptions=None, tags=None):
        """
        # Note lid is local id of thing or point (as per qapi)
        # Note labels & descriptions: dict like {'en': 'blah', 'fr': 'chips'}
        """
        self.__lock = RLock()
        self.__new = new
        self._changes = []
        self.__lid = Validation.lid_check_convert(lid)
        self.__labels = {}
        if labels is not None:
            for lang in labels:
                self.__lang_check_convert(lang)
                self.__labels[lang] = Validation.label_check_convert(labels[lang])
        self.__descriptions = {}
        if descriptions is not None:
            for lang in descriptions:
                self.__lang_check_convert(lang)
                self.__descriptions[lang] = Validation.comment_check_convert(descriptions[lang])
        self.__tags = set() if tags is None else set(tags)

    @classmethod
    def __lang_check_convert(cls, lang):
        if lang == '':
            return None
        if lang is None:
            return ''
        return Validation.lang_check_convert(lang)

    @property
    def lock(self):
        return self.__lock

    @property
    def new(self):
        return self.__new

    def _set_not_new(self):
        self.__new = False

    @property
    def lid(self):
        with self.__lock:
            return self.__lid

    def set_label(self, label, lang=None):
        with self.__lock:
            lang = self.__lang_check_convert(lang)
            label = Validation.label_check_convert(label)
            if lang in self.__labels:
                if self.__labels[lang] != label:
                    self.__labels[lang] = label
                    if LABEL + lang not in self._changes:
                        self._changes.append(LABEL + lang)
            else:
                self.__labels[lang] = label
                self._changes.append(LABEL + lang)

    @property
    def labels(self):
        with self.__lock:
            return self.__labels

    def set_description(self, description, lang=None):
        with self.__lock:
            lang = self.__lang_check_convert(lang)
            description = Validation.comment_check_convert(description)
            if lang in self.__descriptions:
                if self.__descriptions[lang] != description:
                    self.__descriptions[lang] = description
                    if DESCRIPTION + lang not in self._changes:
                        self._changes.append(DESCRIPTION + lang)
            else:
                self.__descriptions[lang] = description
                self._changes.append(DESCRIPTION + lang)

    @property
    def descriptions(self):
        with self.__lock:
            return self.__descriptions

    def create_tag(self, taglist):
        with self.__lock:
            taglist = set(Validation.tags_check_convert(taglist))
            # todo: support replace rather than addition only?
            if taglist - self.__tags:
                if TAGS not in self._changes:
                    self._changes.append(TAGS)
                self.__tags |= taglist

    @property
    def tags(self):
        with self.__lock:
            return tuple(self.__tags)

    @property
    def changes(self):
        with self.__lock:
            return self._changes
