s = open("$WORK/vrsint5/vrs_lib.cpp", encoding="utf-8").read()
hook = r'''
int vrs_dbg_unit_dump(vrs_h* h, const char* file) {  // every turn: its seed, the size of its Y, the fingerprint of its set and a hash of its unit
  if (!h || !file) return -1;
  Store& S = *h->S;
  EbrGuard guard(S);
  FILE* f = std::fopen(file, "w");
  if (!f) return -3;
  const uint32_t n = S.nturn.load();
  for (uint32_t id = 1; id <= n; id++) {
    const TurnRec* t = S.TT[id];
    if (!t) continue;
    const Contrib* c = t->ctr.load(std::memory_order_acquire);
    uint64_t hh = 1469598103934665603ull;
    if (c) for (const CEnt& e : c->e) { hh ^= (uint64_t(e.cell) << 32) ^ e.cnt ^ (uint64_t(e.fl) << 48); hh *= 1099511628211ull; }
    std::fprintf(f, "%016llx %llu ny=%llu phi=%016llx ne=%zu h=%016llx\n", (unsigned long long)t->seed, (unsigned long long)t->o0, c ? (unsigned long long)c->ny : 0ull, c ? (unsigned long long)c->phi : 0ull, c ? c->e.size() : (size_t)0, (unsigned long long)hh);
  }
  std::fclose(f);
  return 0;
}
'''
m = "// order-sensitive hash of everything vrs_insert/restore put into the tables"
assert m in s and "vrs_dbg_unit_dump" not in s
s = s.replace(m, hook + m, 1)
open("$WORK/vrsint5/vrs_lib.cpp", "w", encoding="utf-8").write(s)
h = open("$WORK/vrsint5/vrs.h", encoding="utf-8").read()
h = h.replace("int  vrs_dbg_obs_hash(", "int  vrs_dbg_unit_dump(vrs_h*, const char* file);   /* per turn: the contribution unit */\nint  vrs_dbg_obs_hash(", 1)
open("$WORK/vrsint5/vrs.h", "w", encoding="utf-8").write(h)
d = open("$WORK/vrsint5/vrs_t_live5.cpp", encoding="utf-8").read()
d = d.replace('    } else if (cmd == "OHASH") {', '    } else if (cmd == "UNITDUMP") {\n      std::string f; is >> f; std::printf("OK rc=%d\\n", vrs_dbg_unit_dump(H, f.c_str()));\n    } else if (cmd == "OHASH") {', 1)
open("$WORK/vrsint5/vrs_t_live5.cpp", "w", encoding="utf-8").write(d)
q = open("$WORK/vrsint5/test5/live7q.py", encoding="utf-8").read()
a = '''    sh_live = {p: cmd("HASH " + p) for p in paths}'''
assert a in q
q = q.replace(a, a + '''
    cmd("UNITDUMP " + os.path.join(WORK, "units_live.txt"))''', 1)
a = '''    sh_cold = {p: cmd("HASH " + p) for p in paths}'''
assert a in q
q = q.replace(a, a + '''
    cmd("UNITDUMP " + os.path.join(WORK, "units_cold.txt"))''', 1)
open("$WORK/vrsint5/test5/live7q.py", "w", encoding="utf-8").write(q)
