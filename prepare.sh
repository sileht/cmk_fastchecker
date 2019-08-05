#!/bin/bash

SITENAME=$(id -un)
SITE="/omd/sites/$SITENAME"

BASE_DIR=$(readlink -f $(dirname $0))
cd $BASE_DIR

set -x
set -e

# ENSURE WE DIDN'T USE OMD THING
unset PYTHONPATH
unset LD_LIBRARY_PATH
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export PIP_CONFIG_FILE=$BASE_DIR/pip.conf

pip install -r requirements.txt

cat > $SITE/etc/fastchecker.conf <<EOF
export BASE_DIR="$BASE_DIR"
EOF

. $BASE_DIR/paths.conf

mkdir -p $FASTCHECKER_TMPPATH $FASTPINGER_TMPPATH $FASTPINGER_VARPATH
ln -sf $BASE_DIR/etc/init.d/fastchecker $SITE/etc/init.d/
ln -sf $BASE_DIR/etc/init-hooks.d/icinga-restart-pre $SITE/etc/init-hooks.d
ln -sf $BASE_DIR/etc/cron.d/fastpinger $SITE/etc/cron.d
ln -sf ../init.d/fastchecker $SITE/etc/rc.d/30-fastchecker
