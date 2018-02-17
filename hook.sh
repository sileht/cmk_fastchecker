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

RET=3
cleanup () { 
        [ "$NAMED_PIPE" ] && rm -f $NAMED_PIPE
        exit $RET
}
trap cleanup EXIT

export SITENAME=$(id -un)
. /omd/sites/${SITENAME}/etc/fastchecker.conf
[ ! "$BASE_DIR" ] && { echo  "BASE_DIR is unset, please fill ~/etc/fastchecker.conf"; exit 1; }
. $BASE_DIR/paths.conf
cd $BASE_DIR

NAMED_PIPE=$(mktemp --dry-run ${FASTCHECKER_TMPPATH}/hook_pipe.XXXXXX)
mkfifo $NAMED_PIPE
legacy(){
    mode=$1
    host=$2
    if [ "$mode" == "check" ] ; then
        exec python ~/var/check_mk/precompiled/"$host"
    elif [ "$mode" == "inventory" ] ; then
        exec check_mk --cache --check-discovery "$host"
    fi
}

to_ms(){
        var=$1 n=$2
        ms=${n%???}
        [ ! "$ms" ] && ms=0
        ms=$ms.${n:$((${#n} - 3))}
        eval "$var=$ms"
}

check_icmp_imitation () {
    read rts
    dest=$1 warn=$2 crit=$3 fdate=$4

    warn=${warn%\%}
    crit=${crit%\%}
    rt_warn=${warn%%,*}; rt_warn=${rt_warn%%.*}000
    rt_crit=${crit%%,*}; rt_crit=${rt_crit%%.*}000
    loss_warn=${warn##*,}; loss_warn=${loss_warn%%.*}
    loss_crit=${crit##*,}; loss_crit=${loss_crit%%.*}

    rt_display=0 rt_mean=0 rt_min=99999 rt_max=0 loss=0 count=0 sum=0
    for rt in $rts; do
            if [ "$rt" == "-" ]; then
                loss=$((loss + 20))
            else
                rt=${rt//./}0  # fping always have two digits after the .
                rt=${rt#0}
                sum=$(($sum + $rt))
                count=$((count + 1))
                rt_mean=$(($sum / $count))
                [ $rt -gt $rt_max ] && rt_max=$rt
                [ $rt -lt $rt_min ] && rt_min=$rt
            fi
    done

    state="OK"
    [ $loss -ge $loss_warn -o $rt_mean -ge $rt_warn ] && state="WARNING"
    [ $loss -ge $loss_crit -o $rt_mean -ge $rt_crit ] && state="CRITICAL"

    to_ms rt_display $rt_mean
    to_ms rt_max $rt_max
    to_ms rt_min $rt_min
    to_ms rt_warn $rt_warn
    to_ms rt_crit $rt_crit
    echo "$state - $dest: rta ${rt_display}ms, lost ${loss}% (fastpinger at $fdate)|rta=${rt_display}ms;${rt_warn};${rt_crit};0; pl=${loss}%;${loss_warn};${loss_crit};; rtmax=${rt_max}ms;;;; rtmin=${rt_min}ms;;;;"
    case $state in
        OK) return 0;;
        WARNING) return 1;;
        CRITICAL) return 2;;
        *) return 3;;
    esac
}

mode=$1
shift
if [ "$mode" == "check" -o "$mode" == "inventory" ]; then
    host="$1"
    # h7 checks take 3-4g of RAM, obviously a check_mk bug
    # due to the number of routes gathered
    # TODO(sileht): Move this in conf
    [ "$host" == "h7" ] && legacy $mode $host

    curl -f -s http://localhost:5001/$mode/$host > $NAMED_PIPE &
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
    
    warn="200.00,40.00%"
    crit="500.00,80.00%"
    ip_familly=4
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
        # Format: <ip> : 0.48 0.33 0.46 0.46 0.39
        sed -n "/duplicate/! s/^$dest\s\s*:\s*//gp" $FASTPINGER_DUMP > $NAMED_PIPE &
        check_icmp_imitation $dest $warn $crit "$fdate" < $NAMED_PIPE  # cat is used to empty the pipe in case of duplicate
        RET=$?
        if [ "$RET" == "3" ]; then
            exec ~/lib/nagios/plugins/check_icmp -${ip_familly} -w "${warn}" -c "${crit}" "$dest"
        fi
    fi
else
    echo "fastchecker hook.sh called with invalid mode: $mode"
fi

