#!/usr/bin/env -S python3

# Derived from the ORNL checknode script (bash).  Converted to python,
# modularized, added error checks, signal handling, etc.
# 

# This software is Apache 2.0 licensed 
# Copyright 2024 AMD

# Please see the included LICENSE file for details.

#
# Original developers @ ORNL: Matt Ezell, Nick Hegarty
# Python rewrite @ AMD: Joe Landman, Ken Wright, Vishal Singh
#

import argparse as ap
from multiprocessing import Process
import os
from pathlib import Path
import re
import signal
import socket
import subprocess as sp
import time

t_start = time.time()

ALL=False
VERBOSE=False
DRYRUN=False
RUNDIR='/tmp/amdchecknode'
TESTDIR=''
TIMEOUT=60
CHKNODECONF=''

# set up signal handlers so as to do the right thing
# if we catch specific signals
def sig_handler_setup():
   # handle all the signals that will terminate this
   # and send an error to slurm
   signal.signal(signal.SIGQUIT,sigexits)
   signal.signal(signal.SIGINT,sigexits)
   signal.signal(signal.SIGTRAP,sigexits)
   signal.signal(signal.SIGABRT,sigexits)
   signal.signal(signal.SIGALRM,sigexits)
   signal.signal(signal.SIGBUS,sigexits)

   # handle all the signals that will not terminate this
   signal.signal(signal.SIGFPE,sigwarns)
   signal.signal(signal.SIGUSR1,sigwarns)
   signal.signal(signal.SIGUSR2,sigwarns)
   signal.signal(signal.SIGSEGV,sigwarns)
   signal.signal(signal.SIGPIPE,sigwarns)
   signal.signal(signal.SIGCHLD,sigwarns)
   
def sigexits(number,frame):
   print(f"""TERMINAL SIGNAL number {number} caught\n{frame} """)

   # remove the lock file
   os.unlink("{RUNDIR}/lock")
   exit(1)

def sigwarns(number,frame):
   print(f"""NONTERMINAL SIGNAL number {number} caught\n{frame} """)
   # dont send stuff to slurm

#
# Find top level tests directory.  In order, look for
#  1) command line arguments (--testdir=/path/to/testdir
#      --config=/path/to/config --rundir=/path/to/rundir)
#  1) environment variable AMDCHECKNODEDIR
#  2) /etc/amdchecknode.conf
#  3) $HOME/.config/amdchecknode.conf
#  4) current directory amdnodecheck.conf
#
#  In the environment variable case, this will point to a directory with an amdchecknode.conf
#  file.
#  
#  Structure of amdchecknode.conf file are simple key value pairs.
# 
#  Mandatory keys
#
#  key               type           value 
#  TESTDIR           string         path to amdchecknode tests directory
#  RUNDIR            string         path to run directory where temp files are stored for IPC
#
#  Optional keys
#
#  VERBOSE           integer        1 == true, 0 == false
#  DRYRUN            integer        1 == true, 0 == false


def find_and_read_config(fname=''):
   global TESTDIR, SLURM_CONF, VERBOSE, DRYRUN, RUNDIR, TIMEOUT, CHKNODECONF
   if fname == None:
      fname=''

   # look for AMDCHECKNODEDIR
   if (fname == '') & os.environ.get('AMDCHECKNODEDIR',False):
      fname=os.environ.get('AMDCHECKNODEDIR')
   
   # look for /etc/amdchecknode.conf
   if (fname == '') & exists('/etc/amdchecknode.conf'):
      fname='/etc/amdchecknode.conf'
   
   # look for $HOME/.config/amdchecknode.conf
   if (fname == '') & exists(os.getenv('HOME') + '/.config/amdchecknode.conf'):
      fname=os.getenv('HOME') + '/.config/amdchecknode.conf'
   
   # look for current directory amdchecknode.conf
   if (fname == '') & exists(os.getcwd() + '/amdchecknode.conf'):
      fname=os.getcwd() + '/amdchecknode.conf'

   # if we still don't have a file name (fname) for the config,
   # print an error, and exit with 1
   if fname == '':
      print("WARNING: unable to find amdchecknode.conf\n")
      
   CHKNODECONF=fname
   try:
         
      with open(fname,"r") as f:
         lines=f.readlines()
      
      # minimal parser, pounds are comments, and only look at material to the 
      # left of them.  Skip blank lines
      for l in lines:
         kvp=l.split("#")[0].rstrip()
         if kvp == '':
            continue # ignore blank lines
         
         kvp_l = kvp.split('=')
         if kvp_l[0] == 'TESTDIR':
            TESTDIR=kvp_l[1]
         
         if kvp_l[0] == 'SLURM_CONF':
            SLURM_CONF=kvp_l[1]

         if kvp_l[0] == 'RUNDIR':
            RUNDIR=kvp_l[1]

         if kvp_l[0] == 'TIMEOUT':
            TIMEOUT=float(kvp_l[1])
      
         if kvp_l[0] == 'VERBOSE':
            if kvp_l[1] == 0:
               VERBOSE=False
            else:
               VERBOSE=True
            
         if kvp_l[0] == 'DRYRUN':
            if kvp_l[1] == 0:
               DRYRUN=False
            else:
               DRYRUN=True
   except:
      pass         

def command_line_options():
   global TESTDIR, SLURM_CONF, VERBOSE, DRYRUN, RUNDIR, TIMEOUT, CHKNODECONF
   p = ap.ArgumentParser( 
      prog='amdchecknode',
      description='Amdchecknode runs tests to verify node health before a scheduler based job launch'
   )
   #p.add_argument('-a', '--all', action='store_true', help="run all tests")
   #p.add_argument('-b', '--boot-mode', action='store_true', help="boot mode")
   #p.add_argument('-c', '--check-node-only', action='store_true', help="check node only")
   #p.add_argument('-l', '--local-checks-only', action='store_true', help="local checks only")
   #p.add_argument('-r', '--node-screen', action='store_true', help="run node screen")
   #p.add_argument('-u', '--force-undrain', action='store_true',help="force slurm undrain")
   p.add_argument('-v', '--verbose', action='store_true', help="force verbose")
   p.add_argument('--testdir', help="set test directory")
   p.add_argument('--rundir', help="set run directory")
   
   p.add_argument('--config', help="set config directory")
   #p.add_argument('--slurm', help="set slurm directory")
   #p.add_argument('--parallel', help="run tests in parallel (defaults to serial)")
   p.add_argument('--timeout', help="timeout in seconds for each script to complete")
   p.add_argument('--dryrun', action='store_true',help="print test names that would be run without running them")
   p.add_argument('--settings', action='store_true', help="report variable settings")
   args = p.parse_args()
   return args
 
def exists(path):
   p = Path(path)
   return p.exists()

def mkdir(path):
   p = Path(path)
   result = False
   try:
      result = p.mkdir(parents=True,exist_ok=True)
   except:
      pass
   return result

def touch(path):
   p = Path(path)
   result = False
   try:
      result = p.touch(exist_ok=True)
   except:
      pass
   return result

def check_if_running():
   lockfn=f"{RUNDIR}/lock"
   if VERBOSE: print(f"looking for {lockfn}")
   if exists(lockfn):
      if VERBOSE: print("amdchecknode lock in place, amdchecknode is running")
      return True
   return False

def prepare_run_directory():
   return mkdir(RUNDIR)

def set(path,content):
   p = Path(path)
   result = False
   try:
      result = p.open("w").write(content)
   except:
      pass
   return result

def run(cmdstr):
   global TIMEOUT
   # run a command, return a return code, stdout, and stderr
   # if thgere is an error running the command, return None, and two blank strings
   try:
      s = sp.run(cmdstr,
                  capture_output=True,
                  shell=True,
                  universal_newlines=True,
                  timeout=TIMEOUT
      )
   except:
      return (None,"","")
   return (s.returncode, s.stdout, s.stderr)

def send_failure_notification():
   # this is where we send either a RedFish event,
   # or something similar
   pass

def before_run():
   global TIMEOUT, VERBOSE, TESTDIR, DRYRUN, SLURM_CONF, RUNDIR
   args = command_line_options()
   find_and_read_config(fname=args.config)   
   
   if args.testdir:  TESTDIR=args.testdir
   if args.timeout:  TIMEOUT=float(args.timeout)
   if args.dryrun:   DRYRUN=args.dryrun
   if args.rundir:   RUNDIR=args.rundir
   if args.verbose:  VERBOSE=args.verbose
   
   if args.settings:
      print(f"""
VERBOSE={VERBOSE}            
TIMEOUT={TIMEOUT}
DRYRUN={DRYRUN}
TESTDIR={TESTDIR}
RUNDIR={RUNDIR}
""")
      exit(0)

   if check_if_running():
      print("amdchecknode is currently running\n")
      exit(0)

   if prepare_run_directory() == False:
      if VERBOSE: print(f"Unable to create {RUNDIR}")
      exit(1)

   mkdir("{RUNDIR}/journalcache")
   touch("{RUNDIR}/lock")
   if set("{RUNDIR}/state","running") == False:
      print(f"Unable to create {RUNDIR}/state ")
      exit(1)


   # sanity check boot status
   if re.match(r"No jobs running",run('systemctl list-jobs')[1]):
      touch("{RUNDIR}/booted")
   else:
      if VERBOSE: print("Node is still booting\n")
      os.unlink("{RUNDIR}/booted")
      exit(1)
   


def main():
   global TIMEOUT, DRYRUN, VERBOSE
   ################################################################################
   # tests: return a 0 on success, and non-zero on failure
   ################################################################################

   test_list = os.listdir(TESTDIR)
   test_list.sort()
   tests = {}

   PASSED=True
   # run them in serial for now
   for test in test_list:
      testname = TESTDIR + '/' + test
      if VERBOSE: print(f"test = {test}, file = {testname}")
      if DRYRUN:
         print(" ... Dry run, not actually running this code\n")
      else:
         if VERBOSE: print(f" Beginning run of {test}")
         t_initial = time.time()
         ret = run(testname)
         t_final = time.time()
         dt = t_final - t_initial
         to = False
         if dt >= TIMEOUT:
            to = True
         tests[test] = {'name': test, 
                        'runtime': t_final-t_initial, 
                        'stderr': ret[2],
                        'stdout': ret[1],
                        'returncode': ret[0],
                        'timed_out': to
                        }
         if VERBOSE: print(f" End of run {test}\n delta t = {t_final-t_initial:.3f}\n return code = {ret[0]}\n stderr = {ret[2]}\n stdout = {ret[1]}\n")

if __name__ == '__main__':
   before_run()

   # run main() with a timeout
   p1 = Process(target=main, name='main loop')
   if VERBOSE: print("starting main process\n")
   p1.start()
   p1.join(timeout=TIMEOUT)
   p1.terminate()
   if VERBOSE: print("completed")
