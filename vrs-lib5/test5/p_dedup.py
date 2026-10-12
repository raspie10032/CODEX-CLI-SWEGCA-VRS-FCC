s = open("$WORK/vrsint5/vrs_lib.cpp", encoding="utf-8").read()
key = "int vrs_dbg_obs_dump(vrs_h* h"
a = s.find(key)
b = s.find(key, a + 10)
assert a >= 0 and b > a
end = s.find("\n}\n", b) + 3
s = s[:b] + s[end:].lstrip("\n")
assert s.count(key) == 1
open("$WORK/vrsint5/vrs_lib.cpp", "w", encoding="utf-8").write(s)
h = open("$WORK/vrsint5/vrs.h", encoding="utf-8").read()
k2 = "int  vrs_dbg_obs_dump("
if h.count(k2) > 1:
    i = h.find(k2); j = h.find(k2, i + 5); e = h.find("\n", j) + 1
    h = h[:j] + h[e:]
open("$WORK/vrsint5/vrs.h", "w", encoding="utf-8").write(h)
d = open("$WORK/vrsint5/vrs_t_live5.cpp", encoding="utf-8").read()
print("OBSDUMP count in driver", d.count('cmd == "OBSDUMP"'))
