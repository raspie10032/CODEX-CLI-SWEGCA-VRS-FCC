#!/usr/bin/env python3
"""T7-3: compare two directories of vrs_cli --out answers by their items arrays and token counts (the "us" field is a timing).
For a file whose items differ, report whether the two lists are the same multiset (only the order differs) and the first differing index.
usage: cmp_items.py <dir a> <dir b>"""
import json
import os
import sys

a, b = sys.argv[1], sys.argv[2]
same = order_only = diff = missing = 0
for name in sorted(os.listdir(a)):
    pa, pb = os.path.join(a, name), os.path.join(b, name)
    if not os.path.exists(pb):
        missing += 1
        print("MISSING", name)
        continue
    ja = json.load(open(pa, encoding="utf-8"))
    jb = json.load(open(pb, encoding="utf-8"))
    ia, ib = ja.get("items"), jb.get("items")
    if ia == ib and ja.get("tokens") == jb.get("tokens") and ja.get("ok") == jb.get("ok"):
        same += 1
        continue
    sa = sorted(json.dumps(x, sort_keys=True, ensure_ascii=False) for x in (ia or []))
    sb = sorted(json.dumps(x, sort_keys=True, ensure_ascii=False) for x in (ib or []))
    first = next((i for i, (x, y) in enumerate(zip(ia or [], ib or [])) if x != y), min(len(ia or []), len(ib or [])))
    if sa == sb and ja.get("tokens") == jb.get("tokens"):
        order_only += 1
        print("ORDER", name, "first index", first, "of", len(ia))
    else:
        diff += 1
        print("DIFF", name, "items", len(ia or []), len(ib or []), "tokens", ja.get("tokens"), jb.get("tokens"), "first index", first)
print(f"compared {same + order_only + diff} same {same} order_only {order_only} diff {diff} missing {missing}")
