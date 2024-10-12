#!/bin/bash

# argument 1 is the path you want to install to.  If not provided
# this will default to /opt/rocm/amdchecknode
INSTALLPATH=${1:-"/opt/rocm/amdchecknode"}
ROCMPATH=${2:-"/opt/rocm"}
TESTPATH=${3:-$INSTALLPATH/tests}

echo "Install path = $INSTALLPATH"
echo "ROCMPATH = $ROCMPATH"
echo "TESTDIR = $TESTDIR"

mkdir -p $INSTALLPATH
cp -rvf amdchecknode* LICENSE README.md \
    rvs tests functions include  $INSTALLPATH

# create an /etc/amdchecknode.conf file
cp -fv amdchecknode.conf /etc

echo "You need to have rocm-validation-suite installed.  This has"
echo "a dependency upon libyaml-cpp. Please verify that you can run"
echo "${ROCMPATH}/bin/rvs -t"
echo 
echo "You need at least Python 3.11 for this code to work."