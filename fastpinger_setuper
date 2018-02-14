#!/bin/bash

SITENAME=$(id -un)
TMP_DIR="/omd/sites/${SITENAME}/tmp/fastpinger"
CONFIG="/omd/sites/${SITENAME}/etc/nagios/conf.d/fping_objects.cfg"

cat > $CONFIG <<EOF
define host {
  name                          fping_host_passive
  use                           check_mk_host
  register                      0
  active_checks_enabled         0
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
  service_description           PING
  contact_groups                ircbot,ircbot-infra
  max_check_attempts            1.0
  retry_interval                1.0
  check_interval                1.0
  check_command                 check-mk-dummy
}
EOF

for ip in $(cat $TMP_DIR/ips.lst); do
	ipv4=
	ipv6=
	if [ "$(echo $ip | grep '::')" ]; then
	      	version=6
		ipv6=$ip
	else
		version=4
		ipv4=$ip
	fi

	cat >> $CONFIG <<EOF
define host {
  host_name                     $ip
  use                           fping_host_passive
  address                       $ip
  _ADDRESS_FAMILY               $version
  _ADDRESS_6                    $ipv6
  _ADDRESS_4                    $ipv4
}

define service {
  use                           fping_service_passive
  host_name                     $ip
}
EOF
done
