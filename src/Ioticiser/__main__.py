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
"""Iotic Labs Remote API to Feed example
"""

from __future__ import unicode_literals, print_function

import logging
logging.getLogger('rdflib').setLevel(logging.WARNING)
logging.getLogger('IoticAgent').setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

from sys import argv, exit, stdin  # pylint: disable=redefined-builtin
from os import environ, mkdir
from os.path import exists, isdir, abspath
from signal import signal, SIGINT, SIGTERM
from time import sleep
from threading import Thread

from IoticAgent.Core.compat import Event, Queue

from .compat import SIGUSR1
from .Config import Config
from .Runner import Runner


def usage():
    logger.error('Usage: python3 -m Ioticiser ../cfg/example.ini')
    return 1


def all_runners_finished(runners):
    all_done = True
    for name in runners:
        if runners[name].is_alive():
            all_done = False
            break
    return all_done


def input(input_queue):  # pylint: disable=redefined-builtin
    if not input_queue.empty():
        ret = ""
        while not ret.endswith("\n"):
            ret += input_queue.get()
        ret = ret.strip()
        # logger.critical("input return '%s'", ret)
        return ret
    return None


def add_input(input_queue):
    while True:
        input_queue.put(stdin.read(1))


def main():  # pylint: disable=too-many-return-statements,too-many-branches,too-many-locals
    if len(argv) < 2:
        if not exists(argv[1]):
            return usage()
    try:
        cfg = Config(argv[1])
    except:
        logger.exception("Failed to load/parse Config file '%s'. Giving up.", argv[1])
        return 1

    datapath = cfg.get('main', 'datapath')
    if datapath is None:
        logger.error("Config file must have [main] section with datapath = /path/to/storage")
        return 1
    datapath = abspath(datapath)
    if not exists(datapath):
        mkdir(datapath)
    elif exists(datapath) and not isdir(datapath):
        logger.error("Config file must have [main] datapath not a directory")
        return 1

    source_list = cfg.get('main', 'sources')
    if source_list is None:
        logger.error("Config file must have [main] sources = \n\tSourceName\n\tSourceTwo")
        return 1

    runners = {}
    stop_evt = Event()
    for source_name in source_list.strip().split("\n"):
        try:
            runners[source_name] = Runner(source_name, cfg.get(source_name), stop_evt, datapath)
        except ValueError as e:
            logger.error("Runner [%s] failed init. Reason [%s]", source_name, str(e))
            return 1
        except ImportError as e:
            logger.error("Runner [%s] failed init. Reason [%s]", source_name, str(e))
            return 1
        except Exception as e:  # pylint: disable=broad-except
            logger.exception("Runner [%s] failed init. Reason [%s]", source_name, str(e))
            return 1

    def receive_abort_signal(signum, stack):  # pylint: disable=unused-argument
        if signum == SIGUSR1:
            logger.critical("Received Abort Signal (SIGUSR1).  Exiting.")
            stop_evt.set()
        elif signum == SIGINT or signum == SIGTERM:
            logger.critical('Shutdown requested')
            stop_evt.set()

    signal(SIGUSR1, receive_abort_signal)

    for name, runner in runners.items():
        logger.info("Runner [%s] Started", name)
        runner.start()

    if 'IOTIC_BACKGROUND' in environ:
        logger.info("Started in non-interactive mode.")

        signal(SIGINT, receive_abort_signal)
        signal(SIGTERM, receive_abort_signal)

        while not stop_evt.is_set() or not all_runners_finished(runners):
            stop_evt.wait(timeout=5)
        stop_evt.set()

    else:
        input_queue = Queue()
        input_thread = Thread(target=add_input, name="add_input", args=(input_queue,))
        input_thread.daemon = True
        input_thread.start()

        try:
            print('Enter "q" to exit')
            while not stop_evt.is_set():
                try:
                    inp = input(input_queue)
                    if inp == 'q':
                        break
                    elif inp is not None:
                        print('Enter "q" to exit')
                    if all_runners_finished(runners):
                        logger.warning("All Runners have stopped.  Exit.")
                        break
                    stop_evt.wait(timeout=1)
                except EOFError:
                    logger.warning("Got EOF stopping...")
                    break
                except KeyboardInterrupt:
                    logger.warning("Got ctrl+c stopping...")
                    break
        except SystemExit:
            pass
        stop_evt.set()

    for name, runner in runners.items():
        logger.info("Waiting for runner %s to die...", name)
        while runner.is_alive():
            sleep(0.1)
    return 0


if __name__ == '__main__':
    exit(main())
