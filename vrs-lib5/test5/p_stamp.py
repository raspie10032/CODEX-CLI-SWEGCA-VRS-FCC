s = open("$WORK/vrsint5/vrs_lib.cpp", encoding="utf-8").read()
def rep(a, b):
    global s
    assert s.count(a) == 1, a[:70]
    s = s.replace(a, b)
# 1: the stamp says "good in the state f0"; ph was read from the pass memo (the state at the pass start), so inside a pass the stamp is only put when the pass state is the state now
rep("        if (f0 == s0 && S.B.started.load(std::memory_order_seq_cst) == s0 && S.B.finished.load(std::memory_order_seq_cst) == f0) p->vstamp.store(f0 + 1, std::memory_order_release);",
    "        if (f0 == s0 && S.B.started.load(std::memory_order_seq_cst) == s0 && S.B.finished.load(std::memory_order_seq_cst) == f0 && (!tl_pass || (tl_pass->fin0 == f0 && tl_pass->st0 == s0)))\n          p->vstamp.store(f0 + 1, std::memory_order_release);  // (inside a pass ph is the sum at the pass start: stamping it for a later state would call an old A0 good there)")
# 2: on_turn_in: the rank of z is read again for every y (a turn that came in below z meanwhile moves the positions of the turns above)
rep("    if ((int64_t)S.B.rank(S.TT[y]->the) - (int64_t)p0 >= (int64_t)OBS_W) break;  // z is below the window of y and of every turn above",
    "    if ((int64_t)S.B.rank(S.TT[y]->the) - (int64_t)S.B.rank(tz.the + 1) >= (int64_t)OBS_W) break;  // z is below the window of y and of every turn above (z's rank is read again: a turn that came in below moves both)")
open("$WORK/vrsint5/vrs_lib.cpp", "w", encoding="utf-8").write(s)
