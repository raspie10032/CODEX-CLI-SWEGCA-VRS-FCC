#!/usr/bin/env python3
"""Test (h) (round 4): several threads hand the lines of ONE file to vrs_insert at the same time, with several files at once; late turns (original 2026 timestamps) in between.

usage: live_cmp7.py <snap dir> <work dir> <orig binary dir> <index dir copy source>        env H_THREADS = threads per file (default 6)   H_SEED = shuffle seed (default 4242)
 files (copies of real rollouts, new ids): A with timestamps moved to 2027 (its turns come in above everything), B and C with their original 2026 timestamps (their turns come
 in below turns that are in: late turns, P-8).
 1. the files are created empty; the lines of A, B and C are handed to vrs_insert by T threads each (18 threads on the 12 CPUs), every line in a shuffled order, each thread:
    vrs_insert at the reserved offset, pwrite of the bytes, vrs_written. Nobody waits for anybody: the counter insert_waits (turns of every yield loop in the library) must stay 0.
 2. the library is quiet (every closed turn counted, no sweep in flight, every line in); vrs_assemble answers for every file of the tree are equal (items and tokens, byte for byte)
    to those of a fresh original 42f over the same files; the same after a restart on the shards and after a build from scratch; observers and cells of the three builds equal.
"""
import json, os, re, shutil, socket, subprocess, sys, time

SNAP, WORK, ORIGDIR, IDXSRC = sys.argv[1:5]
NT = int(os.environ.get("H_THREADS", "6"))
SEED = int(os.environ.get("H_SEED", "4242"))
BUDGET = 258400
SOCK = os.path.join(ORIGDIR, "orig7.sock")
UU = re.compile(r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\.jsonl$")
fidre = re.compile(r'"forked_from_id":"([^"]+)"')
XID = "01a04b03-b1c2-7ec0-b228-299e1d3aa709"
FILES = {}
for root, _, fs in os.walk(SNAP):
    for f in fs:
        m = UU.search(f)
        if m: FILES[m.group(1)] = os.path.join(root, f)
ycand = []
for cid, cp in FILES.items():
    if cid == XID or not (20_000 <= os.path.getsize(cp) <= 400_000): continue
    with open(cp, "rb") as fh: l0 = fh.readline().decode("utf-8", "replace")
    if fidre.search(l0) and fidre.search(l0).group(1): continue
    ycand.append((os.path.getsize(cp), cid))
ycand.sort()
OLD = {"A": XID, "B": ycand[len(ycand) // 2][1], "C": ycand[len(ycand) // 3][1]}
NEW = {k: "01f1" + v[4:] for k, v in OLD.items()}
OLDFILE = {k: FILES[v] for k, v in OLD.items()}
NEWDIR = os.path.join(SNAP, "2027", "02", "02")
print("threads per file", NT, "files", OLD)


def span(raw):
    a = raw.find(b'"items":[')
    if a < 0: return None
    a += len(b'"items":[')
    b = raw.rfind(b'],"tokens":')
    return raw[a:b], raw[b + len(b'],"tokens":'):].split(b",")[0]


def ask(rollout):
    s = socket.socket(socket.AF_UNIX); s.connect(SOCK)
    s.sendall((json.dumps({"rollout": rollout, "budget": BUDGET}) + "\n").encode())
    b = b""
    while not b.endswith(b"\n"):
        c = s.recv(1 << 22)
        if not c: break
        b += c
    s.close()
    return b.rstrip(b"\n")


shutil.rmtree(WORK, ignore_errors=True); os.makedirs(WORK + "/src"); os.makedirs(WORK + "/out")
subs = [(OLD[k], NEW[k]) for k in OLD]
srcs, lines, dst = {}, {}, {}
for k in OLD:
    txt = open(OLDFILE[k], "rb").read().decode("utf-8")
    for a, b in subs: txt = txt.replace(a, b)
    if k == "A": txt = txt.replace('"timestamp":"2026-', '"timestamp":"2027-')
    srcs[k] = os.path.join(WORK, "src", k + ".jsonl")
    open(srcs[k], "wb").write(txt.encode("utf-8"))
    lines[k] = txt.split("\n")
    if lines[k] and lines[k][-1] == "": lines[k].pop()
    dst[k] = os.path.join(NEWDIR, os.path.basename(OLDFILE[k]).replace(OLD[k], NEW[k]))

lib = subprocess.Popen(["taskset", "-c", "0-11", os.path.expanduser(os.environ.get("LIVE_BIN", "$WORK/vrsint5/vrs_t_live"))], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
log = []


def cmd(c):
    lib.stdin.write(c + "\n"); lib.stdin.flush()
    return lib.stdout.readline().strip()


def say(m):
    print(m); log.append(m)


fails = 0
orig = None


def need(cond, what):
    global fails
    say(("PASS " if cond else "FAIL ") + what)
    if not cond: fails += 1


def kv(r, key):
    m = re.search(r"\b%s=(-?[0-9.]+)" % key, r)
    return float(m.group(1)) if m else None


def settle(what, want_lines=None, tmo=600):
    ok = 0
    for _ in range(tmo * 20):
        st, st2 = cmd("STATS"), cmd("STATS2")
        if kv(st, "pend") == 0 and kv(st2, "sweep_left") == 0 and (want_lines is None or kv(st, "lines_applied") >= want_lines):
            ok += 1
            if ok >= 3: return st, st2
        else: ok = 0
        time.sleep(0.05)
    say("TIMEOUT waiting for quiet: " + what + " | " + cmd("STATS") + " | " + cmd("STATS2"))
    return cmd("STATS"), cmd("STATS2")


def asm(path, tag):
    out = os.path.join(WORK, "out", tag + ".json")
    if os.path.exists(out): os.remove(out)
    r = cmd("ASM %s %s" % (path, out))
    rc = kv(r, "rc")
    return int(rc) if rc is not None else None, (open(out, "rb").read() if os.path.exists(out) else b"")


try:
    idx = os.path.join(WORK, "idx")
    shutil.rmtree(idx, ignore_errors=True)
    subprocess.check_call(["cp", "-r", "--reflink=auto", IDXSRC, idx])
    say(cmd("OPEN %s %s" % (SNAP, idx)))
    st0 = cmd("STATS"); st20 = cmd("STATS2")
    L0 = kv(st0, "lines_applied"); W0 = kv(st20, "insert_waits")
    say("before: " + st0 + " | " + st20)
    total = sum(len(v) for v in lines.values())
    args = " ".join("%s %s" % (srcs[k], dst[k]) for k in ("A", "B", "C"))
    r = cmd("CONC %d %d %s" % (NT, SEED, args))
    say("CONC: " + r)
    need(kv(r, "bad") == 0 and kv(r, "calls") == total, "every vrs_insert / vrs_written returned 0 (%s calls, %d lines)" % (kv(r, "calls"), total))
    need(kv(r, "threads") == 3 * NT, "%d threads inserted at once (%s)" % (3 * NT, kv(r, "threads")))
    need(kv(r, "insert_waits") == 0, "nobody waited during the inserts: insert_waits delta %s" % kv(r, "insert_waits"))
    say("insert calls that left their line to the thread that held the file: %s of %d" % (kv(r, "insert_left"), total))
    st, st2 = settle("all lines in", L0 + total)
    say("quiet: " + st + " | " + st2)
    need(kv(st, "lines_applied") >= L0 + total, "every line is in (lines_applied %s, wanted %s)" % (kv(st, "lines_applied"), L0 + total))
    need(kv(st, "uw_lines") == 0 and kv(st, "uw_added") == kv(st, "uw_released"), "every copy was released (uw_lines %s, added %s released %s)" % (kv(st, "uw_lines"), kv(st, "uw_added"), kv(st, "uw_released")))
    need(kv(st2, "insert_waits") == W0, "no yield loop was taken anywhere in the library in the whole test (insert_waits %s -> %s)" % (W0, kv(st2, "insert_waits")))
    need(kv(st2, "late_events") >= 1, "late turns came in (late_events %s)" % kv(st2, "late_events"))
    for k in ("A", "B", "C"):
        need(open(dst[k], "rb").read() == open(srcs[k], "rb").read(), "%s: the file equals its source" % k)
    cmd("CELLS " + os.path.join(WORK, "cells_live.txt"))
    paths = []
    for r_, _, fs in os.walk(SNAP):
        for f in fs:
            if f.endswith(".jsonl"): paths.append(os.path.join(r_, f))
    paths.sort()
    env = dict(os.environ, VRS9SYN_SERVE="1", VRS9_SEGWIN="1", CODEX_VRS_SOCK=SOCK)
    if os.path.exists(SOCK): os.remove(SOCK)
    orig = subprocess.Popen(["taskset", "-c", "0-11", os.path.join(ORIGDIR, "vrs9syn42f"), "serve", SNAP, str(BUDGET)], env=env,
                            stdout=open(os.path.join(WORK, "orig7.log"), "w"), stderr=open(os.path.join(WORK, "orig7.err"), "w"))
    say("fresh orig pid %d, files in the tree: %d" % (orig.pid, len(paths)))
    for _ in range(400):
        if os.path.exists(SOCK): break
        time.sleep(3)
    assert os.path.exists(SOCK), "orig did not start"
    time.sleep(1)
    ref = {p: ask(p) for p in paths}

    def compare(tag):
        global fails
        same = diff = 0
        out = os.path.join(WORK, "out", "x.json")
        for p in paths:
            r = cmd("ASM %s %s" % (p, out))
            m = open(out, "rb").read() if os.path.exists(out) else b""
            if os.path.exists(out): os.remove(out)
            so, sm = span(ref[p]), span(m)
            if so is None and sm is None: ok = json.loads(ref[p]).get("error") == (json.loads(m).get("error") if m else r)
            elif so is None or sm is None: ok = False
            else: ok = so == sm
            if ok: same += 1
            else:
                diff += 1
                say("%s DIFF %s orig=%s lib=%s" % (tag, os.path.basename(p), (len(so[0]), so[1]) if so else ref[p][:80], (len(sm[0]), sm[1]) if sm else (r, m[:80])))
        say("%s compared %d same %d diff %d" % (tag, same + diff, same, diff))
        if diff: fails += 1
    compare("live")
    obs_live = {p: cmd("OHASH " + p) for p in paths}
    EXTRA = [p for p in paths if "01a0ffa7-8536" in p]
    for nm, pth in (("A", dst["A"]), ("B", dst["B"]), ("C", dst["C"])) + tuple(("x%d" % i, p) for i, p in enumerate(EXTRA)): cmd("OBSDUMP %s %s" % (pth, os.path.join(WORK, "obs_live_%s.txt" % nm)))
    say(cmd("CLOSE"))
    say(cmd("OPEN %s %s" % (SNAP, idx)))
    say(cmd("STATS") + " | " + cmd("STATS2"))
    cmd("CELLS " + os.path.join(WORK, "cells_restart.txt"))
    compare("restart")
    obs_rest = {p: cmd("OHASH " + p) for p in paths}
    bad = [p for p in paths if obs_live[p] != obs_rest[p]]
    say("observer hash, live-built vs restored from its shards: %d sessions, %d different" % (len(paths), len(bad)))
    for p in bad[:10]: say("  differs: " + p)
    if bad: fails += 1
    say(cmd("CLOSE"))
    cold = os.path.join(WORK, "idx_cold")
    shutil.rmtree(cold, ignore_errors=True)
    say(cmd("OPEN %s %s" % (SNAP, cold)))
    cmd("CELLS " + os.path.join(WORK, "cells_cold.txt"))
    obs_cold = {p: cmd("OHASH " + p) for p in paths}
    for nm, pth in (("A", dst["A"]), ("B", dst["B"]), ("C", dst["C"])) + tuple(("x%d" % i, p) for i, p in enumerate(EXTRA)): cmd("OBSDUMP %s %s" % (pth, os.path.join(WORK, "obs_cold_%s.txt" % nm)))
    for p in [p for p in paths if obs_live[p] != obs_cold[p]][:10]:
        say("  cold differs: " + p); cmd("OBSDUMP %s %s" % (p, os.path.join(WORK, "obs_cold_diff_%s.txt" % os.path.basename(p))))
    bad = [p for p in paths if obs_live[p] != obs_cold[p]]
    say("observer hash, live-built vs built from scratch: %d sessions, %d different" % (len(paths), len(bad)))
    if bad: fails += 1

    def cells(n): return {l.split()[0]: l.strip() for l in open(os.path.join(WORK, "cells_%s.txt" % n))}
    cl, cr, cc = cells("live"), cells("restart"), cells("cold")
    for a_, b_, nm in ((cl, cr, "live vs restart"), (cl, cc, "live vs cold")):
        dif = [k for k in set(a_) | set(b_) if a_.get(k) != b_.get(k)]
        say("cells %s: %d cells in use, %d different" % (nm, len(set(a_) | set(b_)), len(dif)))
        if dif: fails += 1
    compare("cold")
finally:
    try: say(cmd("QUIT"))
    except Exception: pass
    try: lib.wait(timeout=60)
    except Exception: lib.kill()
    if orig is not None:
        orig.terminate()
        try: orig.wait(timeout=60)
        except Exception: orig.kill()
    for k in dst:
        try: os.remove(dst[k])
        except OSError: pass
    for d in (NEWDIR, os.path.join(SNAP, "2027", "02"), os.path.join(SNAP, "2027")):
        try: os.rmdir(d)
        except OSError: pass
    open(os.path.join(WORK, "live_cmp7_result.txt"), "w", encoding="utf-8").write("\n".join(log) + "\nfails %d\n" % fails)
print("fails", fails)
sys.exit(1 if fails else 0)
