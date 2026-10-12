#!/bin/sh
# stage 5: the whole matrix on the final binaries, one after the other (every command on CPUs 0-11). Reference = 42w (ref42w/vrs9syn42f = $WORK/vrs9w/vrs9syn42w, same sha256).
cd $WORK/vrsint5
P=test5/progress.txt
echo "start $(date +%H:%M:%S)" > $P
export LIVE_BIN=$HOME/vrsint5/vrs_t_live5
SN=$HOME/vrsint5/snap; RF=$HOME/vrsint5/ref42w; IX=$HOME/vrsint5/idx_base5
T=taskset
# T5-3 idem / replay / ooo (a single small file each)
S=$(ls snap/2026/08/29/*01a04b03*.jsonl)
$T -c 0-11 timeout 900 ./vrs_t_insert5 idem $S $HOME/vrsint5/test5/work_idem > test5/t53_idem.txt 2>&1; echo "idem rc=$?" >> test5/t53_idem.txt
$T -c 0-11 timeout 1500 ./vrs_t_insert5 replay $S $HOME/vrsint5/test5/work_replay > test5/b_replay.txt 2>&1; echo "replay rc=$?" >> test5/b_replay.txt
$T -c 0-11 timeout 300 ./vrs_t_insert5 ooo $S $HOME/vrsint5/test5/work_ooo > test5/b_ooo.txt 2>&1; echo "ooo rc=$?" >> test5/b_ooo.txt
echo "b done $(date +%H:%M:%S)" >> $P
# T5-1 (d): restart on the shards, assemble every rollout, compare with 42w
rm -rf test5/out_restore; mkdir -p test5/out_restore
$T -c 0-11 ./vrs_cli --stats --cpus 0-11 --workers 12 --out test5/out_restore $SN $IX $(cat test5_all.txt) > test5/t51_d_restore_lib.txt 2>&1
cd ref42w; rm -f w.sock
VRS9SYN_SERVE=1 VRS9_SEGWIN=1 CODEX_VRS_SOCK=$RF/w.sock nohup $T -c 0-11 ./vrs9syn42f serve $SN 258400 > ../test5/w_serve2.log 2> ../test5/w_serve2.err &
echo $! > w.pid
cd ..
i=0; while [ ! -S ref42w/w.sock ] && [ $i -lt 300 ]; do sleep 2; i=$((i+1)); done
sleep 1
python3 libsrc/cmp_orig.py ref42w/w.sock test5/out_restore 258400 $(cat test5_all.txt) > test5/t51_d_vs42w.txt 2>&1
kill $(cat ref42w/w.pid)
echo "d restore done $(date +%H:%M:%S)" >> $P
# T5-1 (d3) and (d4), T5-2 / T5-5 (f), T5-4 (h), crash/hole (g)
D3_MODE=alt     $T -c 0-11 timeout 1500 python3 libsrc/live_cmp3.py $SN $HOME/vrsint5/test5/live3a $RF $IX > test5/d3_alt.txt 2>&1
D3_MODE=insert  $T -c 0-11 timeout 1500 python3 libsrc/live_cmp3.py $SN $HOME/vrsint5/test5/live3i $RF $IX > test5/d3_insert.txt 2>&1
D3_MODE=watch   $T -c 0-11 timeout 1500 python3 libsrc/live_cmp3.py $SN $HOME/vrsint5/test5/live3w $RF $IX > test5/d3_watch.txt 2>&1
echo "d3 done $(date +%H:%M:%S)" >> $P
D4_MODE=watch   $T -c 0-11 timeout 1500 python3 libsrc/live_cmp4.py $SN $HOME/vrsint5/test5/live4w $RF $IX > test5/d4_watch.txt 2>&1
D4_MODE=insert  $T -c 0-11 timeout 1500 python3 libsrc/live_cmp4.py $SN $HOME/vrsint5/test5/live4i $RF $IX > test5/d4_insert.txt 2>&1
echo "d4 done $(date +%H:%M:%S)" >> $P
F_MODE=ordered  $T -c 0-11 timeout 3000 python3 test5/live5.py $SN $HOME/vrsint5/test5/live5o $RF $IX > test5/f_ordered.txt 2>&1;  echo "f ordered done $(date +%H:%M:%S)" >> $P
F_MODE=shuffled $T -c 0-11 timeout 3000 python3 test5/live5.py $SN $HOME/vrsint5/test5/live5s $RF $IX > test5/f_shuffled.txt 2>&1; echo "f shuffled done $(date +%H:%M:%S)" >> $P
$T -c 0-11 timeout 3000 python3 libsrc/live_cmp6.py $SN $HOME/vrsint5/test5/live6 $RF $IX > test5/g_crash_hole.txt 2>&1; echo "g done $(date +%H:%M:%S)" >> $P
H_THREADS=6 $T -c 0-11 timeout 3000 python3 libsrc/live_cmp7.py $SN $HOME/vrsint5/test5/live7 $RF $IX > test5/h_conc6.txt 2>&1; echo "h(6) done $(date +%H:%M:%S)" >> $P
echo "ALL DONE $(date +%H:%M:%S)" >> $P
