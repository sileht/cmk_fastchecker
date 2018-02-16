#!/usr/bin/python
#
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


from __future__ import print_function

import cStringIO
import contextlib
import daiquiri
from distutils import spawn
import imp
import logging
import mock
import monotonic
import multiprocessing
import os
import pwd
import sys
import time

import cmk
import flask

LOG = daiquiri.getLogger(__name__)

SITENAME = pwd.getpwuid(os.getuid())[0]
BASEPATH = "/omd/sites/%s/var/check_mk/precompiled" % SITENAME
TMPPATH = "/omd/sites/%s/tmp/fastchecker" % SITENAME
LOGPATH = "/omd/sites/%s/var/log/fastchecker.log" % SITENAME
CMKPATH = "/omd/sites/%s/share/check_mk/modules/check_mk.py" % SITENAME
PIDFILE = os.environ['PIDFILE']

try:
    os.makedirs(TMPPATH)
except OSError:
    pass

daiquiri.setup(
    outputs=[
        daiquiri.output.STDERR,
    ]
)

LOG.setLevel(logging.INFO)

class StopWatch(object):
    def __init__(self):
        self._started_at = monotonic.monotonic()

    def elapsed(self):
        return max(0.0, monotonic.monotonic() - self._started_at)


def get_modname(name):
    return name.replace(".", "xDOTx")


def prep_and_load_module(f):
    name = get_modname(f[:-3])
    with open("%s/%s.py" % (TMPPATH, name), "w+") as fout:
        with open("%s/%s" % (BASEPATH, f)) as fin:
            for line in fin.readlines():
                if line.startswith("register_sigint_handler()"):
                    continue
                if line.startswith("    sys.exit(do_check"):
                    fout.seek(-5, 1)
                    fout.write("def runner():\n")
                    fout.write(line.replace("sys.exit(", "return ("))
                    break
                fout.write(line)
            fout.seek(0)
            try:
                with mock.patch('sys.path', new=list(sys.path)):
                    imp.load_module(name, fout, fout.name, (".py", "rw", imp.PY_SOURCE))
            except (IOError, ImportError) as e:
                LOG.info("Fail to load %s: %s"% (f, str(e)))

def prep_and_load_check_mk():
    lastline = "register_sigint_handler"
    with open("%s/%s.py" % (TMPPATH, "check_mk"), "w+") as fout:
        with open(CMKPATH, "r") as fin:
            for line in fin.readlines():
                if line.startswith(lastline):
                    break
                fout.write(line)
        fout.seek(0)
        with mock.patch('sys.path', new=list(sys.path)):
            m= imp.load_module("check_mk", fout, fout.name, (".py", "rw", imp.PY_SOURCE))
            m.load_checks()
            m.set_use_cachefile()
            m.enforce_using_agent_cache()
            m.read_config_files()

def preload_checks():
    LOG.info("Loading check_mk module...")
    watch = StopWatch()
    filenames = [f for f in os.listdir(BASEPATH) if f.endswith(".py")]
    prep_and_load_check_mk()
    LOG.info("Loading %d checks..." % len(filenames))
    count=0
    for f in filenames:
        count+=1
        prep_and_load_module(f)
        sys.stdout.write("%d/%d checks loaded. \r" % (count, len(filenames)))
        sys.stdout.flush()
    LOG.info("%d/%d checks loaded in %s." % (count, len(filenames),
                                             watch.elapsed()))

# NOTE(sileht): Copy of the __main__ of check_mk check
def run_check(name, verbose=False):
    try:
        if verbose:
            cmk.log.set_verbosity(verbosity=1)
        sys.exit(sys.modules[name].runner())
    except ImportError:
        sys.stdout.write("UNKNOWN - checks for %s is not loaded" % name)
        sys.exit(3)
    except SystemExit, e:
	sys.exit(e.code)
    except Exception, e:
	import traceback, pprint
	sys.stdout.write("UNKNOWN - Exception in precompiled check: %s (details in long output)\n" % e)
	sys.stdout.write("Traceback: %s\n" % traceback.format_exc())

	l = file(cmk.paths.log_dir + "/crashed-checks.log", "a")
	l.write(("Exception in precompiled check:\n"
		"  Check_MK Version: %s\n"
		"  Date:             %s\n"
		"  Host:             %s\n"
		"  %s\n") % (
		cmk.__version__,
		time.strftime("%Y-%d-%m %H:%M:%S"),
		"g12",
		traceback.format_exc().replace('\n', '\n      ')))
	l.close()
	sys.exit(3)
    finally:
        if name in sys.modules:
            cmk.log.set_verbosity(verbosity=0)


class FakeStdout(object):
    def __init__(self):
        self.data = b""

    def write(self, data):
        self.data += data


def do_run_check(name, verbose=False):
    name = get_modname(name)
    try:
        with mock.patch('%s.sys.stdout' % name, new=FakeStdout()) as out:
            run_check(name, verbose)
    except SystemExit, e:
        return "%s\n%s" % (e.code, out.data)


def wsgi():
    preload_checks()

    app = flask.Flask(__name__)


    @app.route("/check/<name>")
    def check(name):
        return do_run_check(name)


    @app.route("/detail/<name>")
    def detail(name):
        return do_run_check(name, verbose=True)


    @app.route("/inventory/<name>")
    def inventory(name):
        try:
            with mock.patch('check_mk.sys.stdout', new=FakeStdout()) as out:
                sys.modules["check_mk"].check_discovery(name)
        except SystemExit, e:
            return "%s\n%s" % (e.code, out.data)

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
       "--max-requests", "100",
       "--die-on-term",
       "--ignore-sigpipe",
       "--listen", "2048",
       "--processes", str(multiprocessing.cpu_count() * 2 + 1),
       "--pidfile2", PIDFILE,
       "--wsgi-file", __file__,
       "--harakiri", "120",
       "--daemonize2", LOGPATH,
    ]
    uwsgi = spawn.find_executable("uwsgi")
    os.execl(uwsgi, uwsgi, *args)


if __name__ == "__main__":
    main()
else:
    application = wsgi()
