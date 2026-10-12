#!/bin/sh
# T5-4: the lines of the same file are handed in by 12 threads in a shuffled order (5 runs), against the ordered insertion (1 thread, in order) and fresh 42w.
# Each run is live_cmp7.py (3 files A, B, C; H_THREADS threads PER FILE = 36 threads on 3 files at 12 threads each); pass: every run compares 0 differences with 42w on the
# whole tree and the cells of every run are byte-identical to the cells of the ordered run.
cd $WORK/vrsint5
export LIVE_BIN=$HOME/vrsint5/vrs_t_live5
SN=$HOME/vrsint5/snap; RF=$HOME/vrsint5/ref42w; IX=$HOME/vrsint5/idx_base5
R=test5/t54; mkdir -p $R
H_THREADS=1 H_SEED=0 taskset -c 0-11 timeout 3000 python3 test5/live7.py $SN $HOME/vrsint5/test5/live7_ord $RF $IX > $R/h_ordered.txt 2>&1
for s in 1 2 3 4 5; do
  H_THREADS=12 H_SEED=$s taskset -c 0-11 timeout 3000 python3 test5/live7.py $SN $HOME/vrsint5/test5/live7_s$s $RF $IX > $R/h_t12_seed$s.txt 2>&1
  if cmp -s test5/live7_ord/cells_live.txt test5/live7_s$s/cells_live.txt; then echo "seed $s: cells byte-identical to the ordered run" >> $R/cells_cmp.txt; else echo "seed $s: cells DIFFER from the ordered run" >> $R/cells_cmp.txt; fi
done
echo done > $R/done.txt
