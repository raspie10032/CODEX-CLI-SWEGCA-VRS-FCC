s = open("$WORK/vrsint5/vrs_lib.cpp", encoding="utf-8").read()
a = "  return phi == c->phi || !ps.p.stable();  // 𝔅 is moving: the turn that moves it looks at the units that depend on it when it is in\n"
b = ("  // A unit is the unit of the windows only when a pass that saw no turn come in (or go out of the middle of coming in) found the fingerprint it was made over.\n"
     "  // While 𝔅 is moving nothing is concluded: the caller counts again (build_unit repeats its pass until it saw one state). The turn that moves it looks at the units that\n"
     "  // depend on it when it is in, but a turn that finished before that look and met a unit not installed yet (null) skipped it; this check after the install is what catches that.\n"
     "  return ps.p.stable() && phi == c->phi;\n")
assert s.count(a) == 1
s = s.replace(a, b)
open("$WORK/vrsint5/vrs_lib.cpp", "w", encoding="utf-8").write(s)
