s = open('$WORK/vrsint5/test5/live7.py', encoding='utf-8').read()
a = s.index('    env = dict(os.environ, VRS9SYN_SERVE="1"')
b = s.index('    ref = {p: ask(p) for p in paths}')
s = s[:a] + '    ref = {}\n' + s[b + len('    ref = {p: ask(p) for p in paths}'):]
s = s.replace('    compare("live")\n', '').replace('    compare("restart")\n', '').replace('    compare("cold")\n', '')
open('$WORK/vrsint5/test5/live7q.py', 'w', encoding='utf-8').write(s)

s = open('$WORK/vrsint5/test5/live7q.py', encoding='utf-8').read()
a = '''    obs_live = {p: cmd("OHASH " + p) for p in paths}'''
assert a in s
s = s.replace(a, a + '''
    sh_live = {p: cmd("HASH " + p) for p in paths}''', 1)
a = '''    obs_cold = {p: cmd("OHASH " + p) for p in paths}'''
assert a in s
s = s.replace(a, a + '''
    sh_cold = {p: cmd("HASH " + p) for p in paths}
    badh = [p for p in paths if sh_live[p] != sh_cold[p]]
    say("session hash (items, turn data), live-built vs built from scratch: %d sessions, %d different" % (len(paths), len(badh)))
    for p in badh[:10]: say("  session hash differs: " + p)''', 1)
open('$WORK/vrsint5/test5/live7q.py', 'w', encoding='utf-8').write(s)
