s = open("$WORK/vrsint5/vrs_lib.cpp", encoding="utf-8").read()
a = '''    std::fprintf(f, "%016llx %llu ny=%llu phi=%016llx ne=%zu h=%016llx\\n", (unsigned long long)t->seed, (unsigned long long)t->o0, c ? (unsigned long long)c->ny : 0ull, c ? (unsigned long long)c->phi : 0ull, c ? c->e.size() : (size_t)0, (unsigned long long)hh);'''
assert a in s, "anchor"
b = '''    const A0Val* a0 = t->a0.load(std::memory_order_acquire);
    uint64_t av = 0, ab = 0; size_t nv = 0, nb = 0;
    if (a0) { for (uint32_t y : a0->v) av += ci_mix(S.TT[y]->seed ^ S.TT[y]->o0); for (uint32_t y : a0->Yb) ab += ci_mix(S.TT[y]->seed ^ S.TT[y]->o0); nv = a0->v.size(); nb = a0->Yb.size(); }
    std::fprintf(f, "%016llx %llu ny=%llu phi=%016llx ne=%zu h=%016llx a0v=%zu/%016llx a0yb=%zu/%016llx\\n", (unsigned long long)t->seed, (unsigned long long)t->o0, c ? (unsigned long long)c->ny : 0ull, c ? (unsigned long long)c->phi : 0ull, c ? c->e.size() : (size_t)0, (unsigned long long)hh, nv, (unsigned long long)av, nb, (unsigned long long)ab);'''
s = s.replace(a, b, 1)
open("$WORK/vrsint5/vrs_lib.cpp", "w", encoding="utf-8").write(s)
