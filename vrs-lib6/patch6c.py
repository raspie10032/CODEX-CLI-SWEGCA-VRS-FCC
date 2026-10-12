#!/usr/bin/env python3
"""Round 6 fix of P-12 (T6-1 (b) failed): no prefix shortcut (a link inside the root was kept), and the real path of the longest existing
ancestor + the rest for a directory that does not exist yet (cached only once the whole directory exists)."""
import pathlib
import sys

p = pathlib.Path(sys.argv[1]) / "vrs_lib.cpp"
s = p.read_text(encoding="utf-8")
old = s[s.index("// P-12: the path a caller hands in, as the store spells it"):s.index("Sess* get_sess(Store& S, const std::string& p, bool create) {\n")]
new = r'''// P-12: the path a caller hands in, as the store spells it: the real path of its directory plus its name (the file may not exist yet).
// A directory that does not exist yet: the real path of its longest existing ancestor plus the rest (what the directory will be once made,
// links are only ever in existing parts). Each thread keeps its own cache (no shared state), filled only once the whole directory exists.
std::string canon_path(const Store& S, const char* p) {
  (void)S;
  const std::string in(p);
  thread_local std::unordered_map<std::string, std::string> cache;
  if (cache.size() > 4096) cache.clear();
  const auto it = cache.find(in);
  if (it != cache.end()) return it->second;
  const size_t sl = in.rfind('/');
  if (sl == std::string::npos || sl == 0) return in;
  size_t cut = sl;  // in[0, cut) is the directory part being resolved; in[cut, end) is appended as is
  for (;;) {
    const std::string dir = in.substr(0, cut);
    if (char* r = ::realpath(dir.c_str(), nullptr)) {
      std::string out = std::string(r) + in.substr(cut);
      std::free(r);
      if (cut == sl) cache.emplace(in, out);
      return out;
    }
    const size_t up = in.rfind('/', cut - 1);
    if (up == std::string::npos || up == 0) return in;
    cut = up;
  }
}
'''
s = s.replace(old, new)
p.write_text(s, encoding="utf-8")
print("patched c")
