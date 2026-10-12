s = open("$WORK/vrsint5/vrs_lib.cpp", encoding="utf-8").read()
hook = r'''
int vrs_dbg_obs_dump(vrs_h* h, const char* path, const char* file) {  // per closed turn of one session: the observer fields and the seeds of its reference turns
  if (!h || !path || !file) return -1;
  Store& S = *h->S;
  EbrGuard guard(S);
  Sess* ss = get_sess(S, path, false);
  if (!ss) return -2;
  FILE* f = std::fopen(file, "w");
  if (!f) return -3;
  const PubView pv = pub_view(S, *ss);
  for (size_t i = 0, n = pv.ntl; i < n; i++) {
    const uint32_t y = ss->tl[i];
    const ObsY* o = obs_of(S, y);
    const Win w = window_of(S, *S.TT[y]);
    uint64_t rh = 0; for (uint32_t p : o->R) rh = rh * 1099511628211ull + S.TT[S.B[w.lo + p]]->seed;
    uint64_t t = 0; std::memcpy(&t, &o->tau, sizeof t);
    std::fprintf(f, "%zu seed=%llx the=%llu k=%u wn=%u lo=%u phi=%llx bad=%d rules=%d m0=%u max=%u med=%u tau=%llx R=%llx\n", i, (unsigned long long)S.TT[y]->seed, (unsigned long long)S.TT[y]->the, o->k, o->wn, (unsigned)w.lo, (unsigned long long)o->phi, (int)o->bad, o->rules ? 1 : 0, o->m0, o->max, o->med, (unsigned long long)t, (unsigned long long)rh);
  }
  std::fclose(f);
  return 0;
}
'''
m = "// order-sensitive hash of everything vrs_insert/restore put into the tables"
assert m in s
s = s.replace(m, hook + m, 1)
open("$WORK/vrsint5/vrs_lib.cpp", "w", encoding="utf-8").write(s)
h = open("$WORK/vrsint5/vrs.h", encoding="utf-8").read()
h = h.replace("int  vrs_dbg_obs_hash(", "int  vrs_dbg_obs_dump(vrs_h*, const char* path, const char* file);   /* per closed turn: the observer fields */\nint  vrs_dbg_obs_hash(", 1)
open("$WORK/vrsint5/vrs.h", "w", encoding="utf-8").write(h)
# the live driver: OBSDUMP <path> <file>
d = open("$WORK/vrsint5/vrs_t_live5.cpp", encoding="utf-8").read()
d = d.replace('    } else if (cmd == "OHASH") {', '    } else if (cmd == "OBSDUMP") {\n      std::string p, f; is >> p >> f; std::printf("OK rc=%d\\n", vrs_dbg_obs_dump(H, p.c_str(), f.c_str()));\n    } else if (cmd == "OHASH") {', 1)
open("$WORK/vrsint5/vrs_t_live5.cpp", "w", encoding="utf-8").write(d)
