import sys, struct, collections, glob
def frames(p):
    b = open(p, 'rb').read(); pos = 0; out = []
    while pos + 16 <= len(b):
        magic, t, ln = struct.unpack_from('<IB', b, pos)[0], b[pos + 4], struct.unpack_from('<I', b, pos + 8)[0]
        if pos + 16 + ln > len(b): break
        out.append((t, b[pos + 16:pos + 16 + ln])); pos += 16 + ln
    return out
a = sys.argv[1]; c = sys.argv[2]
fa = [f for f in frames(a) if f[0] not in (5, 6, 7)]
fc = [f for f in frames(c) if f[0] not in (5, 6, 7)]
ca, cc = collections.Counter(fa), collections.Counter(fc)
print("full", len(fa), "cut", len(fc), "types full", collections.Counter(t for t, _ in fa), "cut", collections.Counter(t for t, _ in fc))
for k, v in (ca - cc).items(): print("only in full x%d" % v, k[0], k[1][:60].hex(), len(k[1]))
for k, v in (cc - ca).items(): print("only in cut x%d" % v, k[0], k[1][:60].hex(), len(k[1]))
