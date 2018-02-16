#!/bin/bash
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

export SITENAME=$(id -un)
. /omd/sites/${SITENAME}/etc/fastchecker.conf
[ ! "$BASE_DIR" ] && { echo  "BASE_DIR is unset, please fill ~/etc/fastchecker.conf"; exit 1; }
. $BASE_DIR/paths.conf
cd $BASE_DIR

NAMED_PIPE=$(mktemp --dry-run ${FASTCHECKER_TMPPATH}/hook_pipe.XXXXXX)
mkfifo $NAMED_PIPE
cleanup () { rm -f $NAMED_PIPE ; }
trap cleanup EXIT

legacy(){
    mode=$1
    host=$2
    if [ "$mode" == "check" ] ; then
	exec python ~/var/check_mk/precompiled/"$host"
    elif [ "$mode" == "inventory" ] ; then
	exec check_mk --cache --check-discovery "$host"
    fi
}

max() {
    printf "%s\n" "$@" | sort -g | grep -v -- '-' | tail -n1
}

min() {
    printf "%s\n" "$@" | sort -g | grep -v -- '-' | head -n1
}

check_icmp_imitation () {
    dest=$1
    rt_warn=$2
    rt_crit=$3
    loss_warn=$4
    loss_crit=$5
    fdate="$6"
    read p1 p2 p3 p4 p5
    if [ "$p1" -a "$p2" -a "$p3" -a "$p4" -a "$p5" ]; then
        loss=0
        count=0
        math=""
        [ "$p1" == "-" ] && loss=$((loss + 20)) || { math="$math + $p1"; count=$((count + 1)); }
        [ "$p2" == "-" ] && loss=$((loss + 20)) || { math="$math + $p2"; count=$((count + 1)); }
        [ "$p3" == "-" ] && loss=$((loss + 20)) || { math="$math + $p3"; count=$((count + 1)); }
        [ "$p4" == "-" ] && loss=$((loss + 20)) || { math="$math + $p4"; count=$((count + 1)); }
        [ "$p5" == "-" ] && loss=$((loss + 20)) || { math="$math + $p5"; count=$((count + 1)); }
        
        if [ $count -gt 0 ]; then
                rt=$(echo "(0 $math) / $count * 1000" | bc -l | awk '{gsub(/\..*/, "", $1); print $1}')
                rt_display=$(echo "scale=2; (0 $math) / $count" | bc -l)
                rt_min=$(min $p1 $p2 $p3 $p4 $p5)
                rt_max=$(max $p1 $p2 $p3 $p4 $p5)
        else
                rt=0 rt_display=0 rt_min=0 rt_max=0
        fi
        state="OK"
        [ $loss -ge $loss_warn -o $rt -ge $rt_warn ] && state="WARNING"
        [ $loss -ge $loss_crit -o $rt -ge $rt_crit ] && state="CRITICAL"

        echo "$state - $dest : rta ${rt_display}ms, lost ${loss}% (fastpinger at $fdate)|rta=${rt_display}ms;${rt_warn};${rt_crit};0; pl=${loss}%;${loss_warn};${loss_crit};; rtmax=${rt_max}ms;;;; rtmin=${rt_min}ms;;;;"
        case $state in
            OK) return 0;;
            WARNING) return 1;;
            CRITICAL) return 2;;
        esac
    else
        return 3;
    fi
}

mode=$1
shift
if [ "$mode" == "check" -o "$mode" == "inventory" ]; then
    host="$1"
    # h7 checks take 3-4g of RAM, obviously a check_mk bug
    # due to the number of routes gathered
    # TODO(sileht): Move this in conf
    [ "$host" == "h7" ] && legacy $mode $host

    curl -s http://localhost:5001/$mode/$host > $NAMED_PIPE &
    { read RET ; cat ;} < $NAMED_PIPE

    if [[ -z "$RET" ]] || [[ "$RET" -gt 3 ]]; then
        if [ "$FALLBACK_ON_ERROR" ]; then
            legacy $mode $host
        else
            echo "fastchecker unreachable"
        fi
    fi
elif [ "$mode" == "ping" ]; then
    # Python version in fastpinger_push is slower, just due to the Python VM
    # So keep bash for this
    fdate=$(stat  -c %x $FASTPINGER_DUMP | sed 's/\..*//g')

    OPTS=`getopt -o 46w:c:n:i:I:m:l:t:b:H: -n 'parse-options' -- "$@"`
    eval set -- "$OPTS"
    ip_familly=4
    warn="200,40"
    crit="500,80"
    while true; do
        case "$1" in
            -4|-6) ip_familly=${1#-}; shift;;
            -w) warn="$2"; shift ; shift ;;
            -c) crit="$2"; shift ; shift ;;
            -n|-i|-I|-l|-t|-b) shift ; shift ;;  # We hardcode them in fastpinger
            -H) dest=$2; shift;  shift;;
            -m) multi=$2; shift;  shift;;
            --) shift; break;;
            *) break;;
        esac
    done
    [ "$#" -ge 1 ] && dest="$@"

    # FIXME(sileht): Multimode
    if [ "$multi" ]; then
        exec ~/lib/nagios/plugins/check_icmp -${ip_familly} -m $multi -w "${warn}" -c "${crit}" "$dest"
    else
        # Bash need integer
        rt_warn=$(echo $warn | awk -F, '{gsub(/\..*/, "", $1); print $1"000"}')
        rt_crit=$(echo $crit | awk -F, '{gsub(/\..*/, "", $1); print $1"000"}')
        loss_warn=$(echo $warn | awk -F, '{gsub(/\..*/, "", $2); print $2}')
        loss_crit=$(echo $crit | awk -F, '{gsub(/\..*/, "", $2); print $2}')

        # Format: <ip> : 0.48 0.33 0.46 0.46 0.39
        sed -n "s/^$dest\s\s*:\s*//gp" $FASTPINGER_DUMP | grep -v "duplicate" > $NAMED_PIPE &
	check_icmp_imitation $dest $rt_warn $rt_crit $loss_warn $loss_crit "$fdate" < $NAMED_PIPE  # cat is used to empty the pipe in case of duplicate
	RET=$?
        if [ "$RET" == "3" ]; then
            exec ~/lib/nagios/plugins/check_icmp -${ip_familly} -w "${warn}" -c "${crit}" "$dest"
        fi
    fi
else
    echo "fastchecker hook.sh called with invalid mode: $mode"
fi
[ ! "$RET" ] && RET=3
exit $RET
