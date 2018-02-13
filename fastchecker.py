#!/usr/bin/python

from __future__ import print_function

from concurrent import futures
import imp
import mock
import multiprocessing
import os
import pwd
import sys
import time

import cmk
import flask

SITENAME = pwd.getpwuid(os.getuid())[0]
BASEPATH = "/omd/sites/%s/var/check_mk/precompiled" % SITENAME
CMKPATH = "/omd/sites/%s/share/check_mk/modules/check_mk.py" % SITENAME


def get_modname(name):
    return name.replace(".", "xDOTx")


def create_module(name, data):
    with mock.patch('sys.path', new=list(sys.path)):
        code = compile(data, "<string>", "exec")
        m = imp.new_module(name)
        eval(code, m.__dict__, m.__dict__)
        sys.modules[name] = m
        return m


def prep_and_load_module(f):
    name = get_modname(f[:-3])
    data = b''
    with open("%s/%s" % (BASEPATH, f)) as fin:
        for line in fin.readlines():
            if line.startswith("register_sigint_handler()"):
                continue
            if line.startswith("    sys.exit(do_check"):
                data = data[:-5] + "def runner():\n"
                data += line.replace("sys.exit(", "return (")
                break
            data += line
    try:
        m = create_module(name, data)
    except (IOError, ImportError) as e:
        print("Fail to load %s: %s"% (f, str(e)))

def prep_and_load_check_mk():
    lastline = "register_sigint_handler"
    data = b''
    with open(CMKPATH, "r") as fin:
        for line in fin.readlines():
            if line.startswith(lastline):
                break
            data += line
    m = create_module("check_mk", data)
    m.load_checks()
    m.set_use_cachefile()
    m.enforce_using_agent_cache()
    m.read_config_files()

def preload_checks():
    workers = multiprocessing.cpu_count() * 2 + 1
    print("Loading checks with %d workers..." % workers)
    filenames = [f for f in os.listdir(BASEPATH) if f.endswith(".py")]
    print("Loading %d checks..." % len(filenames))
    with futures.ThreadPoolExecutor(max_workers=workers) as e:
        fs = [e.submit(prep_and_load_check_mk)]
        fs.extend([e.submit(prep_and_load_module, f)
                   for f in filenames])
        for f in futures.as_completed(fs):
            f.result()
    print("%d checks loaded." % len(filenames))


# NOTE(sileht): Copy of the __main__ of check_mk check
def run_check(name, verbose=False):
    try:
        if verbose:
            sys.modules[name].cmk.log.set_verbosity(verbosity=1)
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
            sys.modules[name].cmk.log.set_verbosity(verbosity=0)


class FakeStdout(object):
    def __init__(self):
        self.data = b""

    def write(self, data):
        self.data += data


app = flask.Flask(__name__)

@app.route("/check/<name>")
def check(name):
    name = get_modname(name)
    with mock.patch('%s.sys.stdout' % name, new=FakeStdout()) as out:
	try:
            run_check(name)
	except SystemExit, e:
	    return "%s\n%s" % (e.code, out.data)


@app.route("/detail/<name>")
def detail(name):
    name = get_modname(name)
    with mock.patch('%s.sys.stdout' % name, new=FakeStdout()) as out:
	try:
            run_check(name, verbose=True)
	except SystemExit, e:
	    return "%s\n%s" % (e.code, out.data)


@app.route("/inventory/<name>")
def inventory(name):
    with mock.patch('check_mk.sys.stdout', new=FakeStdout()) as out:
	try:
            sys.modules["check_mk"].check_discovery(name)
	except SystemExit, e:
	    return "%s\n%s" % (e.code, out.data)


preload_checks()
