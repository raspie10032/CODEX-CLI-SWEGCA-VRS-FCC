#!/usr/bin/env python3
"""Round 6 (VRS_코덱스일체화_v1.md §8): D12 file identity, P-12 path canonicalization, P-13 seed + VX06, P-14 vrs_wait.
Applied to $WORK/vrsint6/vrs_lib.cpp and vrs.h (copies of round 5). Every replacement must match exactly once."""
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
src = root / "vrs_lib.cpp"
hdr = root / "vrs.h"
s = src.read_text(encoding="utf-8")
h = hdr.read_text(encoding="utf-8")


def rep(text, old, new, label):
    n = text.count(old)
    if n != 1:
        raise SystemExit(f"{label}: expected 1 match, found {n}")
    return text.replace(old, new)


# includes for futex
s = rep(s, '#include <unistd.h>\n', '#include <unistd.h>\n#include <climits>\n#include <linux/futex.h>\n#include <sys/syscall.h>\n', "includes")

# P-14: progress word + debug hold
s = rep(s,
        "  std::atomic<int64_t> fin_left{0};              // base sessions whose first look after the load has not run\n",
        "  std::atomic<int64_t> fin_left{0};              // base sessions whose first look after the load has not run\n"
        "  std::atomic<uint32_t> progress{0};             // 6th stage P-14: bumped (and futex-woken) when ready is set or a lineage is set up; vrs_wait sleeps on it\n"
        "  std::chrono::steady_clock::time_point hold_ready{};  // test hook VRS_DBG_HOLD_READY_MS (race injection T6-2): ready is not latched before this\n"
        "  std::atomic<int> hold_armed{0};\n",
        "store fields")

# D12 identity helper, futex helpers, canon (placed before get_sess)
helpers = r'''
// 6th stage D12: the identity of a file is the uuid in its name (fid_key), or its path relative to the store root; never the spelling of its path.
uint64_t ident_hash(const Sess& ss) {
  const uint64_t k = fid_key(ss.path);
  return k ? k : fnv(ss.rel.data(), ss.rel.size());
}
// P-14: wake every vrs_wait sleeper after a state change it may be waiting for
void bump_progress(Store& S) {
  S.progress.fetch_add(1, std::memory_order_seq_cst);
  syscall(SYS_futex, reinterpret_cast<uint32_t*>(&S.progress), FUTEX_WAKE_PRIVATE, INT_MAX, nullptr, nullptr, 0);
}
// P-12: the path a caller hands in, as the store spells it: the real path of its directory plus its name (the file may not exist yet).
// Each thread keeps its own cache (no shared state): one realpath per spelling and thread.
std::string canon_path(const Store& S, const char* p) {
  const std::string in(p);
  const std::string pre = S.sdir + "/";
  if (in.size() > pre.size() && in.compare(0, pre.size(), pre) == 0) return in;
  thread_local std::unordered_map<std::string, std::string> cache;
  if (cache.size() > 4096) cache.clear();
  const auto it = cache.find(in);
  if (it != cache.end()) return it->second;
  const size_t sl = in.rfind('/');
  std::string out = in;
  if (sl != std::string::npos && sl > 0) {
    const std::string dir = in.substr(0, sl);
    if (char* r = ::realpath(dir.c_str(), nullptr)) { out = std::string(r) + in.substr(sl); std::free(r); }
  }
  cache.emplace(in, out);
  return out;
}
'''
s = rep(s, "Sess* get_sess(Store& S, const std::string& p, bool create) {\n", helpers.lstrip("\n") + "Sess* get_sess(Store& S, const std::string& p, bool create) {\n", "helpers")

# P-13 seeds
s = rep(s, "  const std::string& path = ss.path;\n  t->seed = fnv(path.data(), path.size()) ^ (uint64_t(p.ord0) * 0x9E3779B97F4A7C15ull);\n",
        "  t->seed = ident_hash(ss) ^ (uint64_t(p.ord0) * 0x9E3779B97F4A7C15ull);  // D12\n", "seed fill")
s = rep(s, "    t->seed = fnv(ss.path.data(), ss.path.size()) ^ (uint64_t(t->ord0) * 0x9E3779B97F4A7C15ull);\n",
        "    t->seed = ident_hash(ss) ^ (uint64_t(t->ord0) * 0x9E3779B97F4A7C15ull);  // D12\n", "seed restore")
s = rep(s, 'constexpr uint32_t VX_MAGIC = 0x35305856u;  // "VX05"', 'constexpr uint32_t VX_MAGIC = 0x36305856u;  // "VX06" (6th stage: D12 seeds); before: "VX05"', "magic")

# ensure_segs: lineage set up -> progress
s = rep(s, "  ss.seg_state.store(2, std::memory_order_seq_cst);\n  drive_counts(S, ss);\n  return true;\n",
        "  ss.seg_state.store(2, std::memory_order_seq_cst);\n  bump_progress(S);  // P-14\n  drive_counts(S, ss);\n  return true;\n", "segs progress")

# maybe_ready: hold hook + progress
s = rep(s,
        "    int z = 0;\n    S.ready.compare_exchange_strong(z, 1, std::memory_order_seq_cst);\n  }\n}\n",
        "    if (S.hold_ready.time_since_epoch().count() && std::chrono::steady_clock::now() < S.hold_ready) {  // T6-2 race injection: latch later\n"
        "      int a = 0;\n"
        "      if (S.hold_armed.compare_exchange_strong(a, 1)) std::thread([&S] { std::this_thread::sleep_until(S.hold_ready); maybe_ready(S); }).detach();\n"
        "      return;\n"
        "    }\n"
        "    int z = 0;\n    if (S.ready.compare_exchange_strong(z, 1, std::memory_order_seq_cst)) bump_progress(S);\n  }\n}\n",
        "maybe_ready")

# vrs_open: real paths + hold hook
s = rep(s,
        "  S.sdir = o->sessions_dir;\n  while (S.sdir.size() > 1 && S.sdir.back() == '/') S.sdir.pop_back();\n  S.idir = o->index_dir ? o->index_dir : \"\";\n  while (S.idir.size() > 1 && S.idir.back() == '/') S.idir.pop_back();\n",
        "  S.sdir = o->sessions_dir;\n  while (S.sdir.size() > 1 && S.sdir.back() == '/') S.sdir.pop_back();\n"
        "  if (char* r = ::realpath(S.sdir.c_str(), nullptr)) { S.sdir = r; std::free(r); }  // P-12: the store root as the file system spells it\n"
        "  S.idir = o->index_dir ? o->index_dir : \"\";\n  while (S.idir.size() > 1 && S.idir.back() == '/') S.idir.pop_back();\n"
        "  if (!S.idir.empty()) { std::error_code ec; fs::create_directories(S.idir, ec); if (char* r = ::realpath(S.idir.c_str(), nullptr)) { S.idir = r; std::free(r); } }\n"
        "  if (const char* hv = std::getenv(\"VRS_DBG_HOLD_READY_MS\")) S.hold_ready = std::chrono::steady_clock::now() + std::chrono::milliseconds(std::atoll(hv));  // T6-2 only\n",
        "open")

# API entry canonicalization
s = rep(s, "  if (len && line[len - 1] == '\\n') len--;\n  Sess* ss = get_sess(S, path, true);\n",
        "  if (len && line[len - 1] == '\\n') len--;\n  Sess* ss = get_sess(S, canon_path(S, path), true);  // P-12\n", "insert canon")
s = rep(s, "  Store& S = *h->S;\n  Sess* ss = get_sess(S, path, false);\n  if (!ss) return -2;\n  if (!uw_del(",
        "  Store& S = *h->S;\n  Sess* ss = get_sess(S, canon_path(S, path), false);  // P-12\n  if (!ss) return -2;\n  if (!uw_del(", "written canon")
s = rep(s, "  if (!path || !*path || B == 0) return -1;\n  Sess* ss = get_sess(S, path, true);\n",
        "  if (!path || !*path || B == 0) return -1;\n  Sess* ss = get_sess(S, canon_path(S, path), true);  // P-12\n", "assemble canon")

# vrs_wait
wait_fn = r'''
// 6th stage P-14 (D13): wait until the store can answer the file exactly (ready, and the file's lineage set up). 0 = it can, 1 = not within timeout_ms, <0 = error.
// The caller sleeps on the progress word; whoever changes one of the two conditions wakes it. Nobody else is held.
int vrs_wait(vrs_h* h, const char* path, uint64_t timeout_ms) {
  if (!h) return -1;
  Store& S = *h->S;
  const std::string cp = (path && *path) ? canon_path(S, path) : std::string();
  const auto end = std::chrono::steady_clock::now() + std::chrono::milliseconds(timeout_ms);
  for (;;) {
    const uint32_t seen = S.progress.load(std::memory_order_seq_cst);
    const int rd = S.ready.load(std::memory_order_seq_cst);
    if (rd < 0) return -2;
    if (rd == 1) {
      if (cp.empty()) return 0;
      Sess* ss = get_sess(S, cp, false);
      if (!ss) return 0;  // a file the store has not met: the assembly makes it
      if (ensure_segs(S, *ss, false) || !(ss->meta_pub.load(std::memory_order_acquire) && !ss->fpar.empty())) return 0;
    }
    const auto now = std::chrono::steady_clock::now();
    if (now >= end) return 1;
    const auto left = std::chrono::duration_cast<std::chrono::nanoseconds>(end - now).count();
    timespec ts{time_t(left / 1000000000), long(left % 1000000000)};
    syscall(SYS_futex, reinterpret_cast<uint32_t*>(&S.progress), FUTEX_WAIT_PRIVATE, seen, &ts, nullptr, 0);
  }
}
'''
s = rep(s, "int vrs_assemble_b(vrs_h* h, const char* path, uint64_t budget, char** json, size_t* len) {\n",
        wait_fn.lstrip("\n") + "int vrs_assemble_b(vrs_h* h, const char* path, uint64_t budget, char** json, size_t* len) {\n", "wait fn")

h = rep(h, "void vrs_free(char*);\n",
        "int  vrs_wait(vrs_h*, const char* path, uint64_t timeout_ms);  /* 6th stage: 0 = the store can answer `path` exactly (ready and its lineage set up; NULL path = ready), 1 = not within timeout_ms, <0 = error */\nvoid vrs_free(char*);\n",
        "header")

src.write_text(s, encoding="utf-8")
hdr.write_text(h, encoding="utf-8")
print("patched")
