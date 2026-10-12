#!/bin/sh
# Round 6 tests (VRS_코덱스일체화_v1.md §8.4), CPUs 0-11 only. Progress: test6/t6_progress.txt
cd $WORK/vrsint6
F=test6/t6_progress.txt
echo "start $(date +%H:%M:%S) libvrs.a $(sha256sum libvrs.a | cut -c1-16) libvrs_dbg.a $(sha256sum libvrs_dbg.a | cut -c1-16)" > $F
SN=$HOME/vrsint6/snap; SNV=$WORK/vrsint6/snap
sed "s#$WORK/vrsint5/snap#$SN#" test6_all.txt > test6_all.txt
sed -i "s#test6_all.txt#test6_all.txt#g" test6/*.sh

# ---- T6-3: fresh lib6 vs fresh 42x, all 462 files (also builds idx_base6, through the /home spelling)
rm -rf idx_base6 test6/out_fresh; mkdir -p test6/out_fresh
( time taskset -c 0-11 ./vrs_cli --stats --cpus 0-11 --workers 12 --out test6/out_fresh $SN idx_base6 $(cat test6_all.txt) ) > test6/d_fresh_lib.txt 2> test6/d_fresh_time.txt
echo "fresh build done $(date +%H:%M:%S)" >> $F
rm -f test6/t51a_done.txt
sh test6/run_t51a.sh
echo "T6-3 done $(date +%H:%M:%S): $(tail -1 test6/t51_a_vs42w.txt)" >> $F

# ---- T6-1 (a): built through /home, reopened through /var/home: shards rewritten = 0
taskset -c 0-11 ./vrs_cli --stats --cpus 0-11 --workers 12 $SNV idx_base6 $(sed -n 1p test6_all.txt | sed "s#^/home/#/var/home/#") > test6/t61_reopen_var.txt 2>&1
# the other way: built through /var/home, reopened through /home
rm -rf test6/idx_var
taskset -c 0-11 ./vrs_cli --stats --cpus 0-11 --workers 12 $SNV test6/idx_var $(sed -n 1p test6_all.txt | sed "s#^/home/#/var/home/#") > test6/t61_build_var.txt 2>&1
taskset -c 0-11 ./vrs_cli --stats --cpus 0-11 --workers 12 $SN test6/idx_var $(sed -n 1p test6_all.txt) > test6/t61_reopen_home.txt 2>&1
# (b): one file inserted through two spellings is one session, both answers equal
W=$HOME/vrsint6/test6/alias; rm -rf $W; mkdir -p $W/sessions/2026/01/01 $W/idx $W/sessions/2027/01/01
for f in $(ls -S snap/2026/0[5-9]/*/*.jsonl | tail -n +20 | head -30); do ln $f $W/sessions/2026/01/01/$(basename $f); done
ln -s $W/sessions/2027 $W/sessions/lnk
SRC=$(ls snap/2026/08/29/*01a04b03*.jsonl)
NAME=rollout-2027-01-01T00-00-00-01f0c000-0000-7000-8000-000000000001.jsonl
taskset -c 0-11 ./vrs_cli --stats --cpus 0-11 --workers 12 $W/sessions $W/idx > test6/t61_alias_build.txt 2>&1
taskset -c 0-11 ./t6drv alias $W/sessions $W/idx $SRC $W/sessions/2027/01/01/$NAME $WORK/vrsint6/test6/alias/sessions/lnk/01/01/$NAME 200 > test6/t61_alias.txt 2>&1
echo "alias rc=$?" >> test6/t61_alias.txt
# (c): the same, the first line handed in before its day directory exists
NAME2=rollout-2027-02-01T00-00-00-01f0c000-0000-7000-8000-000000000002.jsonl
T6_LATE_DIR=1 taskset -c 0-11 ./t6drv alias $W/sessions $W/idx $SRC $W/sessions/2027/02/01/$NAME2 $WORK/vrsint6/test6/alias/sessions/lnk/02/01/$NAME2 200 > test6/t61_alias_late.txt 2>&1
echo "alias late rc=$?" >> test6/t61_alias_late.txt
# (d) extra check: the root moved (renamed on the same file system) keeps its shards (the old path-spelling stale rule is gone under D12)
mv snap snapmv
taskset -c 0-11 ./vrs_cli --stats --cpus 0-11 --workers 12 $HOME/vrsint6/snapmv idx_base6 $(sed -n 1p test6_all.txt | sed "s#/snap/#/snapmv/#") > test6/t61_moved.txt 2>&1
mv snapmv snap
echo "T6-1 done $(date +%H:%M:%S)" >> $F

# ---- T6-2: ready held 3 s (debug build), wait + assemble = the unheld answer; ready < 0 imitation is an error
P=$(sed -n 1p test6_all.txt)
taskset -c 0-11 ./t6drv_dbg wait $SN idx_base6 $P test6/t62_plain.items > test6/t62_plain.txt 2>&1; echo "rc=$?" >> test6/t62_plain.txt
VRS_DBG_HOLD_READY_MS=3000 taskset -c 0-11 ./t6drv_dbg wait $SN idx_base6 $P test6/t62_hold.items > test6/t62_hold.txt 2>&1; echo "rc=$?" >> test6/t62_hold.txt
if cmp -s test6/t62_plain.items test6/t62_hold.items; then echo "items equal" >> test6/t62_hold.txt; else echo "items DIFFER" >> test6/t62_hold.txt; fi
# held over a cold index (the case of the app after a format change): wait covers the whole rebuild
rm -rf test6/idx_cold
VRS_DBG_HOLD_READY_MS=3000 taskset -c 0-11 ./t6drv_dbg wait $SN test6/idx_cold $P test6/t62_cold.items > test6/t62_cold.txt 2>&1; echo "rc=$?" >> test6/t62_cold.txt
if cmp -s test6/t62_plain.items test6/t62_cold.items; then echo "items equal" >> test6/t62_cold.txt; else echo "items DIFFER" >> test6/t62_cold.txt; fi
VRS_DBG_FAIL_READY=1 taskset -c 0-11 ./t6drv_dbg wait $SN idx_base6 $P test6/t62_fail.items > test6/t62_fail.txt 2>&1; echo "rc=$?" >> test6/t62_fail.txt
echo "T6-2 done $(date +%H:%M:%S)" >> $F

# ---- T6-4: T5-4 seed 1 + ordered, T5-6 five restarts, T5-7 100 processes
sed -i "s/for s in 1 2 3 4 5; do/for s in 1; do/" test6/run_t54.sh
rm -rf test6/t54; sh test6/run_t54.sh
echo "T5-4 done $(date +%H:%M:%S)" >> $F
for i in 1 2 3 4 5; do taskset -c 0-11 ./vrs_cli --stats --cpus 0-11 --workers 12 $SN idx_base6 $(sed -n 1p test6_all.txt) | cut -c1-300; done > test6/t56.txt 2>&1
echo "T5-6 done $(date +%H:%M:%S)" >> $F
rm -f test6/t57_done.txt; sh test6/run_t57.sh
echo "T5-7 done $(date +%H:%M:%S)" >> $F
echo "ALL DONE $(date +%H:%M:%S)" >> $F
