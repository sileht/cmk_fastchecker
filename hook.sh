#!/bin/bash

max() {
    printf "%s\n" "$@" | sort -g | grep -v -- '-' | tail -n1
}
min() {
    printf "%s\n" "$@" | sort -g | grep -v -- '-' | head -n1
}

CMK_FASTPINGER_DUMP="/omd/sites/ttnn/tmp/cmk_fastpinger/cmk_fastpinger.dump"
mode=$1
if [ "$mode" != "ping" ]; then
    url="$@"
    curl -s http://localhost:5001/$url | (read ret; cat ; exit $ret)
    if [ "$?" == "7" ]; then
        echo "cmk_fastchecker unreachable"
        exit 1
    fi

else
    shift
    fdate=$(stat  -c %x $CMK_FASTPINGER_DUMP | sed 's/\..*//g')

    OPTS=`getopt -o 46w:c:n:i:I:m:l:t:b:H: -n 'parse-options' -- "$@"`
    eval set -- "$OPTS"
    ip_familly=4
    while true; do
        case "$1" in
            -4|-6) ip_familly=${1#-}; shift;;
            -w) warn="$2"; shift ; shift ;;
            -c) crit="$2"; shift ; shift ;;
            -n|-i|-I|-l|-t|-b) shift ; shift ;;  # We hardcode them in cmk_fastpinger
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
        sed -n "s/^$dest\s\s*:\s*//gp" $CMK_FASTPINGER_DUMP | grep -v "duplicate" | (
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

                echo "$state - $dest : rta ${rt_display}ms, lost ${loss}% (fastpinger at $fdate)|rta=${rt_display}ms;${rt_warn};${rt_cirt};0; pl=${loss}%;${loss_warn};${loss_crit};; rtmax=${rt_max}ms;;;; rtmin=${rt_min}ms;;;;"
                case $state in
                    OK) exit 0;;
                    WARNING) exit 1;;
                    CRITICAL) exit 2;;
                    *) exit 3;;
                esac
            else
                exec ~/lib/nagios/plugins/check_icmp -${ip_familly} -w "${warn}" -c "${crit}" "$dest"
            fi
        );
	ret=$?
	exit $ret
    fi
fi
