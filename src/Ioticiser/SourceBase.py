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


class SourceBase(object):
    """Source base class
    """

    def __init__(self, stash, config, stop):
        self._stash = stash
        self._config = config
        self._stop = stop

    def run(self):
        """Entry point for the Source
        """
        raise NotImplementedError

    def control_callback(self, thing, control, msg):
        """Override to handle control request callbacks. `thing` & `control` are Stash object instances associated with
        the control. `msg` has the same format as IoticAgent.IOT's control callback. Note that this callback will not be
        triggered for unknown (to the stash/runner) controls.
        To confirm a "tell" request, one can use self._stash.confirm_tell (in the same fashion as for IoticAgent.IOT).
        """
        pass

    def control_callback_parsed(self, thing, control, msg):
        """See `control_callback`. This callback is only triggered if the incoming control request data could be parsed
        according to its metadata definition.
        """
        pass
