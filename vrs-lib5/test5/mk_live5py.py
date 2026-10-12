#!/usr/bin/env python3
# makes test5/live5.py from libsrc/live_cmp5.py (stage 4 test (f)): reference = 42w (ORIGDIR=ref42w); stage-5 adaptations, each listed in REPORT5 (VI-36):
#  - the calm point replaces "synchronous counting": settle() before the first assemble / pend check (counting is done by tasks now)
#  - step 0 (T5-2 / T5-5): ASMLOOP on another file every 1 ms while Y is worked in; counters y_max / x_max / late_events read after
import sys
s = open('$WORK/vrsint5/libsrc/live_cmp5.py', encoding='utf-8').read()

def rep(a, b, cnt=1):
    global s
    assert s.count(a) >= 1, a[:60]
    s = s.replace(a, b, cnt)

rep('SOCK = os.path.join(ORIGDIR, "orig5.sock")', 'SOCK = os.path.join(ORIGDIR, "w5.sock")')
rep('"$WORK/vrsint5/vrs_t_live"', '"$WORK/vrsint5/vrs_t_live5"')
# step 0: start the 1 ms assemble loop on a base file that is not Y, before Y's bytes are written
rep('''    t_y = time.time()
    r = cmd("FLUSHW %s 778 100000000 nowritten" % dst["Y"])''', '''    t_y = time.time()
    loop_file = OLDFILE["P1"]
    say("T5-5 loop file: " + loop_file + " " + cmd("ASMLOOP %s 1" % loop_file))
    st3_before = cmd("STATS3"); say("STATS3 before the rest of Y: " + st3_before)
    r = cmd("FLUSHW %s 778 100000000 nowritten" % dst["Y"])''')
rep('''    say("after Y: %s | %s | quiet %.1f s after the last byte of Y was written" % (st, st2, time.time() - t_y))''', '''    say("after Y: %s | %s | quiet %.1f s after the last byte of Y was written" % (st, st2, time.time() - t_y))
    rl = cmd("ASMSTOP"); say("T5-5 loop: " + rl)
    need(kv(rl, "rc1") == 0 and kv(rl, "calls") is not None and kv(rl, "calls") >= 50, "T5-5: assemble on another file every 1 ms while Y was worked in: rc 1 count %s of %s calls (rc0 %s, other %s, max %s us)" % (kv(rl, "rc1"), kv(rl, "calls"), kv(rl, "rc0"), kv(rl, "rcother"), kv(rl, "maxus")))
    st3 = cmd("STATS3"); say("STATS3 after Y: " + st3)
    T = kv(st3, "theta_maxgroup"); Wm = 1024
    ym, xm = kv(st3, "y_max"), kv(st3, "x_max")
    need(ym <= Wm - 1 + T, "T5-2: observers rebuilt for one late turn at most W-1+T = %d (y_max %s, T %s)" % (Wm - 1 + T, ym, T))
    need(xm <= (Wm - 1 + T) * 9 * 4095, "T5-2: x seen again for one late turn at most (W-1+T)*9*4095 = %d (x_max %s)" % ((Wm - 1 + T) * 9 * 4095, xm))
    say("T5-2 totals: late_events %s, y_total %s, x_total %s, revisit_tasks %s, obs_rebuilt %s, quiet %.1f s after the last byte" % (kv(st3, "late_events"), kv(st3, "y_total"), kv(st3, "x_total"), kv(st3, "revisit_tasks"), kv(st3, "obs_rebuilt"), time.time() - t_y))''')
# step 1: counting is by tasks; wait for the calm point instead of "pend == 0 inside the call"
rep('''    need(kv(r, "pend") == 0, "X: pend == 0 when the last vrs_insert returned (the closed turns were counted inside the calls), got %s" % kv(r, "pend"))''', '''    stq, _ = settle("X reserve")
    need(kv(stq, "pend") == 0, "X: calm point reached (pend 0) after the inserts, got %s" % kv(stq, "pend"))''')
rep('''        r = reserve(P, iA, len(PL)); say("P reserve (rest): " + r)
        lat.append(kv(r, "us_per_insert"))''', '''        r = reserve(P, iA, len(PL)); say("P reserve (rest): " + r)
        lat.append(kv(r, "us_per_insert"))
        settle("pair %d" % i)''')
open('$WORK/vrsint5/test5/live5.py', 'w', encoding='utf-8').write(s)

# observer dumps of Y's original and Y's copy (live, restart, cold) for a diagnosis when the observer hashes differ
s = open('$WORK/vrsint5/test5/live5.py', encoding='utf-8').read()
s = s.replace('''    obs_live = {p: cmd("OHASH " + p) for p in paths}''', '''    obs_live = {p: cmd("OHASH " + p) for p in paths}
    for nm, pth in (("yorig", OLDFILE["Y"]), ("ycopy", dst["Y"])): cmd("OBSDUMP %s %s" % (pth, os.path.join(WORK, "obs_live_%s.txt" % nm)))''', 1)
s = s.replace('''    obs_cold = {p: cmd("OHASH " + p) for p in paths}''', '''    obs_cold = {p: cmd("OHASH " + p) for p in paths}
    for nm, pth in (("yorig", OLDFILE["Y"]), ("ycopy", dst["Y"])): cmd("OBSDUMP %s %s" % (pth, os.path.join(WORK, "obs_cold_%s.txt" % nm)))''', 1)
open('$WORK/vrsint5/test5/live5.py', 'w', encoding='utf-8').write(s)
