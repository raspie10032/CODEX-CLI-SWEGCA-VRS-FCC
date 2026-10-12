#!/bin/sh
# repeats the concurrent insert test without the 42w reference (cells live vs cold, observer hashes) to catch a rare difference
cd $WORK/vrsint5
export LIVE_BIN=$HOME/vrsint5/vrs_t_live5
R=test5/q; rm -rf $R; mkdir -p $R
for i in $(seq 1 ${1:-12}); do
  H_THREADS=12 H_SEED=$i taskset -c 0-11 timeout 600 python3 test5/live7q.py $HOME/vrsint5/snap $HOME/vrsint5/$R/w$i $HOME/vrsint5/ref42w $HOME/vrsint5/idx_base5 > $R/o$i.txt 2>&1
  echo "run $i: $(grep -E 'fails' $R/o$i.txt | tail -1) | $(grep -E 'cells live vs cold' $R/o$i.txt | cut -c1-60) | $(grep -c differs $R/o$i.txt) differs" >> $R/summary.txt
done
echo done >> $R/summary.txt
