s = open("$WORK/vrsint5/vrs_lib.cpp", encoding="utf-8").read()
def rep(a, b):
    global s
    assert s.count(a) == 1, (s.count(a), a[:60])
    s = s.replace(a, b)
rep("  uint32_t rturns = 0;             // restored closed turns (their slots are not used)\n",
    "  uint32_t rturns = 0;             // restored closed turns (their slots are not used)\n  std::unordered_set<uint64_t> have_rec;  // restore: offsets of the lines after base_end whose records the shard holds already (the lines of the open turn are read again; their records are not written again)\n")
rep("    emit_item(wb, m, L.ts, L.r, L.ord, L.pfx);\n  }\n", "    if (!have) emit_item(wb, m, L.ts, L.r, L.ord, L.pfx);\n  }\n")
rep("  if (L.fl & LF_META) emit_meta(wb, off, L.len, L.ord, L.ts, L.r, ss);\n  if (start) emit_ts(wb, off, L.len, L.ord, L.ord, L.ts, L.r);\n",
    "  if ((L.fl & LF_META) && !have) emit_meta(wb, off, L.len, L.ord, L.ts, L.r, ss);\n  if (start && !have) emit_ts(wb, off, L.len, L.ord, L.ord, L.ts, L.r);\n")
rep("  const bool item = (L.fl & LF_ITEM) != 0, user = (L.fl & LF_USER) != 0, start = (L.fl & LF_START) != 0;\n  uint32_t ib = 0, ub = 0, sb = 0;\n",
    "  const bool item = (L.fl & LF_ITEM) != 0, user = (L.fl & LF_USER) != 0, start = (L.fl & LF_START) != 0;\n  const bool have = !ss.have_rec.empty() && ss.have_rec.count(off) != 0;\n  uint32_t ib = 0, ub = 0, sb = 0;\n")
rep("  size_t k = (size_t)(std::lower_bound(I.begin(), I.end(), start, [](const ItemP& a, uint64_t v) { return a.off < v; }) - I.begin());  // items before start\n",
    "  size_t k = (size_t)(std::lower_bound(I.begin(), I.end(), start, [](const ItemP& a, uint64_t v) { return a.off < v; }) - I.begin());  // items before start\n  for (size_t i = k; i < n; i++) ss.have_rec.insert(I[i].off);\n  for (const auto& x : sh.tss) if (x.off >= start) ss.have_rec.insert(x.off);\n  for (const auto& m : sh.metas) if (m.off >= start) ss.have_rec.insert(m.off);\n")
open("$WORK/vrsint5/vrs_lib.cpp", "w", encoding="utf-8").write(s)
