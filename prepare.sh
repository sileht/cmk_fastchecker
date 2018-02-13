#!/bin/bash

SITENAME=$(id -un)
SITE="/omd/sites/$SITENAME"

here=$(readlink -f $(dirname $0))
cd $here

set -x
set -e

# ENSURE WE DIDN'T USE OMD THING
unset PYTHONPATH
unset LD_LIBRARY_PATH
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export PIP_CONFIG_FILE=$here/pip.conf

[ ! -d venv ] && virtualenv -vvv venv || true
venv/bin/pip install -U -r requirements.txt

echo "BASE_DIR=\"$here\"" > $SITE/etc/fastchecker.conf
ln -sf $here/etc/init.d/fastchecker $SITE/etc/init.d/
ln -sf $here/etc/init-hooks.d/icinga-restart-pre $SITE/etc/init-hooks.d
ln -sf $here/etc/cron.d/fastpinger $SITE/etc/cron.d
ln -sf ../init.d/fastchecker $SITE/etc/rc.d/30-fastchecker
