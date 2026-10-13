#!/bin/sh
# Round 7 tests (VRS_코덱스일체화_v1.md §9.4), CPUs 0-11 only. Progress: test6/t7_progress.txt
cd $WORK/vrsint7
F=test6/t7_progress.txt
echo "start $(date +%H:%M:%S) libvrs.a $(sha256sum libvrs.a | cut -c1-16)" > $F
SN=$HOME/vrsint7/snap
sed "s#$WORK/vrsint6/snap#$SN#" $WORK/vrsint6/test6_all.txt > test6_all.txt

# ---- T7-3: fresh lib7, then against lib6's answers and against fresh 42x7
rm -rf idx_base6 test6/out_fresh; mkdir -p test6/out_fresh
( time taskset -c 0-11 ./vrs_cli --stats --cpus 0-11 --workers 12 --out test6/out_fresh $SN idx_base6 $(cat test6_all.txt) ) > test6/d_fresh_lib.txt 2> test6/d_fresh_time.txt
same=0; diff=0; : > test6/t73_vs_lib6.txt
for f in test6/out_fresh/*; do b=$(basename $f); if cmp -s $f $WORK/vrsint6/test6/out_fresh/$b; then same=$((same+1)); else diff=$((diff+1)); echo "DIFF $b" >> test6/t73_vs_lib6.txt; fi; done
echo "vs lib6: same $same diff $diff" >> test6/t73_vs_lib6.txt
echo "T7-3 lib6 done $(date +%H:%M:%S): $(tail -1 test6/t73_vs_lib6.txt)" >> $F
rm -f test6/t51a_done.txt
sh test6/run_t51a.sh
echo "T7-3 42x7 done $(date +%H:%M:%S): $(tail -1 test6/t51_a_vs42w.txt)" >> $F

# ---- T7-5: T6-1 (alias) and T6-2 (wait), then T5-4 seed 1 + ordered, T5-6, T5-7
W=$HOME/vrsint7/test6/alias; rm -rf $W; mkdir -p $W/sessions/2026/01/01 $W/idx $W/sessions/2027/01/01
for f in $(ls -S snap/2026/0[5-9]/*/*.jsonl | tail -n +20 | head -30); do ln $f $W/sessions/2026/01/01/$(basename $f); done
ln -s $W/sessions/2027 $W/sessions/lnk
SRC=$(ls snap/2026/08/29/*01a04b03*.jsonl)
NAME=rollout-2027-01-01T00-00-00-01f0c000-0000-7000-8000-000000000001.jsonl
taskset -c 0-11 ./vrs_cli --stats --cpus 0-11 --workers 12 $W/sessions $W/idx > test6/t61_alias_build.txt 2>&1
taskset -c 0-11 ./t6drv alias $W/sessions $W/idx $SRC $W/sessions/2027/01/01/$NAME $WORK/vrsint7/test6/alias/sessions/lnk/01/01/$NAME 200 > test6/t61_alias.txt 2>&1; echo "alias rc=$?" >> test6/t61_alias.txt
NAME2=rollout-2027-02-01T00-00-00-01f0c000-0000-7000-8000-000000000002.jsonl
T6_LATE_DIR=1 taskset -c 0-11 ./t6drv alias $W/sessions $W/idx $SRC $W/sessions/2027/02/01/$NAME2 $WORK/vrsint7/test6/alias/sessions/lnk/02/01/$NAME2 200 > test6/t61_alias_late.txt 2>&1; echo "alias late rc=$?" >> test6/t61_alias_late.txt
P=$(sed -n 1p test6_all.txt)
taskset -c 0-11 ./t6drv_dbg wait $SN idx_base6 $P test6/t62_plain.items > test6/t62_plain.txt 2>&1; echo "rc=$?" >> test6/t62_plain.txt
VRS_DBG_HOLD_READY_MS=3000 taskset -c 0-11 ./t6drv_dbg wait $SN idx_base6 $P test6/t62_hold.items > test6/t62_hold.txt 2>&1; echo "rc=$?" >> test6/t62_hold.txt
if cmp -s test6/t62_plain.items test6/t62_hold.items; then echo "items equal" >> test6/t62_hold.txt; else echo "items DIFFER" >> test6/t62_hold.txt; fi
VRS_DBG_FAIL_READY=1 taskset -c 0-11 ./t6drv_dbg wait $SN idx_base6 $P test6/t62_fail.items > test6/t62_fail.txt 2>&1; echo "rc=$?" >> test6/t62_fail.txt
echo "T6-1/T6-2 done $(date +%H:%M:%S)" >> $F
rm -rf test6/t54 test6/live7_*; sh test6/run_t54.sh
echo "T5-4 done $(date +%H:%M:%S)" >> $F
for i in 1 2 3 4 5; do taskset -c 0-11 ./vrs_cli --stats --cpus 0-11 --workers 12 $SN idx_base6 $(sed -n 1p test6_all.txt) | cut -c1-300; done > test6/t56.txt 2>&1
echo "T5-6 done $(date +%H:%M:%S)" >> $F
rm -f test6/t57_done.txt; sh test6/run_t57.sh
echo "T5-7 done $(date +%H:%M:%S)" >> $F
echo "ALL DONE $(date +%H:%M:%S)" >> $F
