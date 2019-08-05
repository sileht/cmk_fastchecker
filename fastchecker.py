#!/usr/bin/env python
#
# Copyright (C) 2018-2019 Mehdi Abaakouk <sileht@sileht.net>
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


from __future__ import print_function

import daiquiri
import functools
import logging
import mock
import monotonic
import multiprocessing
import os

import cmk
import cmk.log

import cmk_base
import cmk_base.checking as checking
import cmk_base.checks as checks
import cmk_base.discovery as discovery
import cmk_base.config as config
import cmk_base.ip_lookup as ip_lookup
import cmk_base.data_sources as data_sources
import cmk_base.item_state as item_state


import flask

cmk.log.setup_console_logging()

LOG = daiquiri.getLogger(__name__)

PIDFILE = os.environ['PIDFILE']

SITENAME = os.environ['SITENAME']
SITEPATH = os.environ['SITEPATH']
TMPPATH = os.environ['FASTCHECKER_TMPPATH']
LOGPATH = os.environ['FASTCHECKER_LOGPATH']

daiquiri.setup(
    level=logging.INFO,
    outputs=[
        daiquiri.output.STDERR,
    ]
)

class StopWatch(object):
    def __init__(self):
        self._started_at = monotonic.monotonic()

    def elapsed(self):
        return max(0.0, monotonic.monotonic() - self._started_at)


class FakeStdout(object):
    def __init__(self):
        self.data = b""

    def write(self, data):
        self.data += data


def input_output_fixup(func):
    @functools.wraps(func)
    def wrapped(hostname):
        hostname = str(hostname)
        with mock.patch('cmk_base.console.sys.stdout', new=FakeStdout()) as out:
	    exit_status = func(hostname)
            if exit_status is not None:
                return "%s\n%s" % (exit_status, out.data)
            else:
                return out.data
    return wrapped

def wsgi():
    LOG.info("Loading check_mk module...")
    watch = StopWatch()
    checks.load()
    config.load()
    count = len(checks.check_info)
    LOG.info("%d checks loaded in %s." % (count, watch.elapsed()))

    app = flask.Flask(__name__)

    @app.route("/check/<hostname>")
    @input_output_fixup
    def check(hostname):
        return checking.do_check(hostname, None, None)

    @app.route("/detail/<hostname>")
    @input_output_fixup
    def detail(hostname):
        try:
            cmk.debug.enable()
            cmk.log.set_verbosity(verbosity=2)
            return checking.do_check(hostname, None, None)
        finally:
            cmk.log.set_verbosity(verbosity=0)
            cmk.debug.disable()

    @app.route("/inventory/<hostname>")
    @input_output_fixup
    def inventory(hostname):
        return discovery.do_inv_check(hostname, None)

    return app


def main():
    args = [
       "--master",
       "--http", "127.0.0.1:5001",
       "--need-app",
       "--enable-threads",
       "--thunder-lock",
       "--add-header", "Connection: Close",
       "--procname-prefix-spaced", "fastchecker",
       "--max-requests", "500",
       "--die-on-term",
       "--ignore-sigpipe",
       "--listen", "2048",
       "--processes", str(multiprocessing.cpu_count() * 6 + 1),
       "--pidfile2", PIDFILE,
       "--wsgi-file", __file__,
       "--harakiri", "58",
       "--disable-logging",
       "--daemonize2", LOGPATH,
    ]
    uwsgi = SITEPATH + "/local/lib/python/bin/uwsgi"
    os.execl(uwsgi, uwsgi, *args)


if __name__ == "__main__":
    main()
else:
    application = wsgi()
