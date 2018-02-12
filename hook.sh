#!/bin/bash

set -o pipefail

cleanup() {
	if [ "$?" == "7" ]; then
		echo "cmk_fastchecker unreachable"
		exit 1
	fi
}
trap cleanup EXIT
curl -s http://localhost:5001/$* | (read ret; cat ; exit $ret)
