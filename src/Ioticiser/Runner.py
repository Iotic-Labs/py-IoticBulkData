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

from os import getpid, kill, path
from threading import Thread
from time import sleep
import logging
logger = logging.getLogger(__name__)

from IoticAgent import IOT

from .compat import SIGUSR1
from .import_helper import getItemFromModule
from .Stash import Stash


class Runner(object):  # pylint: disable=too-many-instance-attributes

    def __init__(self, name, config, stop, datapath):
        """
        """
        self.__name = name
        self.__config = config
        self.__stop = stop
        self.__datapath = datapath
        #
        self.__module = None
        self.__agentfile = None
        self.__workers = 1
        #
        self.__validate_config()
        #
        self.__agent = IOT.Client(config=self.__agentfile)
        fname = path.join(datapath, name + '.json')
        self.__stash = Stash(fname, self.__agent, self.__workers)
        self.__modinst = self.__module(self.__stash, self.__config, self.__stop)
        self.__thread = None

    def __validate_config(self):
        if 'import' not in self.__config:
            msg = "[%s] Config requires import = module.name" % self.__name
            logger.error(msg)
            raise ValueError(msg)
        self.__module = getItemFromModule(self.__config['import'])
        if 'agent' not in self.__config:
            msg = "[%s] Config requires agent = /path/to/agent.ini" % self.__name
            logger.error(msg)
            raise ValueError(msg)
        if not path.exists(self.__config['agent']):
            msg = "[%s] agent = %s file not found" % (self.__name, self.__config['agent'])
            logger.error(msg)
            raise ValueError(msg)  # note: valueerror since nobody cares file not found
        self.__agentfile = self.__config['agent']
        if 'workers' in self.__config:
            self.__workers = int(self.__config['workers'])

    def start(self):
        self.__agent.start()
        self.__thread = Thread(target=self.__run, name=('runner-%s' % self.__name))
        self.__thread.start()

    def stop(self):
        self.__stop.set()

    def __run(self):
        with self.__stash:
            try:
                self.__modinst.run()
            except:
                logger.critical("Runner died!  Aborting.", exc_info=True)
                kill(getpid(), SIGUSR1)
            if not self.__stop.is_set():
                while not self.__stash.queue_empty:
                    logger.info("Runner finished but stop not set!  Draining work queue.")
                    sleep(5)
        self.__agent.stop()

    def is_alive(self):
        return self.__thread.is_alive()
