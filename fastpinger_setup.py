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

from __future__ import with_statement

from datetime import datetime
import itertools
import netaddr
import os
import sys
import time

IPS_PATH = os.environ['FASTPINGER_IPSPATH']
NAGIOS_CONFIG_PATH = os.environ['FASTPINGER_NAGIOS_CONFIG']
NETWORK_PATH = os.environ['FASTPINGER_NETWORKSPATH']

TEMPLATE="""
define service {
  use                           fping_service_passive
  service_description           PING %s
}
"""

map_ipv4v6 = {
    '91.224.148': 80,
    '91.224.149': 81,
    '89.234.156': 83,
    '89.234.157': 84,
}

def get_ipv6(ip):
    if "::" in ip:
        return
    for prefix in map_ipv4v6:
        if ip.startswith(prefix):
            digit = hex(int(ip.split(".")[-1]))[2:]
            net = map_ipv4v6[prefix]
            return "2a03:7220:80%s:%s00::1" % (net, digit)

with open(NAGIOS_CONFIG_PATH, "w") as f_nagios, open(NETWORK_PATH, "r") as f_networks, open("%s.tmp" % IPS_PATH, "w") as f_ips:

    f_nagios.write("""
define service {
  name                          fping_service_passive
  use                           check_mk_passive_perf
  register                      0
  host_name                     fping
  max_check_attempts            1.0
  retry_interval                1.0
  check_interval                1.0
  check_command                 check-mk-dummy
}
""")

    def write_both(ip):
        ip = str(ip) 
        f_ips.write("%s\n" % ip)
        if ip.split(".")[0] not in ["192", "172"]:
            f_nagios.write(TEMPLATE % ip)

        ipv6 = get_ipv6(ip)
        if ipv6:
            f_ips.write("%s\n" % ipv6)
            f_nagios.write(TEMPLATE % ipv6)
        return [ip, ipv6]

    nets = filter(lambda l: l and not l.startswith("#"),
            itertools.imap(lambda l: l.split("#")[0].strip(), 
                f_networks.readlines()))
    ips = itertools.chain(*itertools.imap(netaddr.IPNetwork, nets))
    ips = list(itertools.chain(*map(write_both, ips)))
    print("%d ips generated." % len(ips))

try:
    os.remove(IPS_PATH)
except OSError:
    pass
os.rename("%s.tmp" % IPS_PATH, IPS_PATH)
