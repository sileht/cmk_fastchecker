#!/usr/bin/python

from __future__ import print_function

import imp
import mock
import os
import pwd
import sys
import time

import cmk
import flask

SITENAME = pwd.getpwuid(os.getuid())[0]
BASEPATH = "/omd/sites/%s/var/check_mk/precompiled" % SITENAME
TMPPATH = "/opt/omd/sites/%s/tmp/fastchecker/checks" % SITENAME
CMKPATH = "/omd/sites/%s/share/check_mk/modules/check_mk.py" % SITENAME

def get_modname(name):
    return name.replace(".", "xDOTx")


def preload_checks():
    try:
	os.makedirs(TMPPATH)
    except OSError:
	pass

    print("Loading checks ...")
    count = 0
    for f in os.listdir(BASEPATH):
	if not f.endswith(".py"):
	    continue
	name = get_modname(f[:-3])
	preloadpath = os.path.join(TMPPATH, "%s.py" % name)

	with open(preloadpath, "w+") as fout:
	    with open("%s/%s" % (BASEPATH, f)) as fin:
		for line in fin.readlines():
		    if line.startswith("    sys.exit(do_check"):
			fout.seek(-5, 1)
			fout.write("def runner():\n")
			fout.write(line.replace("sys.exit(", "return ("))
			break
		    fout.write(line)

	    fout.seek(0)
	    # NOTE(sileht): Each check pop the first item from the list
            # so copy paths to ensure they all have the same list.
	    with mock.patch('sys.path', new=list(sys.path)):
		imp.load_module(name, fout, preloadpath, (".py", "rw", imp.PY_SOURCE))
	    count += 1
    print("%d checks loaded" % count)

    lastline = "register_sigint_handler"
    preloadpath = os.path.join(TMPPATH, "check_mk.py")
    with open(preloadpath, "w+") as fout:
        with open(CMKPATH, "r") as fin:
            for line in fin.readlines():
                if line.startswith(lastline):
                    break
                fout.write(line)
        fout.seek(0)
        with mock.patch('sys.path', new=list(sys.path)):
            imp.load_module("check_mk", fout, preloadpath, (".py", "rw", imp.PY_SOURCE))
    sys.modules["check_mk"].load_checks()
    sys.modules["check_mk"].set_use_cachefile()
    sys.modules["check_mk"].enforce_using_agent_cache()
    sys.modules["check_mk"].read_config_files()


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
