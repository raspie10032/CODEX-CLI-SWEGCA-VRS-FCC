#!/usr/bin/env python3
"""P-3' test (f): vrs_insert at RECORD time, before the line is on disk, with reserved offsets; the bytes are written later (pwrite, shuffled), then vrs_written.

usage: live_cmp5.py <snap dir> <work dir> <orig binary dir> <index dir copy source>     env F_MODE = ordered | shuffled   (order of the vrs_insert calls)
 sessions (copies of real rollouts, new ids, timestamps moved to 2027): X plain, up to three fork pairs (parent P, child C), Y plain and written by "another process"
 (pwrite only, no vrs_insert: the watcher meets NUL holes).
 1. every file is created EMPTY; all lines of X are handed to vrs_insert (pend must be 0 when the call returns: synchronous counting); C's lines before P's (rc 1 while
    the lineage is pending), then P's; the library answers (vrs_assemble) with NOTHING on disk. Y: file empty, nothing handed over.
 2. half of the lines of every file is pwritten in shuffled order (holes of NUL), vrs_written after each; the answers must not change (byte for byte).
 3. the rest is written; vrs_written; all copies released (uw_lines 0, uw_added == uw_released); an unknown key gives an error code.
 4. the reference is a fresh original 42f over the final files: the answers of step 1, 2 and 3 equal it; observer hash and cells of the live build equal a restart on
    its shards and a build from scratch.
"""
import json, os, re, shutil, socket, subprocess, sys, time

SNAP, WORK, ORIGDIR, IDXSRC = sys.argv[1:5]
MODE = os.environ.get("F_MODE", "ordered")
INSEED = 0 if MODE == "ordered" else 4242
BUDGET = 258400
SOCK = os.path.join(ORIGDIR, "w5.sock")
XID = "01a04b03-b1c2-7ec0-b228-299e1d3aa709"
UU = re.compile(r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\.jsonl$")
tsre = re.compile(r'"timestamp":"([^"]+)"')
ordre = re.compile(r'"ordinal":(\d+)')
fkre = re.compile(r'"forked_from_ordinal_exclusive":(\d+)')
fidre = re.compile(r'"forked_from_id":"([^"]+)"')
FILES = {}
for root, _, fs in os.walk(SNAP):
    for f in fs:
        m = UU.search(f)
        if m: FILES[m.group(1)] = os.path.join(root, f)


def first_last_ts(p):
    with open(p, "rb") as fh:
        first = fh.readline().decode("utf-8", "replace")
        last = first
        for ln in fh: last = ln.decode("utf-8", "replace")
    return tsre.search(first).group(1), tsre.search(last).group(1)


cand = []
for cid, cp in FILES.items():
    if os.path.getsize(cp) > 400_000: continue
    with open(cp, "rb") as fh: l0 = fh.readline().decode("utf-8", "replace")
    m, pid = fkre.search(l0), fidre.search(l0)
    if not (m and pid and pid.group(1) in FILES): continue
    pp = FILES[pid.group(1)]
    if os.path.getsize(pp) > 4_000_000: continue
    n = sum(1 for _ in open(pp, "rb"))
    if int(m.group(1)) >= n: continue
    ps, pe = first_last_ts(pp); cs, ce = first_last_ts(cp)
    cand.append((ps, max(pe, ce), pid.group(1), cid))
cand.sort()
pairs, t_end, used = [], "", set()
for ps, pe, pid, cid in cand:
    if ps > t_end and pid not in used:
        pairs.append((pid, cid)); used.add(pid); t_end = pe
    if len(pairs) == 3: break
assert pairs, "no fork pair found"
OLD = {"X": XID}
for i, (pid, cid) in enumerate(pairs):
    OLD["P%d" % (i + 1)] = pid; OLD["C%d" % (i + 1)] = cid
taken = set(OLD.values())
ycand = []
for cid, cp in FILES.items():
    if cid in taken or not (20_000 <= os.path.getsize(cp) <= 400_000): continue
    with open(cp, "rb") as fh: l0 = fh.readline().decode("utf-8", "replace")
    if fidre.search(l0) and fidre.search(l0).group(1): continue
    ycand.append((os.path.getsize(cp), cid))
ycand.sort()
OLD["Y"] = ycand[len(ycand) // 2][1]
NEW = {k: "01f0" + v[4:] for k, v in OLD.items()}
OLDFILE = {k: FILES[v] for k, v in OLD.items()}
NEWDIR = os.path.join(SNAP, "2027", "01", "01")
print("mode", MODE, "pairs (parent, child):", pairs, "Y", OLD["Y"])


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
    if k != "Y": txt = txt.replace('"timestamp":"2026-', '"timestamp":"2027-')  # Y keeps its original timestamps (2026): its turns come in below turns that are in already (P-8)
    srcs[k] = os.path.join(WORK, "src", k + ".jsonl")
    open(srcs[k], "wb").write(txt.encode("utf-8"))
    lines[k] = txt.split("\n")
    if lines[k] and lines[k][-1] == "": lines[k].pop()
    dst[k] = os.path.join(NEWDIR, os.path.basename(OLDFILE[k]).replace(OLD[k], NEW[k]))

lib = subprocess.Popen(["taskset", "-c", "0-11", os.path.expanduser(os.environ.get("LIVE_BIN", "$WORK/vrsint5/vrs_t_live5"))], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
log = []


def cmd(c):
    lib.stdin.write(c + "\n"); lib.stdin.flush()
    return lib.stdout.readline().strip()


def say(m):
    print(m); log.append(m)


fails = 0
created = []
orig = None


def need(cond, what):
    global fails
    say(("PASS " if cond else "FAIL ") + what)
    if not cond: fails += 1


def kv(r, key):
    m = re.search(r"\b%s=(-?[0-9.]+)" % key, r)
    return float(m.group(1)) if m else None


def asm(path, tag):
    out = os.path.join(WORK, "out", tag + ".json")
    if os.path.exists(out): os.remove(out)
    r = cmd("ASM %s %s" % (path, out))
    rc = kv(r, "rc")
    return int(rc) if rc is not None else None, (open(out, "rb").read() if os.path.exists(out) else b"")


def reserve(k, a, b, noinsert=False):
    r = cmd("RESERVE %s %s %d %d %d %s" % (srcs[k], dst[k], a, b, 0 if noinsert else INSEED, "noinsert" if noinsert else ""))
    if dst[k] not in created: created.append(dst[k])
    return r


def zeros(p):
    d = open(p, "rb").read()
    return len(d), d.count(b"\0")


def settle(what, want_lines=None, tmo=400):
    """quiet = every closed turn counted (pend 0), no sweep task in flight (sweep_left 0), all lines in; seen three times in a row"""
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


try:
    idx = os.path.join(WORK, "idx")
    shutil.rmtree(idx, ignore_errors=True)
    subprocess.check_call(["cp", "-r", "--reflink=auto", IDXSRC, idx])
    say(cmd("OPEN %s %s" % (SNAP, idx)))
    L0 = kv(cmd("STATS"), "lines_applied")
    before = {}
    lat = []
    # ---- step 0 (P-8): Y keeps its original 2026 timestamps; another process writes it (pwrite, shuffled, with NUL holes), nobody hands it to vrs_insert. Its turns close below
    # turns that are counted already (the 462 files, 2026 timestamps, and X / P / C below, 2027 timestamps are above it): the library works them in. It is quiet before step 1,
    # so that steps 1-3 (the claims of P-3') run over a fixed set of the other files.
    reserve("Y", 0, len(lines["Y"]), noinsert=True)
    for _ in range(100):
        if cmd("HASH " + dst["Y"]).startswith("OK rc=0"): break
        time.sleep(0.05)
    need(cmd("HASH " + dst["Y"]).startswith("OK rc=0"), "Y: the watcher knows the (empty) file")
    base_lines = kv(cmd("STATS"), "lines_applied")
    nul0 = kv(cmd("STATS"), "nul_stops")
    r = cmd("FLUSHW %s 777 %d nowritten" % (dst["Y"], len(lines["Y"]) // 2))
    sz, nz = zeros(dst["Y"]); say("step 0 Y half: %s | file %d bytes, %d NUL" % (r, sz, nz))
    time.sleep(0.5)
    st, st2 = settle("Y half")
    say("after Y half: " + st + " | " + st2)
    need(nz > 0, "step 0: Y holds NUL holes (%d)" % nz)
    need(kv(st, "nul_stops") >= nul0 + 1, "step 0: the watcher stopped at a NUL (nul_stops %s -> %s)" % (nul0, kv(st, "nul_stops")))
    t_y = time.time()
    loop_file = OLDFILE["P1"]
    say("T5-5 loop file: " + loop_file + " " + cmd("ASMLOOP %s 1" % loop_file))
    st3_before = cmd("STATS3"); say("STATS3 before the rest of Y: " + st3_before)
    r = cmd("FLUSHW %s 778 100000000 nowritten" % dst["Y"])
    sz, nz = zeros(dst["Y"]); say("step 0 Y rest: %s | file %d bytes (source %d), %d NUL" % (r, sz, os.path.getsize(srcs["Y"]), nz))
    need(sz == os.path.getsize(srcs["Y"]) and nz == 0 and open(dst["Y"], "rb").read() == open(srcs["Y"], "rb").read(), "step 0: Y file is complete and equal to its source")
    st, st2 = settle("Y all", base_lines + len(lines["Y"]))
    say("after Y: %s | %s | quiet %.1f s after the last byte of Y was written" % (st, st2, time.time() - t_y))
    rl = cmd("ASMSTOP"); say("T5-5 loop: " + rl)
    need(kv(rl, "rc1") == 0 and kv(rl, "calls") is not None and kv(rl, "calls") >= 50, "T5-5: assemble on another file every 1 ms while Y was worked in: rc 1 count %s of %s calls (rc0 %s, other %s, max %s us)" % (kv(rl, "rc1"), kv(rl, "calls"), kv(rl, "rc0"), kv(rl, "rcother"), kv(rl, "maxus")))
    st3 = cmd("STATS3"); say("STATS3 after Y: " + st3)
    T = kv(st3, "theta_maxgroup"); Wm = 1024
    ym, xm = kv(st3, "y_max"), kv(st3, "x_max")
    need(ym <= Wm - 1 + T, "T5-2: observers rebuilt for one late turn at most W-1+T = %d (y_max %s, T %s)" % (Wm - 1 + T, ym, T))
    need(xm <= (Wm - 1 + T) * 9 * 4095, "T5-2: x seen again for one late turn at most (W-1+T)*9*4095 = %d (x_max %s)" % ((Wm - 1 + T) * 9 * 4095, xm))
    say("T5-2 totals: late_events %s, y_total %s, x_total %s, revisit_tasks %s, obs_rebuilt %s, quiet %.1f s after the last byte" % (kv(st3, "late_events"), kv(st3, "y_total"), kv(st3, "x_total"), kv(st3, "revisit_tasks"), kv(st3, "obs_rebuilt"), time.time() - t_y))
    need(kv(st, "lines_applied") >= base_lines + len(lines["Y"]), "step 0: every line of Y is in (lines_applied %s, wanted %s)" % (kv(st, "lines_applied"), base_lines + len(lines["Y"])))
    need(kv(st2, "late_events") is not None and kv(st2, "late_events") >= 1, "step 0: Y's turns came in below turns that are in (late_events %s)" % kv(st2, "late_events"))
    need(kv(st2, "sweep_left") == 0 and kv(st, "pend") == 0, "step 0: quiet (sweep_left %s, pend %s)" % (kv(st2, "sweep_left"), kv(st, "pend")))
    nul_after_y = kv(st, "nul_stops")
    # ---- step 1: record time
    r = reserve("X", 0, len(lines["X"]))
    say("X reserve: " + r)
    lat.append(kv(r, "us_per_insert"))
    need(kv(r, "bad") == 0, "X: every vrs_insert returned 0")
    stq, _ = settle("X reserve")
    need(kv(stq, "pend") == 0, "X: calm point reached (pend 0) after the inserts, got %s" % kv(stq, "pend"))
    need(kv(r, "uw_lines") == len(lines["X"]), "X: %d lines held in memory, got %s" % (len(lines["X"]), kv(r, "uw_lines")))
    need(os.path.getsize(dst["X"]) == 0, "X: the file is still empty")
    rc, b = asm(dst["X"], "X0"); before["X"] = (rc, b)
    need(rc == 0 and len(b) > 0, "X: assemble with nothing on disk answers rc 0 with items, got rc %s, %d bytes" % (rc, len(b)))
    cmd("STATS"); say(cmd("STATS"))
    for i in range(1, len(pairs) + 1):
        P, C = "P%d" % i, "C%d" % i
        PL = lines[P]
        fk = int(fkre.search(lines[C][0]).group(1))
        pord = [int(ordre.search(l).group(1)) if ordre.search(l) else j for j, l in enumerate(PL)]
        iA = next(j for j, o in enumerate(pord) if o >= fk - 1)
        say("pair %d: fork ordinal %d, parent %d lines (fork reached by line index %d), child %d lines" % (i, fk, len(PL), iA, len(lines[C])))
        say(cmd("TOUCH " + dst[P])); created.append(dst[P])                           # the parent's file exists but holds no line
        for _ in range(100):
            if cmd("HASH " + dst[P]).startswith("OK rc=0"): break
            time.sleep(0.05)
        r = reserve(C, 0, len(lines[C])); say("C reserve: " + r)
        lat.append(kv(r, "us_per_insert"))
        rc, _ = asm(dst[C], "tmp")
        need(rc == 1, "pair %d: child handed over before its parent: assemble rc 1 (lineage pending), got %s" % (i, rc))
        r = reserve(P, 0, iA); say("P reserve (up to the fork ordinal, excluded): " + r)
        rc, _ = asm(dst[C], "tmp")
        need(rc == 1, "pair %d: parent still short of the fork ordinal: child rc 1, got %s" % (i, rc))
        r = reserve(P, iA, len(PL)); say("P reserve (rest): " + r)
        lat.append(kv(r, "us_per_insert"))
        settle("pair %d" % i)
        rcc = None
        for _ in range(200):
            rcc, bc = asm(dst[C], "C%d0" % i)
            if rcc == 0: break
            time.sleep(0.05)
        need(rcc == 0, "pair %d: parent crossed the fork ordinal: child answers rc 0, got %s" % (i, rcc))
        before[C] = (rcc, bc)
        rcp, bp = asm(dst[P], "P%d0" % i); before[P] = (rcp, bp)
        need(rcp == 0, "pair %d: parent answers rc 0, got %s" % (i, rcp))
    st, st2 = settle("step 1")
    say("after step 1: " + st + " | " + st2)
    # ---- step 2: half of the bytes, shuffled, with holes
    for k in ("X", "P1", "C1", "P2", "C2", "P3", "C3"):
        if k not in dst or dst[k] not in created: continue
        n = len(lines[k])
        r = cmd("FLUSHW %s 777 %d" % (dst[k], n // 2))
        sz, nz = zeros(dst[k])
        say("step 2 %s: %s | file %d bytes, %d NUL" % (k, r, sz, nz))
    time.sleep(0.5)
    holes_seen = sum(1 for k in dst if dst[k] in created and zeros(dst[k])[1] > 0)
    need(holes_seen >= 1, "step 2: the files hold NUL holes now (%d files)" % holes_seen)
    st = cmd("STATS"); say("after step 2: " + st)
    mid = {}
    for k in before:
        rc, b = asm(dst[k], k + "1"); mid[k] = (rc, b)
        need(rc == before[k][0] and span(b) == span(before[k][1]), "step 2: %s answer with half of the bytes on disk has items and tokens byte-identical to the answer with none (rc %s, %d bytes)" % (k, rc, len(b)))
    # ---- step 3: the rest
    for k in ("X", "P1", "C1", "P2", "C2", "P3", "C3"):
        if k not in dst or dst[k] not in created: continue
        r = cmd("FLUSHW %s 778 100000000" % dst[k])
        sz, nz = zeros(dst[k])
        say("step 3 %s: %s | file %d bytes (source %d), %d NUL" % (k, r, sz, os.path.getsize(srcs[k]), nz))
        need(sz == os.path.getsize(srcs[k]) and nz == 0 and open(dst[k], "rb").read() == open(srcs[k], "rb").read(), "step 3: %s file is complete and equal to its source" % k)
    st, st2 = settle("step 3", L0 + sum(len(v) for v in lines.values()))
    say("after step 3: " + st + " | " + st2)
    need(kv(st, "uw_lines") == 0 and kv(st, "uw_bytes") == 0, "step 3: every copy was released (uw_lines %s, uw_bytes %s)" % (kv(st, "uw_lines"), kv(st, "uw_bytes")))
    need(kv(st, "uw_added") == kv(st, "uw_released"), "step 3: copies made == copies released (%s, %s)" % (kv(st, "uw_added"), kv(st, "uw_released")))
    r1 = cmd("WRITTEN %s 0" % dst["X"]); r2 = cmd("WRITTEN %s 999999999" % dst["X"]); r3 = cmd("WRITTEN /nonexistent/x.jsonl 0")
    need(r1.endswith("rc=-3") and r2.endswith("rc=-3") and r3.endswith("rc=-2"), "vrs_written on an unknown key / released key / unknown file: %s | %s | %s" % (r1, r2, r3))
    hashes = {}
    after = {}
    for k in before:
        rc, b = asm(dst[k], k + "2"); after[k] = (rc, b)
        need(rc == before[k][0] and span(b) == span(before[k][1]), "step 3: %s answer after all bytes are on disk has items and tokens byte-identical to the answer with none" % k)
    hashes = {k: cmd("HASH " + dst[k]) for k in dst}
    cmd("CELLS " + os.path.join(WORK, "cells_live.txt"))
    # ---- the reference: a fresh original 42f over the final files
    env = dict(os.environ, VRS9SYN_SERVE="1", VRS9_SEGWIN="1", CODEX_VRS_SOCK=SOCK)
    if os.path.exists(SOCK): os.remove(SOCK)
    orig = subprocess.Popen(["taskset", "-c", "0-11", os.path.join(ORIGDIR, "vrs9syn42f"), "serve", SNAP, str(BUDGET)], env=env,
                            stdout=open(os.path.join(WORK, "orig5.log"), "w"), stderr=open(os.path.join(WORK, "orig5.err"), "w"))
    say("fresh orig pid %d" % orig.pid)
    for _ in range(400):
        if os.path.exists(SOCK): break
        time.sleep(3)
    assert os.path.exists(SOCK), "orig did not start"
    time.sleep(1)
    paths = []
    for r_, _, fs in os.walk(SNAP):
        for f in fs:
            if f.endswith(".jsonl"): paths.append(os.path.join(r_, f))
    paths.sort()
    say("files in the tree: %d" % len(paths))
    ref = {p: ask(p) for p in paths}
    for k in before:
        so, sm = span(ref[dst[k]]), span(before[k][1])
        need(so is not None and sm is not None and so == sm, "%s: the answer given BEFORE any byte was on disk equals the fresh 42f over the final file (%s bytes of items)" % (k, len(sm[0]) if sm else None))

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
    for nm, pth in (("yorig", OLDFILE["Y"]), ("ycopy", dst["Y"]), ("p1orig", OLDFILE["P1"]), ("p1copy", dst["P1"])): cmd("OBSDUMP %s %s" % (pth, os.path.join(WORK, "obs_live_%s.txt" % nm)))
    say(cmd("CLOSE"))
    say(cmd("OPEN %s %s" % (SNAP, idx)))
    st = cmd("STATS"); say(st)
    cmd("CELLS " + os.path.join(WORK, "cells_restart.txt"))
    h2 = {k: cmd("HASH " + dst[k]) for k in dst}
    for k in dst:
        ok = hashes[k] == h2[k]
        say("hash after restart %s %s" % (k, "SAME" if ok else "DIFF"))
        if not ok: fails += 1
    compare("restart")
    obs_rest = {p: cmd("OHASH " + p) for p in paths}
    bad = [p for p in paths if obs_live[p] != obs_rest[p]]
    say("observer hash, live-built vs restored from its shards: %d sessions, %d different" % (len(paths), len(bad)))
    if bad: fails += 1
    say(cmd("CLOSE"))
    cold = os.path.join(WORK, "idx_cold")
    shutil.rmtree(cold, ignore_errors=True)
    t1 = time.time()
    say(cmd("OPEN %s %s" % (SNAP, cold)))
    say("cold build %.1f s" % (time.time() - t1))
    cmd("CELLS " + os.path.join(WORK, "cells_cold.txt"))
    obs_cold = {p: cmd("OHASH " + p) for p in paths}
    for nm, pth in (("yorig", OLDFILE["Y"]), ("ycopy", dst["Y"]), ("p1orig", OLDFILE["P1"]), ("p1copy", dst["P1"])): cmd("OBSDUMP %s %s" % (pth, os.path.join(WORK, "obs_cold_%s.txt" % nm)))
    bad = [p for p in paths if obs_live[p] != obs_cold[p]]
    say("observer hash, live-built vs built from scratch: %d sessions, %d different" % (len(paths), len(bad)))
    for p in bad[:10]: say("  differs: " + os.path.basename(p))
    if bad: fails += 1

    def cells(n): return {l.split()[0]: l.strip() for l in open(os.path.join(WORK, "cells_%s.txt" % n))}
    cl, cr, cc = cells("live"), cells("restart"), cells("cold")
    for a_, b_, nm in ((cl, cr, "live vs restart"), (cl, cc, "live vs cold")):
        dif = [k for k in set(a_) | set(b_) if a_.get(k) != b_.get(k)]
        say("cells %s: %d cells in use, %d different" % (nm, len(set(a_) | set(b_)), len(dif)))
        if dif: fails += 1
    compare("cold")
    say("vrs_insert latency per call (us, mean per RESERVE batch): %s" % ", ".join("%.1f" % x for x in lat if x is not None))
finally:
    try: say(cmd("QUIT"))
    except Exception: pass
    try: lib.wait(timeout=60)
    except Exception: lib.kill()
    if orig is not None:
        orig.terminate()
        try: orig.wait(timeout=60)
        except Exception: orig.kill()
    for p in created:
        try: os.remove(p)
        except OSError: pass
    for d in (NEWDIR, os.path.join(SNAP, "2027", "01"), os.path.join(SNAP, "2027")):
        try: os.rmdir(d)
        except OSError: pass
    open(os.path.join(WORK, "live_cmp5_result.txt"), "w", encoding="utf-8").write("\n".join(log) + "\nfails %d\n" % fails)
print("fails", fails)
sys.exit(1 if fails else 0)
