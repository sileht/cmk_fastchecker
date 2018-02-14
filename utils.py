#!/usr/bin/python

# Copyright (C) 2018 Mehdi Abaakouk <sileht@sileht.net>
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import monotonic


class StopWatch(object):
    """A simple timer/stopwatch helper class.
    Inspired by: apache-commons-lang java stopwatch.
    Not thread-safe (when a single watch is mutated by multiple threads at
    the same time). Thread-safe when used by a single thread (not shared) or
    when operations are performed in a thread-safe manner on these objects by
    wrapping those operations with locks.
    It will use the `monotonic`_ pypi library to find an appropriate
    monotonically increasing time providing function (which typically varies
    depending on operating system and python version).
    .. _monotonic: https://pypi.python.org/pypi/monotonic/
    """
    _STARTED = object()
    _STOPPED = object()

    def __init__(self):
        self._started_at = None
        self._stopped_at = None
        self._state = None

    def start(self):
        """Starts the watch (if not already started).
        NOTE(harlowja): resets any splits previously captured (if any).
        """
        if self._state == self._STARTED:
            return self
        self._started_at = monotonic.monotonic()
        self._state = self._STARTED
        return self

    @staticmethod
    def _delta_seconds(earlier, later):
        # Uses max to avoid the delta/time going backwards (and thus negative).
        return max(0.0, later - earlier)

    def elapsed(self):
        """Returns how many seconds have elapsed."""
        if self._state not in (self._STARTED, self._STOPPED):
            raise RuntimeError("Can not get the elapsed time of a stopwatch"
                               " if it has not been started/stopped")
        if self._state == self._STOPPED:
            elapsed = self._delta_seconds(self._started_at, self._stopped_at)
        else:
            elapsed = self._delta_seconds(
                self._started_at, monotonic.monotonic())
        return elapsed

    def __enter__(self):
        """Starts the watch."""
        self.start()
        return self

    def __exit__(self, type, value, traceback):
        """Stops the watch (ignoring errors if stop fails)."""
        try:
            self.stop()
        except RuntimeError:
            pass

    def stop(self):
        """Stops the watch."""
        if self._state == self._STOPPED:
            return self
        if self._state != self._STARTED:
            raise RuntimeError("Can not stop a stopwatch that has not been"
                               " started")
        self._stopped_at = monotonic.monotonic()
        self._state = self._STOPPED
        return self

    def reset(self):
        """Stop and re-start the watch."""
        self.stop()
        return self.start()

