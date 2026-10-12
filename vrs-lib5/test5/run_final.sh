#!/bin/sh
# the whole stage-5 matrix on the final binaries, one after the other (CPUs 0-11 only)
cd $WORK/vrsint5
F=test5/final_progress.txt
echo "start $(date +%H:%M:%S) libvrs.a sha256 $(sha256sum libvrs.a | cut -c1-16)" > $F
SN=$HOME/vrsint5/snap
# fresh build, index for the later runs, answers for T5-1 (a)
rm -rf idx_base5 test5/out_fresh; mkdir -p test5/out_fresh
( time taskset -c 0-11 ./vrs_cli --stats --cpus 0-11 --workers 12 --out test5/out_fresh $SN idx_base5 $(cat test5_all.txt) ) > test5/d_fresh_lib.txt 2> test5/d_fresh_time.txt
echo "fresh build done $(date +%H:%M:%S)" >> $F
rm -f test5/t51a_done.txt
sh test5/run_t51a.sh
echo "T5-1 (a) done $(date +%H:%M:%S)" >> $F
rm -f test5/progress.txt
sh test5/run_all5.sh
echo "matrix done $(date +%H:%M:%S)" >> $F
rm -rf test5/t54
sh test5/run_t54.sh
echo "T5-4 done $(date +%H:%M:%S)" >> $F
rm -rf test5/w52b; mkdir -p test5/w52b
python3 test5/t52b.py $SN $HOME/vrsint5/test5/w52b $HOME/vrsint5/idx_base5 > test5/t52b.txt 2>&1
echo "T5-2b done $(date +%H:%M:%S)" >> $F
# T5-6: five restarts on the index, time to the first answer
for i in 1 2 3 4 5; do taskset -c 0-11 ./vrs_cli --stats --cpus 0-11 --workers 12 $SN idx_base5 $(sed -n 1p test5_all.txt) | cut -c1-260; done > test5/t56.txt 2>&1
echo "T5-6 done $(date +%H:%M:%S)" >> $F
rm -f test5/t57_done.txt
sh test5/run_t57.sh
echo "T5-7 done $(date +%H:%M:%S)" >> $F
echo "ALL DONE $(date +%H:%M:%S)" >> $F
