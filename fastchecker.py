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


from __future__ import print_function

import cStringIO
import contextlib
import daiquiri
import imp
import logging
import mock
import os
import pwd
import sys
import time

import cmk
import flask

import utils

DEBUG_MEM_LEAK = False

if DEBUG_MEM_LEAK:
    import pympler.muppy
    import pympler.summary

def dump_memory():
    if not DEBUG_MEM_LEAK:
        return
    objects = pympler.muppy.get_objects()
    rows = pympler.summary.summarize(objects)
    LOG.info("--- memleak start ---")
    for row in list(sorted(((r[2], r[1], r[0]) for r in rows), reverse=True))[:10]:
        LOG.info("memleak: %s" % str(row))
    LOG.info("--- memleak stop ---")


LOG = daiquiri.getLogger(__name__)

SITENAME = pwd.getpwuid(os.getuid())[0]
BASEPATH = "/omd/sites/%s/var/check_mk/precompiled" % SITENAME
TMPPATH = "/omd/sites/%s/tmp/fastchecker/checks" % SITENAME
LOGPATH = "/omd/sites/%s/var/log/fastchecker/fastchecker.log" % SITENAME
CMKPATH = "/omd/sites/%s/share/check_mk/modules/check_mk.py" % SITENAME

try:
    os.makedirs(TMPPATH)
except OSError:
    pass

daiquiri.setup(
    outputs=[
        daiquiri.output.STDERR,
#        daiquiri.output.File(filename=LOGPATH),
    ]
)

LOG.setLevel(logging.INFO)

CODES = {}

def get_modname(name):
    return name.replace(".", "xDOTx")


def reload_module(name):
    return
    if CODES:
        if name in sys.modules:
            del sys.modules[name]
        m = imp.new_module(name)
        eval(CODES[name], m.__dict__, m.__dict__)
        sys.modules[name] = m
        return m
    else:
        return reload(sys.modules[name])


def create_module_from_memory(name, f):
    with mock.patch('sys.path', new=list(sys.path)):
        CODES[name]= compile(f.read(), "<string>", "exec")
        return reload_module(name)


def create_module_from_file(name, f):
    with mock.patch('sys.path', new=list(sys.path)):
        return imp.load_module(name, f, f.name, (".py", "rw", imp.PY_SOURCE))


@contextlib.contextmanager
def create_memory_buffer(name):
    s = cStringIO.StringIO()
    try:
        yield s
    finally:
        s.close()


def create_file_buffer(name):
    path = "%s/%s.py" % (TMPPATH, name)
    return open(path, "w+")


mode = "file"
create_module = globals()["create_module_from_%s" % mode]
create_buffer =  globals()["create_%s_buffer" % mode]

def prep_and_load_module(f):
    name = get_modname(f[:-3])
    with create_buffer(name) as fout:
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
                create_module(name, fout)
            except (IOError, ImportError) as e:
                LOG.info("Fail to load %s: %s"% (f, str(e)))

def prep_and_load_check_mk():
    lastline = "register_sigint_handler"
    with create_buffer("check_mk") as fout:
        with open(CMKPATH, "r") as fin:
            for line in fin.readlines():
                if line.startswith(lastline):
                    break
                fout.write(line)
        fout.seek(0)
        m = create_module("check_mk", fout)
        m.load_checks()
        m.set_use_cachefile()
        m.enforce_using_agent_cache()
        m.read_config_files()

def preload_checks_threads():
    from concurrent import futures
    import multiprocessing
    workers = multiprocessing.cpu_count() * 2 + 1
    LOG.info("Loading checks with %d workers..." % workers)
    filenames = [f for f in os.listdir(BASEPATH) if f.endswith(".py")]
    LOG.info("Loading %d checks..." % len(filenames))
    with futures.ThreadPoolExecutor(max_workers=workers) as e:
        fs = [e.submit(prep_and_load_check_mk)]
        fs.extend([e.submit(prep_and_load_module, f)
                   for f in filenames])
        for f in futures.as_completed(fs):
            f.result()
    LOG.info("%d checks loaded." % len(filenames))


def preload_checks_serial():
    LOG.info("Loading check_mk module...")
    watch = utils.StopWatch().start()
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

preload_checks = preload_checks_serial


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
    watch = utils.StopWatch().start()
    name = get_modname(name)
    try:
        with mock.patch('%s.sys.stdout' % name, new=FakeStdout()) as out:
            run_check(name, verbose)
    except SystemExit, e:
        LOG.info("Checks for %s done in %s." % (name, watch.elapsed()))
        return "%s\n%s" % (e.code, out.data)
    finally:
        reload_module(name)
        dump_memory()


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
    finally:
        dump_memory()


preload_checks()
