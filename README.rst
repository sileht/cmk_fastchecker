cmk_fastchecker
===============

**Warning this is POC code.**

This is a CheckMK helper to keep in memory CheckMK python stuffs, so a host check take 0.05s instead of 2s.

By default, nagios double fork and then run a python script built by check_mk.
This consumes a ton of cpu, starting the python VM take ages, the check file is
read from disk again and again.  While the check itself is just a tcp
connection to the server and then a connection to an unix socket to report back
the result to nagios.

CheckMK propose a new CORE called CMC (instead of using nagios/icinga), written
in Python that doesn't have all of this issue because it's all python and all
preloaded. But this is not a opensource software...

So here the idea:

I wrote the small daemon that:

* Load CheckMK modules and all host checks in memory, (it take somes times to start).
* Provide a HTTP server to run check and inventory

Performance example:

.. code-block::

        $ time cmk www ; echo $?
        OK - Agent version 1.4.0p24, execution time 0.5 sec|execution_time=0.541 user_time=0.070 system_time=0.010 children_user_time=0.000 children_system_time=0.000 cmk_time_agent=0.464

        real    0m1.742s
        user    0m1.220s
        sys     0m0.052s
        0

We can see the overhead of Python VM and module loading take 1.2seconds

.. code-block::

        $ time curl -s http://localhost:5001/check/www
        0
        OK - Agent version 1.4.0p24, execution time 0.5 sec|execution_time=0.508 user_time=0.040 system_time=0.000 children_user_time=0.000 children_system_time=0.000 cmk_time_agent=0.464

        real    0m0.523s
        user    0m0.008s
        sys     0m0.004s

Here, the overhead of curl is only 0.008s

So for our supervision that checks 657 hosts every minute, it's 1.2 * 657 / 60 == 13.14 minutes of time wasted on each cycle.

The load of our tiny Intel NUC server was around 40-60..., Now it's 0.6.

The goals of cmk_fastchecker is to make icinga/nagios doing only the
active_checks/scheduling/notification stuffs. cmk_fastchecker will run all
python stuffs.


Configuration
-------------

Looks at the prepare.sh script to prepare the environment, and then edit
etc/icinga/conf.d/check_mk_templates.cfg, replace the command_line of two main
checks by:

.. code-block::

        # Calling check_mk with precompiled checks
        define command {
          command_name  check-mk
          # command_line  python $USER4$/var/check_mk/precompiled/"$HOSTNAME$"
          command_line  $USER4$/etc/check_mk/cmk_fastchecker/hook.sh "check/$HOSTNAME$"
        }

        # Inventory check
        define command {
          command_name  check-mk-inventory
          # command_line  check_mk --cache --check-discovery "$HOSTNAME$"
          command_line  $USER4$/etc/check_mk/cmk_fastchecker/hook.sh "inventory/$HOSTNAME$"
        }
        ```
