#!/bin/sh
# T5-7: open/close in the shapes of S1-S5, 100 rounds, the library process is ended by std::exit(0) with workers running (how=exit) or after vrs_close (how=close).
# pass: no process ends by a signal (exit code >= 128), no open failure; answers (exit 3) are counted separately.
cd $WORK/vrsint5
W=$WORK/vrsint5/test5/t57
rm -rf $W; mkdir -p $W
SRC=$(ls snap/2026/08/29/*01a04b03*.jsonl)
NL=$(wc -l < $SRC)
echo "src $SRC lines $NL" > test5/t57_result.txt
ls -S snap/2026/0[5-9]/*/*.jsonl | tail -n +20 | head -60 > $W/base_list.txt
tot=0; sig=0; bad=0; ans=0
run() {  # shape how sdir idir target l0 l1
  taskset -c 0-11 timeout 120 ./vrs_t_shut "$@" $SRC > /dev/null 2>&1
}
for n in $(seq 1 100); do
  D=$W/r$n; S=$D/sessions; I=$D/idx
  mkdir -p $S/2026/01/01 $I
  for f in $(cat $W/base_list.txt); do b=$(basename $f); ln $f $S/2026/01/01/$b 2>/dev/null || cp $f $S/2026/01/01/$b; done
  T=$S/2027/01/01/rollout-2027-01-01T00-00-00-01f0c000-0000-7000-8000-000000000$(printf '%03d' $n).jsonl
  T2=$S/2027/01/02/rollout-2027-01-02T00-00-00-01f0c001-0000-7000-8000-000000000$(printf '%03d' $n).jsonl
  T3=$S/2027/01/03/rollout-2027-01-03T00-00-00-01f0c002-0000-7000-8000-000000000$(printf '%03d' $n).jsonl
  if [ $((n % 2)) -eq 0 ]; then HOW=exit; else HOW=close; fi
  for step in S1 S2 S3 S4 S5 S5x; do
    case $step in
      S1) taskset -c 0-11 timeout 120 ./vrs_t_shut S1 exit $S $I $SRC $T 0 23 >/dev/null 2>&1; rc=$? ;;
      S2) taskset -c 0-11 timeout 120 ./vrs_t_shut S2 exit $S $I $SRC $T 23 60 >/dev/null 2>&1; rc=$? ;;
      S3) taskset -c 0-11 timeout 120 ./vrs_t_shut S3 $HOW $S $I $SRC $T2 0 210 >/dev/null 2>&1; rc=$? ;;
      S4) # two processes at once, each its own session file, same index dir (the app: two codex processes)
          taskset -c 0-11 timeout 120 ./vrs_t_shut S3 exit $S $I $SRC $T3 0 210 >/dev/null 2>&1 &
          p1=$!
          taskset -c 0-11 timeout 120 ./vrs_t_shut S3 exit $S $I $SRC $T 60 270 >/dev/null 2>&1; rc=$?
          wait $p1; rc1=$?
          [ $rc1 -gt $rc ] && rc=$rc1 ;;
      S5) taskset -c 0-11 timeout 120 ./vrs_t_shut S5 exit $S $I $SRC $T 0 0 >/dev/null 2>&1; rc=$? ;;
      S5x) taskset -c 0-11 timeout 120 ./vrs_t_shut S5x exit $S $I $SRC $T 0 0 >/dev/null 2>&1; rc=$? ;;
    esac
    tot=$((tot+1))
    if [ $rc -ge 128 ]; then sig=$((sig+1)); echo "SIGNAL round $n step $step how $HOW rc $rc" >> test5/t57_result.txt;
    elif [ $rc -eq 3 ]; then ans=$((ans+1)); echo "NOANSWER round $n step $step rc $rc" >> test5/t57_result.txt;
    elif [ $rc -ne 0 ]; then bad=$((bad+1)); echo "OTHER round $n step $step rc $rc" >> test5/t57_result.txt; fi
  done
  rm -rf $D
  if [ $((n % 10)) -eq 0 ]; then echo "round $n done: processes $tot signals $sig noanswer $ans other $bad" >> test5/t57_result.txt; fi
done
echo "T5-7 total processes $tot, ended by a signal $sig, no answer $ans, other failures $bad" >> test5/t57_result.txt
echo done > test5/t57_done.txt
