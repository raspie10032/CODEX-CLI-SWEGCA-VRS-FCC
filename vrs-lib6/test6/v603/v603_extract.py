#!/usr/bin/env python3
"""V6-03 reproducer input: the three rollout files of a failed T-a3 run (captured by the experiment copy), as a script of operations
in the order Hermes made them: W <file> <line> = pwrite then vrs_insert; A <file> = assemble and check.
usage: v603_extract.py <pytest output with EXPFILE dumps> <out dir>"""
import json
import os
import sys

src, out = sys.argv[1], sys.argv[2]
files = {}
cur = None
for ln in open(src, encoding="utf-8"):
    if ln.startswith("EXPFILE "):
        cur = os.path.basename(ln.split()[1])
        files[cur] = []
    elif cur and ln.startswith("   {"):
        files[cur].append(ln[3:].rstrip("\n"))
    elif not ln.startswith("   "):
        cur = None if not ln.startswith("EXP") else cur
# order the files by lineage: root first
meta = {k: json.loads(v[0])["payload"] for k, v in files.items()}
byid = {m["id"]: k for k, m in meta.items()}
order = []
root = [k for k, m in meta.items() if "forked_from_id" not in m][0]
order.append(root)
while True:
    nxt = [k for k, m in meta.items() if m.get("forked_from_id") == meta[order[-1]]["id"]]
    if not nxt:
        break
    order.append(nxt[0])
os.makedirs(out, exist_ok=True)
ops = []
# Hermes order: root file lines up to the first fork's cut; the child is made after the parent wrote everything it has
for i, k in enumerate(order):
    for line in files[k]:
        ops.append("W %d %s" % (i, line))
        if i > 0 and '"role":"user"' in line and '"input_text","text":"after ' in line:
            ops.append("A %d" % i)  # the test assembles right after each new user text in a fork
with open(os.path.join(out, "ops.txt"), "w", encoding="utf-8") as f:
    f.write("\n".join(ops) + "\n")
with open(os.path.join(out, "names.txt"), "w", encoding="utf-8") as f:
    f.write("\n".join(order) + "\n")
print(len(ops), order)
