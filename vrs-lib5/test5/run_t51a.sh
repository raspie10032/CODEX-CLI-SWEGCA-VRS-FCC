#!/bin/sh
# T5-1 (a): fresh lib5 vs fresh 42w (serve), then vs 42f (counted separately)
cd $WORK/vrsint5/ref42w
rm -f w.sock
VRS9SYN_SERVE=1 VRS9_SEGWIN=1 CODEX_VRS_SOCK=$HOME/vrsint5/ref42w/w.sock nohup taskset -c 0-11 ./vrs9syn42f serve $HOME/vrsint5/snap 258400 > ../test5/w_serve.log 2> ../test5/w_serve.err &
echo $! > w.pid
cd ..
i=0; while [ ! -S ref42w/w.sock ] && [ $i -lt 300 ]; do sleep 2; i=$((i+1)); done
sleep 1
python3 libsrc/cmp_orig.py ref42w/w.sock test5/out_fresh 258400 $(cat test5_all.txt) > test5/t51_a_vs42w.txt 2>&1
kill $(cat ref42w/w.pid)
cd orig
rm -f f.sock
VRS9SYN_SERVE=1 VRS9_SEGWIN=1 CODEX_VRS_SOCK=$HOME/vrsint5/orig/f.sock nohup taskset -c 0-11 ./vrs9syn42f serve $HOME/vrsint5/snap 258400 > ../test5/f_serve.log 2> ../test5/f_serve.err &
echo $! > f.pid
cd ..
i=0; while [ ! -S orig/f.sock ] && [ $i -lt 300 ]; do sleep 2; i=$((i+1)); done
sleep 1
python3 libsrc/cmp_orig.py orig/f.sock test5/out_fresh 258400 $(cat test5_all.txt) > test5/t51_a_vs42f.txt 2>&1
kill $(cat orig/f.pid)
echo done > test5/t51a_done.txt
