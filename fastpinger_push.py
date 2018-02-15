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


import itertools
from datetime import datetime
import pwd
import os
import sys
import time

SITENAME = pwd.getpwuid(os.getuid())[0]
COMMAND_FILE = "/omd/sites/%s/tmp/run/icinga.cmd" % SITENAME
FASTPINGER_DUMP = "/omd/sites/%s/tmp/fastpinger/fastpinger.dump" % SITENAME

NOW = time.strftime('%s')
MDATE = datetime.fromtimestamp(os.path.getmtime(FASTPINGER_DUMP)).isoformat()

PROCESS_FILE = "/omd/sites/%s/tmp/fastpinger/nagios_processfile.%s.cmd" % (SITENAME, NOW)
PROCESS_FILE = None

with open(FASTPINGER_DUMP, "r") as f:
    lines = list(l for l in f.readlines() if "duplicate" not in l and l.split(".")[0] not in ["192", "172"])

total = len(lines)
count = 0
with open(PROCESS_FILE if PROCESS_FILE else COMMAND_FILE, "w") as f:
    print("Sending data in %s" % f.name)
    for line in lines:
        raw = line.split()
        ip = raw[0]
        rts = list(map(float, filter(lambda rt: rt != "-", raw[2:])))
        info = {
            "ip": ip,
            "state": "OK",
            "exit_code": 0,
            "mdate": MDATE,
            "now": NOW,
            "rt": (sum(rts) / len(rts)) if rts else 0,
            "rt_min": min(rts) if rts else 0,
            "rt_max": max(rts) if rts else 0,
            "loss": 100 - len(rts) * 100 / 5,
        }
        if info["loss"] >= 100:
            info["state"] = "CRITICAL"
            info["exit_code"] = 2

        # We just want UP/DOWN for now,
        #elif 0 < info["loss"] < 100:
        #    info["state"] = "WARNING"
        #    info["exit_code"] = 1

        info["output"] = "%(state)s - %(ip)s : rta %(rt)sms, lost %(loss)s%% (fastpinger at %(mdate)s)|rta=%(rt)sms;;;0; pl=%(loss)s%%;;;; rtmax=%(rt_max)sms;;;; rtmin=%(rt_min)sms;;;;" % info
	f.write("[%(now)s] PROCESS_SERVICE_CHECK_RESULT;fping;PING %(ip)s;%(exit_code)s;%(output)s\n" % info)
        count += 1
        sys.stdout.write("%d/%d icmp data pushed to nagios\r" % (count, total))
        sys.stdout.flush()
print("")

if PROCESS_FILE:
    with open(COMMAND_FILE, "w") as f:
        f.write("[%s] PROCESS_FILE;%s;1\n" % (NOW, PROCESSFILE))
