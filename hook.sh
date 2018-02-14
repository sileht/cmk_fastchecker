#!/bin/bash

here=$(readlink -f $(dirname $0))
cd $here

. fastpinger_utils.sh

SITENAME="$(id -un)"
CONF="/omd/sites/$SITENAME/etc/fastchecker.conf"
TMPDIR="/omd/sites/$SITENAME/tmp/fastchecker/hooks"
CMK_FASTPINGER_DUMP="/omd/sites/$SITENAME/tmp/fastpinger/fastpinger.dump"
mkdir -p $TMPDIR

NAMED_PIPE=$(mktemp --dry-run $TMPDIR/pipe.XXXXXX)
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

mode=$1
shift
if [ "$mode" == "check" -o "$mode" == "inventory" ]; then
    host="$1"
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
    fdate=$(stat  -c %x $CMK_FASTPINGER_DUMP | sed 's/\..*//g')

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
        sed -n "s/^$dest\s\s*:\s*//gp" $CMK_FASTPINGER_DUMP | grep -v "duplicate" > $NAMED_PIPE &
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
