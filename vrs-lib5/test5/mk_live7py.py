s = open('$WORK/vrsint5/libsrc/live_cmp7.py', encoding='utf-8').read()
a = '''    bad = [p for p in paths if obs_live[p] != obs_rest[p]]
    say("observer hash, live-built vs restored from its shards: %d sessions, %d different" % (len(paths), len(bad)))'''
b = a + '''
    for p in bad[:10]: say("  differs: " + p)'''
assert a in s
s = s.replace(a, b, 1)
a = '''    obs_live = {p: cmd("OHASH " + p) for p in paths}'''
b = a + '''
    for nm, pth in (("A", dst["A"]), ("B", dst["B"]), ("C", dst["C"])): cmd("OBSDUMP %s %s" % (pth, os.path.join(WORK, "obs_live_%s.txt" % nm)))'''
assert a in s
s = s.replace(a, b, 1)
a = '''    obs_cold = {p: cmd("OHASH " + p) for p in paths}'''
b = a + '''
    for nm, pth in (("A", dst["A"]), ("B", dst["B"]), ("C", dst["C"])): cmd("OBSDUMP %s %s" % (pth, os.path.join(WORK, "obs_cold_%s.txt" % nm)))
    for p in [p for p in paths if obs_live[p] != obs_cold[p]][:10]:
        say("  cold differs: " + p); cmd("OBSDUMP %s %s" % (p, os.path.join(WORK, "obs_cold_diff_%s.txt" % os.path.basename(p))))'''
assert a in s
s = s.replace(a, b, 1)
open('$WORK/vrsint5/test5/live7.py', 'w', encoding='utf-8').write(s)

s = open('$WORK/vrsint5/test5/live7.py', encoding='utf-8').read()
s = s.replace('''for nm, pth in (("A", dst["A"]), ("B", dst["B"]), ("C", dst["C"])): cmd("OBSDUMP %s %s" % (pth, os.path.join(WORK, "obs_live_%s.txt" % nm)))''',
 '''EXTRA = [p for p in paths if "01a0ffa7-8536" in p]
    for nm, pth in (("A", dst["A"]), ("B", dst["B"]), ("C", dst["C"])) + tuple(("x%d" % i, p) for i, p in enumerate(EXTRA)): cmd("OBSDUMP %s %s" % (pth, os.path.join(WORK, "obs_live_%s.txt" % nm)))''', 1)
s = s.replace('''for nm, pth in (("A", dst["A"]), ("B", dst["B"]), ("C", dst["C"])): cmd("OBSDUMP %s %s" % (pth, os.path.join(WORK, "obs_cold_%s.txt" % nm)))''',
 '''for nm, pth in (("A", dst["A"]), ("B", dst["B"]), ("C", dst["C"])) + tuple(("x%d" % i, p) for i, p in enumerate(EXTRA)): cmd("OBSDUMP %s %s" % (pth, os.path.join(WORK, "obs_cold_%s.txt" % nm)))''', 1)
open('$WORK/vrsint5/test5/live7.py', 'w', encoding='utf-8').write(s)
