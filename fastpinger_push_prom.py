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
import os
import sys
import time

NOW = time.strftime('%s')
COMMAND_FILE = os.environ['FASTPINGER_COMMANDFILE']
FASTPINGER_DUMP = os.environ['FASTPINGER_DUMP']
MDATE = datetime.fromtimestamp(os.path.getmtime(FASTPINGER_DUMP)).isoformat()

HEADER_TEMPLATE = """# HELP fastpinger_%(metric)s fping metric %(metric)s
# TYPE fastpinger_%(metric)s gauge
"""

TEMPLATE = """fastpinger_%(metric)s{fastping_ip="%(ip)s"} %(value)s
"""

with open(FASTPINGER_DUMP, "r") as f:
    lines = list(l for l in f.readlines() if "duplicate" not in l and l.split(".")[0] not in ["192", "172"])

total = len(lines)
header_done = False
for line in lines:
    raw = line.split()
    ip = raw[0]

    # Don't sent to prometheus non ttnn stuff
    for prefix in ["2a03:", "91.224.", "89.234.", "185.119."]:
        if ip.startswith(prefix):
            break
    else:
        continue

    rts = list(map(float, filter(lambda rt: rt != "-", raw[2:])))
    rt = (sum(rts) / len(rts)) if rts else 0
    loss = 100 - len(rts) * 100 / 5
    up = 0 if loss >= 100 else 1
    if not header_done:
        sys.stdout.write(HEADER_TEMPLATE % {'ip': ip, 'metric': 'up', 'value': up})
    sys.stdout.write(TEMPLATE % {'ip': ip, 'metric': 'up', 'value': up})
    if not header_done:
        sys.stdout.write(HEADER_TEMPLATE % {'ip': ip, 'metric': 'rta_ms', 'value': rt})
    sys.stdout.write(TEMPLATE % {'ip': ip, 'metric': 'rta_ms', 'value': rt})
    if not header_done:
        sys.stdout.write(HEADER_TEMPLATE % {'ip': ip, 'metric': 'loss_perc', 'value': loss})
    sys.stdout.write(TEMPLATE % {'ip': ip, 'metric': 'loss_perc', 'value': loss})
    header_done = True
