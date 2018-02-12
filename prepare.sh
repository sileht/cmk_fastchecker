#!/bin/bash

here=$(readlink -f $(dirname $0))
cd $here
virtualenv venv
venv/bin/pip install -r requirements.txt
ln -sf ../check_mk/cmk_fastchecker/cmk_fastchecker /omd/sites/ttnn/etc/init.d/cmk_fastchecker
ln -sf ../init.d/cmk_fastchecker /omd/sites/ttnn/etc/rc.d/30-cmk_fastchecker
chown -h ttnn: /omd/sites/ttnn/etc/rc.d/30-cmk_fastchecker /omd/sites/ttnn/etc/init.d/cmk_fastchecker
