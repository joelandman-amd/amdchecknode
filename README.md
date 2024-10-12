# AMD checknode

This is derived from ORNL checknode (https://github.com/olcf/frontier-checknode).

# Overview

Amdchecknode provides a framework to check a node's state in order to determine if a job has all the resources and performance it needs to succeed.  It depends upon end user written scripts, examples of which are provided in the tests directory.  These scripts drive other programs, and the return values are checked.  A return value of 0 means a script has succeeded, and by extension, the code that the script has run. A non-zero return value will terminate the amdchecknode script, and return a non-zero value to the calling process.

The tests directory contains scripts that each perform one check.  The check could be anything that you find useful for determining node state. The rvs_* scripts drive radeon-validation-script based runs, and thus depend upon rvs being installed.

To add or remove scripts, simply move them into or out of the tests directory.  The scripts can run independently of amdchecknode.  This simplifies testing of the scripts.

# Installation

Run the install.sh script as root.  Arguments are optional.  1st argument is the installation path, where you want the script, the tests and other directories to live.  By default it will send these to `/opt/rocm/amdchecknode` .  

Make sure you have rocm-validation-suite installed.  The install script will place a config file at `/etc/amdchecknode.conf`.  You should edit this to make sure it matches where you have installed amdchecknode, and the path to
your rocm installation.  The rvs binary and libraries are assumed to be under the ROCMPATH.  Note that this also requires libyaml-cpp in the system image.

You need to use Python 3.11 or higher for this tool.  Python 3.6.x will not work.

# Running 

Assuming all pathing is correct, you can try this to validate the installation.

```
landman@phonon:~/work/amdchecknode$ /opt/rocm/amdchecknode/amdchecknode.py -h
usage: amdchecknode [-h] [-v] [--testdir TESTDIR] [--rundir RUNDIR] [--rocmdir ROCMDIR]
                    [--config CONFIG] [--timeout TIMEOUT] [--dryrun] [--settings] [--force]

Amdchecknode runs tests to verify node health before a scheduler based job launch

options:
  -h, --help         show this help message and exit
  -v, --verbose      force verbose
  --testdir TESTDIR  set test directory
  --rundir RUNDIR    set run directory
  --rocmdir ROCMDIR  set rocm install directory
  --config CONFIG    set config directory
  --timeout TIMEOUT  timeout in seconds for each script to complete
  --dryrun           print test names that would be run without running them
  --settings         report variable settings
  --force            force run to occur despite a lock file being present
```

This script needs to be run with elevated privileges. 

```
landman@phonon:~/work/amdchecknode$ sudo /opt/rocm/amdchecknode/amdchecknode.py --verbose
looking for /tmp/amdchecknode/lock
starting main process

test = boot_error_checks, cmd = 'ROCMDIR=/opt/rocm /opt/rocm/amdchecknode/tests/boot_error_checks '
 Beginning run of boot_error_checks
 End of run boot_error_checks
 delta t = 0.004
 return code = 0
 stderr = 
 stdout = 

test = check_for_running_jobs, cmd = 'ROCMDIR=/opt/rocm /opt/rocm/amdchecknode/tests/check_for_running_jobs '
 Beginning run of check_for_running_jobs
test check_for_running_jobs exited with a non-zero return code, terminating run


stdout=

stderr=/opt/rocm/amdchecknode/tests/check_for_running_jobs: line 8: scontrol: command not found



completed
Exiting due to a test failure

jlandman@phonon:~/work/amdchecknode$ echo $?
1
```

If a test fails, it will cause the entire script to fail, and return a non-zero value.  