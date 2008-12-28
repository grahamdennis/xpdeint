#!/usr/bin/env python
# encoding: utf-8
"""This is the list of preferences that we don't want to bother listing at runtime.
Chief amongst them are the compile options.

We start here just listing these preferences, and then later we can generate this file via some clever method.  Or autoconf."""

CC="g++"
CFLAGS="-O3 -ffast-math -funroll-all-loops -fomit-frame-pointer"
MPICC="mpic++"
MPICFLAGS=""

versionString = '0.6 "A Physicist is an atom\'s way of knowing about atoms."'