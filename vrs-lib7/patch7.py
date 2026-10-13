#!/usr/bin/env python3
"""Round 7 (VRS_코덱스일체화_v1.md §9, V6-03): view time θᵛ, present t = θᵛ(request line), in-view bounds by view position, output order (θᵛ, position).
usage: patch7.py <file> lib|42x"""
import pathlib
import sys

p = pathlib.Path(sys.argv[1])
mode = sys.argv[2]
s = p.read_text(encoding="utf-8")


def rep(old, new, label, count=1):
    global s
    n = s.count(old)
    if n != count:
        raise SystemExit(f"{label}: expected {count} match(es), found {n}")
    s = s.replace(old, new)


own_n = "sn.nsess" if mode == "lib" else "S.sess[sg].size()"
pre = """    // 7th stage D15/D16 (VRS_코덱스일체화_v1.md §9): the view time thv(x) = max(theta*(x), M_k) (M_k: the latest theta* of the segments before x's),
    // the present t = thv(request line); bounds inside the view by view position (D17)
    std::vector<uint32_t> vs_sg, vs_n; std::vector<size_t> vs_off; std::vector<uint64_t> Mb;
    {
      uint64_t mx = 0; size_t o = 0;
      if (lsg) for (auto& g : *lsg) {
        vs_sg.push_back(g[0]); vs_n.push_back(g[1]); vs_off.push_back(o); Mb.push_back(mx); o += g[1];
        if (g[1]) mx = std::max<uint64_t>(mx, S.it[S.sess[g[0]][g[1] - 1]].th);
        if (g[3]) mx = std::max<uint64_t>(mx, S.TT[S.tl[g[0]][g[3] - 1]]->the);
      }
      vs_sg.push_back(sg); vs_n.push_back(uint32_t(OWN_N)); vs_off.push_back(o); Mb.push_back(mx);
    }
    t = std::max<uint64_t>(t, Mb.back());
    auto vseg = [&](uint32_t m) -> int { const uint32_t s0 = S.it[m].sess, p0 = S.it[m].pos;
      for (size_t k = 0; k < vs_sg.size(); k++) if (vs_sg[k] == s0) return p0 < vs_n[k] ? int(k) : -1;
      return -1; };
    auto thv = [&](uint32_t m) -> uint64_t { const uint64_t th = S.it[m].th; const int k = vseg(m); return k < 0 ? th : std::max<uint64_t>(th, Mb[k]); };
    auto vpos = [&](uint32_t m) -> size_t { const int k = vseg(m); return k < 0 ? SIZE_MAX : vs_off[k] + S.it[m].pos; };
    auto okey = [&](uint32_t m) { const size_t vp = vpos(m); return std::make_pair(thv(m), vp != SIZE_MAX ? uint64_t(vp) : uint64_t(L.size()) + m); };
""".replace("OWN_N", own_n)
rep("    // last position with theta <= t (binary search; D-ctx-01)\n",
    pre + "    // last position with theta <= t (binary search; D-ctx-01); 7th stage: by thv, which does not go down along the view (lemma 7-1)\n",
    "prelude")
rep("auto ub = [&](const View& v) { size_t lo = 0, h = v.size(); while (lo < h) { size_t md = (lo + h) / 2; if (S.it[v[md]].th <= t) lo = md + 1; else h = md; } return lo; };",
    "auto ub = [&](const View& v) { size_t lo = 0, h = v.size(); while (lo < h) { size_t md = (lo + h) / 2; if (thv(v[md]) <= t) lo = md + 1; else h = md; } return lo; };",
    "ub")
rep("        const uint64_t thx = S.it[L[from]].th;\n        size_t lo = 0, h2 = uh; while (lo < h2) { size_t md = (lo + h2) / 2; if (S.it[U[md]].th < thx) lo = md + 1; else h2 = md; }\n",
    "        size_t lo = 0, h2 = uh; while (lo < h2) { size_t md = (lo + h2) / 2; if (vpos(U[md]) < from) lo = md + 1; else h2 = md; }  // D17: by view position\n",
    "U_x")
rep("mdl(L[r - 1]) && S.it[L[r - 1]].th <= t && S.it[L[r - 1]].sess == S.it[z].sess",
    "mdl(L[r - 1]) && thv(L[r - 1]) <= t && S.it[L[r - 1]].sess == S.it[z].sess", "runs_of")
if mode == "lib":
    rep("      const uint64_t th0 = open ? sn.th0 : t;\n", "      const uint64_t th0 = open ? std::max<uint64_t>(sn.th0, Mb.back()) : t;  // D16\n", "th0")
else:
    rep("      const uint64_t th0 = xo != UINT32_MAX ? TT[xo]->th0 : open ? otp->th0 : t;",
        "      const uint64_t th0 = std::max<uint64_t>(xo != UINT32_MAX ? TT[xo]->th0 : open ? otp->th0 : t, Mb.back());  // D16", "th0")
rep("if (!S.it[U[q]].fwd || S.it[U[q]].th >= thx_open) N3.push_back(U[q]);",
    "if (!S.it[U[q]].fwd || (thx_open != UINT64_MAX && vpos(U[q]) >= from)) N3.push_back(U[q]);  // D17", "relays")
n_sort = 1 if mode == "lib" else 3
rep("std::sort(A.ids.begin(), A.ids.end(), [&](uint32_t a, uint32_t b) { return S.it[a].th < S.it[b].th; });",
    "std::sort(A.ids.begin(), A.ids.end(), [&](uint32_t a, uint32_t b) { return okey(a) < okey(b); });  // D17",
    "sort", n_sort)
p.write_text(s, encoding="utf-8")
print("patched7", mode)
