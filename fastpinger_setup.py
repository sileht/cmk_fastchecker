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
import pwd
import netaddr
import os
import sys
import time


#if [[ ! -e $TMP_DIR/ips.lst ]] || [[ networks.lst -nt $TMP_DIR/ips.lst ]] || [[ -n "$FORCE" ]]; then
#	log "Start generating ips list..."
#	> $TMP_DIR/ips.lst.new
#	grep -v -e '^[[:space:]]*#' -e '^[[:space:]]*$' networks.lst | while read network garbage; do
#		is_ipv6=$(echo $network | grep '::')
#		if [ "$is_ipv6" ]; then
#			echo $network >> $TMP_DIR/ips.lst.new
#		else
#			prips $network | while read ip ; do
#				echo $ip >> $TMP_DIR/ips.lst.new
#				ipv6=$(get_ipv6 $ip)
#				[ "$ipv6" ] && echo $ipv6 >> $TMP_DIR/ips.lst.new
#			done
#		fi
#	done
#	mv -f $TMP_DIR/ips.lst.new $TMP_DIR/ips.lst
#	#$here/fastpinger_setuper
#fi


SITENAME = pwd.getpwuid(os.getuid())[0]
IPS_PATH = "/omd/sites/%s/tmp/fastpinger/ips.lst" % SITENAME
CONFIG_PATH="/omd/sites/%s/etc/nagios/conf.d/fping_objects.cfg" % SITENAME
NETWORK_PATH = "%s/networks.lst" % os.environ["BASE_DIR"]

TEMPLATE="""
define service {
  use                           fping_service_passive
  service_description           PING %s
}
"""

with open(CONFIG_PATH, "w") as f_nagios, open(NETWORK_PATH, "r") as f_networks, open("%s.tmp" % IPS_PATH, "w") as f_ips:

    f_nagios.write("""
define host {
  name                          fping
  use                           check_mk_host
  contact_groups                ircbot
  max_check_attempts            1.0
  retry_interval                1.0
  check_interval                1.0
  _FILENAME                     none
  _TAGS                         fping
  check_command                 check-mk-dummy
}

define service {
  name                          fping_service_passive
  use                           check_mk_passive_perf
  register                      0
  host_name                     fping
  contact_groups                ircbot,ircbot-infra
  max_check_attempts            1.0
  retry_interval                1.0
  check_interval                1.0
  check_command                 check-mk-dummy
}
""")

    def write_both(ip):
        f_ips.write("%s\n" % ip)
        f_nagios.write(TEMPLATE % ip)

    nets = filter(lambda l: l and not l.startswith("#"),
            itertools.imap(lambda l: l.split("#")[0].strip(), 
                f_networks.readlines()))
    ips = itertools.chain(*itertools.imap(netaddr.IPNetwork, nets))
    map(write_both, ips)

try:
    os.remove(IPS_PATH)
except OSError:
    pass
os.rename("%s.tmp" % IPS_PATH, IPS_PATH)
