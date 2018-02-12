#!/bin/bash

set -o pipefail

cleanup() {
	if [ "$?" == "7" ]; then
		echo "cmk_fastchecker unreachable"
		exit 1
	fi
}
trap cleanup EXIT

url="$@"
# op=${url%/*}
#if [ "$op" == "inventory" ]; then
#   exec check_mk --cache --check-discovery ${url#*/}
#elif [ "$op" == "check" ]; then
#   exec python /omd/sites/ttnn/var/check_mk/precompiled/${url#*/}
#fi
curl -s http://localhost:5001/$url | (read ret; cat ; exit $ret)
