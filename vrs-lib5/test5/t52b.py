#!/usr/bin/env python3
"""T5-2b (single late turn, counters only): one real rollout with exactly one task_started turn, new id, ORIGINAL (2026-06) timestamps, is put into the calm base
(462 files) from 0 bytes - once by the watcher (one write), once by vrs_insert line by line.  The counters of the library tell what one late turn cost:
 obs_rebuilt delta (observers replaced), y_max (observers whose window the turn is in), x_max (x seen again), time to calm.
pass (fixed before the run, same bounds as T5-2): y_max <= W-1+T, obs_rebuilt delta <= W-1+T, x_max <= (W-1+T)*9*4095, with T = theta_maxgroup measured.
usage: t52b.py <snap> <work> <index source>"""
import os, re, shutil, subprocess, sys, time
SNAP, WORK, IDXSRC = sys.argv[1:4]
SRC = os.path.join(SNAP, "2026/06/01/rollout-2026-06-01T22-10-06-019e834e-3470-7cb1-aec8-1536f043b153.jsonl")
OLDID = "019e834e-3470-7cb1-aec8-1536f043b153"
fails = 0
def kv(r, key):
    m = re.search(r"\b%s=(-?[0-9.]+)" % key, r)
    return float(m.group(1)) if m else None
def run(mode, tag):
    global fails
    shutil.rmtree(WORK + "/" + tag, ignore_errors=True); os.makedirs(WORK + "/" + tag + "/src")
    newid = "01f2" + OLDID[4:]
    txt = open(SRC, "rb").read().decode("utf-8").replace(OLDID, newid)  # original timestamps kept
    s = WORK + "/" + tag + "/src/one.jsonl"; open(s, "wb").write(txt.encode("utf-8"))
    n = len(txt.split("\n")) - 1
    dst = os.path.join(SNAP, "2027", "03", "03", "rollout-2026-06-01T22-10-06-%s.jsonl" % newid)
    idx = WORK + "/" + tag + "/idx"; subprocess.check_call(["cp", "-r", "--reflink=auto", IDXSRC, idx])
    lib = subprocess.Popen(["taskset", "-c", "0-11", os.path.expanduser("$WORK/vrsint5/vrs_t_live5")], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
    def cmd(c):
        lib.stdin.write(c + "\n"); lib.stdin.flush(); return lib.stdout.readline().strip()
    try:
        print(tag, cmd("OPEN %s %s" % (SNAP, idx)))
        b = cmd("STATS3"); print(tag, "before", b)
        t0 = time.time()
        r = cmd("APPEND %s %s %s 0 %d" % (mode, s, dst, n)); print(tag, r)
        ok = 0
        for _ in range(600):
            st = cmd("STATS3")
            if kv(st, "pend") == 0 and kv(cmd("STATS"), "lines_applied") >= 12313 + n: ok += 1
            else: ok = 0
            if ok >= 3: break
            time.sleep(0.05)
        a = cmd("STATS3"); print(tag, "after ", a, "calm after %.2f s" % (time.time() - t0))
        T = kv(a, "theta_maxgroup"); W = 1024
        ym, xm = kv(a, "y_max"), kv(a, "x_max")
        od = kv(a, "obs_rebuilt") - kv(b, "obs_rebuilt")
        res = [(kv(a, "late_events") - kv(b, "late_events") >= 1, "a late turn came in (late_events delta %s)" % (kv(a, "late_events") - kv(b, "late_events"))),
               (ym <= W - 1 + T, "y_max %s <= W-1+T = %s" % (ym, W - 1 + T)),
               (od <= W - 1 + T, "obs_rebuilt delta %s <= W-1+T = %s" % (od, W - 1 + T)),
               (xm <= (W - 1 + T) * 9 * 4095, "x_max %s <= %s" % (xm, (W - 1 + T) * 9 * 4095))]
        for ok_, what in res:
            print(tag, "PASS" if ok_ else "FAIL", what)
            if not ok_: fails += 1
        print(tag, "late_events delta %s, y_total delta %s, x_total delta %s, revisit_tasks delta %s, pass_retries delta %s" % (kv(a, "late_events") - kv(b, "late_events"), kv(a, "y_total") - kv(b, "y_total"), kv(a, "x_total") - kv(b, "x_total"), kv(a, "revisit_tasks") - kv(b, "revisit_tasks"), kv(a, "pass_retries") - kv(b, "pass_retries")))
    finally:
        try: cmd("QUIT")
        except Exception: pass
        try: lib.wait(timeout=60)
        except Exception: lib.kill()
        try: os.remove(dst)
        except OSError: pass
        for d in (os.path.dirname(dst), os.path.join(SNAP, "2027", "03"), os.path.join(SNAP, "2027")):
            try: os.rmdir(d)
            except OSError: pass
run("watch", "w"); run("insert", "i")
print("fails", fails); sys.exit(1 if fails else 0)
