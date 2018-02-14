
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

        echo "$state - $dest : rta ${rt_display}ms, lost ${loss}% (fastpinger at $fdate)|rta=${rt_display}ms;${rt_warn};${rt_cirt};0; pl=${loss}%;${loss_warn};${loss_crit};; rtmax=${rt_max}ms;;;; rtmin=${rt_min}ms;;;;"
        case $state in
            OK) return 0;;
            WARNING) return 1;;
            CRITICAL) return 2;;
        esac
    else
        return 3;
    fi
}

