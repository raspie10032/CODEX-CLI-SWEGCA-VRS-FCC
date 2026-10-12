s = open("$WORK/vrsint5/vrs_lib.cpp", encoding="utf-8").read()
a = "  if (v.open) {  // the open turn: the lines of its slot below the end of the prefix\n    const TurnSlot& sl = *ss.slots.find(v.sa);\n"
b = "  if (v.open) {  // the open turn: the lines of its slot below the end of the prefix\n    const TurnSlot* slp = ss.slots.find(v.sa);\n    if (!slp) { sn.open = false; }  // no slot yet: the start line of the turn has not been processed; there is no open turn to read\n    else {\n    const TurnSlot& sl = *slp;\n"
assert s.count(a) == 1
s = s.replace(a, b)
a2 = "    sn.open = true; sn.pos0 = g.pos0; sn.th0 = g.th0; sn.tq1 = p.tq1; sn.q1 = std::move(p.q1); sn.ocalls = agg_ocalls_set(g);\n  }\n"
b2 = "    sn.open = true; sn.pos0 = g.pos0; sn.th0 = g.th0; sn.tq1 = p.tq1; sn.q1 = std::move(p.q1); sn.ocalls = agg_ocalls_set(g);\n    }\n  }\n"
assert s.count(a2) == 1
s = s.replace(a2, b2)
open("$WORK/vrsint5/vrs_lib.cpp", "w", encoding="utf-8").write(s)
