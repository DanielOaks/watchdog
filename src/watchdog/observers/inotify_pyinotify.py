#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2011 Yesudeep Mangalapilly <yesudeep@gmail.com>
# Copyright 2012 Google, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


"""
:module: watchdog.observers.inotify_pyinotify
:synopsis: pyinotify-based ``inotify(7)`` emitter implementation.
:author: Daniel Oaks <danneh@danneh.net>
:platforms: Linux 2.6.13+.

Classes
-------
.. autoclass:: PollingEmitter
     :members:
     :show-inheritance:
"""

from __future__ import with_statement
from watchdog.utils import platform

if platform.is_linux():
    import pyinotify
    import threading

    from watchdog.observers.api import\
        EventEmitter,\
        BaseObserver,\
        DEFAULT_OBSERVER_TIMEOUT,\
        DEFAULT_EMITTER_TIMEOUT
    from watchdog.events import\
        DirDeletedEvent,\
        DirModifiedEvent,\
        DirMovedEvent,\
        DirCreatedEvent,\
        FileDeletedEvent,\
        FileModifiedEvent,\
        FileMovedEvent,\
        FileCreatedEvent,\
        EVENT_TYPE_MODIFIED,\
        EVENT_TYPE_CREATED,\
        EVENT_TYPE_DELETED,\
        EVENT_TYPE_MOVED

    mask = (pyinotify.IN_DELETE | pyinotify.IN_CREATE | pyinotify.IN_MODIFY | pyinotify.IN_CLOSE_WRITE |
            pyinotify.IN_ATTRIB | pyinotify.IN_MOVED_FROM | pyinotify.IN_MOVED_TO)

    ACTION_EVENT_MAP = {
        (True, EVENT_TYPE_MODIFIED): DirModifiedEvent,
        (True, EVENT_TYPE_CREATED): DirCreatedEvent,
        (True, EVENT_TYPE_DELETED): DirDeletedEvent,
        (True, EVENT_TYPE_MOVED): DirMovedEvent,
        (False, EVENT_TYPE_MODIFIED): FileModifiedEvent,
        (False, EVENT_TYPE_CREATED): FileCreatedEvent,
        (False, EVENT_TYPE_DELETED): FileDeletedEvent,
        (False, EVENT_TYPE_MOVED): FileMovedEvent,
    }

    class InotifyEventHandler(pyinotify.ProcessEvent):
        def my_init(self, emitter):
            self.emitter = emitter

        def process_IN_MOVED_TO(self, event):
            self.emitter.queue_event(ACTION_EVENT_MAP[event.dir, EVENT_TYPE_MOVED](event.src_pathname, event.pathname))

        def process_IN_ATTRIB(self, event):
            self.emitter.queue_event(ACTION_EVENT_MAP[event.dir, EVENT_TYPE_MODIFIED](event.pathname))

        def process_IN_CLOSE_WRITE(self, event):
            self.emitter.queue_event(ACTION_EVENT_MAP[event.dir, EVENT_TYPE_MODIFIED](event.pathname))

        def process_IN_MODIFY(self, event):
            self.emitter.queue_event(ACTION_EVENT_MAP[event.dir, EVENT_TYPE_MODIFIED](event.pathname))

        def process_IN_CREATE(self, event):
            self.emitter.queue_event(ACTION_EVENT_MAP[event.dir, EVENT_TYPE_CREATED](event.pathname))

        def process_IN_DELETE(self, event):
            self.emitter.queue_event(ACTION_EVENT_MAP[event.dir, EVENT_TYPE_DELETED](event.pathname))

    class InotifyEmitter(EventEmitter):
        """
        Platform-independent emitter that polls a directory to detect file
        system changes.
        """

        def __init__(self, event_queue, watch, timeout=DEFAULT_EMITTER_TIMEOUT):
            EventEmitter.__init__(self, event_queue, watch, timeout)
            self.wm = pyinotify.WatchManager()
            self.notifier = pyinotify.Notifier(self.wm, InotifyEventHandler(emitter=self))
            self.wm.add_watch(watch.path, mask, rec=watch.is_recursive)
            self.stopped = threading.Event()
            self.path = watch.path

        def queue_events(self, timeout):
            while not self.stopped.is_set():
                self.notifier.process_events()
                if self.notifier.check_events():
                    self.notifier.read_events()

        def on_thread_exit(self):
            self.stopped.set()
            self.notifier.stop()

    class InotifyObserver(BaseObserver):
        """
        Observer thread that schedules watching directories and dispatches
        calls to event handlers.
        """

        def __init__(self, timeout=DEFAULT_OBSERVER_TIMEOUT):
            BaseObserver.__init__(self, emitter_class=InotifyEmitter, timeout=timeout)
