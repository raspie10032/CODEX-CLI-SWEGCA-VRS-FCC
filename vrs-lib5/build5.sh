#!/bin/sh
set -e
cd $WORK/vrsint5
CXX="taskset -c 0-11 g++ -O2 -std=c++20 -mcx16 -pthread -fPIC -Wall -Wno-unused-function -Wno-unused-variable -Wno-misleading-indentation -I swegca_cpp"
$CXX -c vrs_lib.cpp -o vrs_lib.o 2>&1 | grep -E "error|warning" -A4 | head -${1:-80} || true
[ -f vrs_lib.o ] || exit 1
rm -f libvrs.a
ar rcs libvrs.a vrs_lib.o obj/evidence_rules.o obj/sha256.o obj/strong_types.o
ls -la libvrs.a
