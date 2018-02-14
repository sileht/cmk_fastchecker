#!/bin/bash

SITENAME=$(id -un)
LOG_DIR="/omd/sites/${SITENAME}/var/log/fastpinger"
TMP_DIR="/omd/sites/${SITENAME}/tmp/fastpinger"
COMMAND_FILE="/omd/sites/${SITENAME}/tmp/run/icinga.cmd"
CMK_FASTPINGER_DUMP="/omd/sites/$SITENAME/tmp/fastpinger/fastpinger.dump"

here=$(readlink -f $(dirname $0))
cd $here

. fastpinger_utils.sh

now=`date +%s`
PROCESS_FILE="$TMP_DIR/send_status.$now.cmd"

now=$(printf "%lu" $now)

> $PROCESS_FILE

fdate=$(stat  -c %x $CMK_FASTPINGER_DUMP | sed 's/\..*//g')

total=$(grep -v duplicate $CMK_FASTPINGER_DUMP | wc -l)
nb=0
grep -v duplicate $CMK_FASTPINGER_DUMP | while read ip _ remain ; do
	nb=$((nb + 1))
        ip=${ip%:}
	output=$(echo $remain | check_icmp_imitation $ip 200 500 40 80 "$fdate")
	ret=$? # We don't want nagios to blink, just log state and graph for now
	echo "[$now] PROCESS_HOST_CHECK_RESULT;$ip;$ret;$output" > $COMMAND_FILE
	echo "[$now] PROCESS_SERVICE_CHECK_RESULT;$ip;PING;$ret;$output" > $COMMAND_FILE
	echo -en "$nb/$total ips updated in nagios\r"
done
echo
