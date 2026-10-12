// vrs_t_live: a libvrs process driven line by line over stdin by live_cmp.py (new sessions that grow while both the library and the original 42f run).
//   OPEN <sessions_dir> <index_dir>           open and wait until ready          -> OK ready_ms=..
//   APPEND <insert|watch> <src> <dst> <l0> <l1>  lines [l0,l1) of <src> appended to <dst>; insert = write then vrs_insert per line, watch = one write, the watcher finds it
//                                              -> OK applied=N (waits until lines_applied grew by the number of lines, 10 s at most)
//   ASM <path> <out file>                      vrs_assemble -> OK rc=.. bytes=..
//   STATS                                      -> OK items=.. turns=.. sessions=.. lines_applied=.. cells_hash=..
//   HASH <path>                                -> OK <session hash>
//   CLOSE | QUIT
#include "vrs.h"
#include <atomic>
#include <mutex>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fcntl.h>
#include <filesystem>
#include <fstream>
#include <algorithm>
#include <iostream>
#include <map>
#include <random>
#include <sstream>
#include <string>
#include <sys/stat.h>
#include <thread>
#include <unistd.h>
#include <vector>

namespace fs = std::filesystem;
static vrs_h* H = nullptr;
struct Pend { uint64_t off; std::string line; };
static std::map<std::string, std::vector<Pend>> PEND;   // RESERVE: lines handed to vrs_insert whose bytes are not in the file yet
static std::map<std::string, uint64_t> NEXTOFF;          // next reserved offset per file
static void pwrite_all(int fd, const std::string& s, uint64_t off) { size_t w = 0; while (w < s.size()) { ssize_t k = ::pwrite(fd, s.data() + w, s.size() - w, (off_t)(off + w)); if (k <= 0) return; w += (size_t)k; } }

struct Loop { std::thread th; std::atomic<int> stop{0}; std::atomic<uint64_t> calls{0}, rc0{0}, rc1{0}, rcother{0}, maxus{0}; };
static Loop* LOOP = nullptr;
static vrs_dbg stats() { vrs_dbg d; vrs_dbg_stats(H, &d); return d; }
static void put(int fd, const std::string& s) { size_t w = 0; while (w < s.size()) { ssize_t k = ::write(fd, s.data() + w, s.size() - w); if (k <= 0) return; w += (size_t)k; } }

int main() {
  std::string ln;
  while (std::getline(std::cin, ln)) {
    std::istringstream is(ln); std::string cmd; is >> cmd;
    if (cmd == "OPEN") {
      std::string sdir, idir; is >> sdir >> idir;
      const auto t0 = std::chrono::steady_clock::now();
      vrs_opts o{}; o.sessions_dir = sdir.c_str(); o.index_dir = idir.c_str(); o.segwin = 1; o.budget = 258400;
      if (vrs_open(&o, &H) != 0) { std::printf("ERR open\n"); std::fflush(stdout); continue; }
      while (vrs_ready(H) == 0) std::this_thread::sleep_for(std::chrono::milliseconds(1));
      std::printf("OK ready=%d ready_ms=%.1f\n", vrs_ready(H), std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t0).count());
    } else if (cmd == "APPEND") {
      std::string mode, src, dst; size_t l0, l1; is >> mode >> src >> dst >> l0 >> l1; std::string flag; is >> flag;
      std::ifstream in(src, std::ios::binary); std::vector<std::string> L; std::string l;
      while (std::getline(in, l)) L.push_back(l);
      if (l1 > L.size()) l1 = L.size();
      fs::create_directories(fs::path(dst).parent_path());
      const uint64_t base = stats().lines_applied;
      const int fd = ::open(dst.c_str(), O_WRONLY | O_APPEND | O_CREAT, 0644);
      off_t off = ::lseek(fd, 0, SEEK_END);
      if (mode == "held") {  // the lines are handed over first, all but the first one first (they wait beyond a gap), the file is written afterwards
        std::vector<uint64_t> offs; uint64_t o = (uint64_t)off; for (size_t i = l0; i < l1; i++) { offs.push_back(o); o += L[i].size() + 1; }
        for (size_t i = l0 + 1; i < l1; i++) vrs_insert(H, dst.c_str(), offs[i - l0], L[i].data(), L[i].size());
        if (l1 > l0) vrs_insert(H, dst.c_str(), offs[0], L[l0].data(), L[l0].size());
        std::string all; for (size_t i = l0; i < l1; i++) all += L[i] + "\n";
        put(fd, all);
        for (size_t i = l0; i < l1; i++) vrs_written(H, dst.c_str(), offs[i - l0]);
      } else if (mode == "swap") {  // the new bytes are made visible at once: old content + lines in a temporary name, renamed over the file (the watcher meets IN_MOVED_TO)
        std::string cur; { std::ifstream f(dst, std::ios::binary); cur.assign((std::istreambuf_iterator<char>(f)), std::istreambuf_iterator<char>()); }
        for (size_t i = l0; i < l1; i++) cur += L[i] + "\n";
        const std::string tmp = dst + ".tmp";
        { const int tf = ::open(tmp.c_str(), O_WRONLY | O_CREAT | O_TRUNC, 0644); put(tf, cur); ::close(tf); }
        ::rename(tmp.c_str(), dst.c_str());
      } else if (mode == "insert") {
        for (size_t i = l0; i < l1; i++) { put(fd, L[i] + "\n"); vrs_insert(H, dst.c_str(), (uint64_t)off, L[i].data(), L[i].size()); vrs_written(H, dst.c_str(), (uint64_t)off); off += (off_t)L[i].size() + 1; }
      } else {
        std::string all; for (size_t i = l0; i < l1; i++) all += L[i] + "\n";
        put(fd, all);
      }
      ::close(fd);
      const uint64_t want = base + (l1 > l0 ? l1 - l0 : 0);
      int waited = 0;
      while ((stats().lines_applied < want || (stats().pend != 0 && flag != "nopend")) && waited < 10000) { std::this_thread::sleep_for(std::chrono::milliseconds(1)); waited++; }  // lines in, and every closed turn counted
      std::printf("%s applied=%llu want=%llu waited_ms=%d\n", stats().lines_applied >= want ? "OK" : "TIMEOUT", (unsigned long long)(stats().lines_applied - base), (unsigned long long)(want - base), waited);
    } else if (cmd == "RESERVE") {  // RESERVE <src> <dst> <l0> <l1> <seed>: record time. The file exists (empty or short), nothing of these lines is written; every line is handed to vrs_insert at its reserved offset (seed 0: in order, else shuffled)
      std::string src, dst, fl; size_t l0, l1; unsigned seed; is >> src >> dst >> l0 >> l1 >> seed >> fl;  // fl = noinsert: only reserve (a file written by another process)
      std::ifstream in(src, std::ios::binary); std::vector<std::string> L; std::string l;
      while (std::getline(in, l)) L.push_back(l);
      if (l1 > L.size()) l1 = L.size();
      fs::create_directories(fs::path(dst).parent_path());
      { const int fd = ::open(dst.c_str(), O_WRONLY | O_APPEND | O_CREAT, 0644); if (fd >= 0) ::close(fd); }
      if (!NEXTOFF.count(dst)) { struct stat st; NEXTOFF[dst] = ::stat(dst.c_str(), &st) == 0 ? (uint64_t)st.st_size : 0; }
      std::vector<Pend> v; uint64_t o = NEXTOFF[dst];
      for (size_t i = l0; i < l1; i++) { v.push_back(Pend{o, L[i]}); o += L[i].size() + 1; }
      NEXTOFF[dst] = o;
      std::vector<size_t> ord(v.size()); for (size_t i = 0; i < ord.size(); i++) ord[i] = i;
      if (seed) { std::mt19937 g(seed); std::shuffle(ord.begin(), ord.end(), g); }
      int bad = 0;
      const auto t0 = std::chrono::steady_clock::now();
      for (size_t i : ord) if (fl != "noinsert" && vrs_insert(H, dst.c_str(), v[i].off, v[i].line.data(), v[i].line.size()) != 0) bad++;
      const double us = std::chrono::duration<double, std::micro>(std::chrono::steady_clock::now() - t0).count();
      for (auto& x : v) PEND[dst].push_back(std::move(x));
      const vrs_dbg d = stats();
      std::printf("OK reserved=%zu bad=%d next=%llu us_per_insert=%.1f pend=%llu uw_lines=%llu insert_left=%llu insert_waits=%llu\n", v.size(), bad, (unsigned long long)o, ord.empty() ? 0.0 : us / (double)ord.size(), (unsigned long long)d.pend, (unsigned long long)d.uw_lines, (unsigned long long)d.insert_left, (unsigned long long)d.insert_waits);
    } else if (cmd == "CONC") {  // CONC <threads per file> <seed> <src1> <dst1> [<src2> <dst2> ...]: several threads insert the lines of one file at once (all files at once), each line: vrs_insert at its reserved offset, pwrite, vrs_written
      unsigned nt = 0, seed = 0; is >> nt >> seed;
      struct F { std::vector<Pend> v; std::string dst; int fd = -1; };
      std::vector<F> files; std::string s1, d1;
      while (is >> s1 >> d1) {
        F f; f.dst = d1;
        std::ifstream in(s1, std::ios::binary); std::string l; uint64_t o = 0;
        fs::create_directories(fs::path(d1).parent_path());
        { const int fd = ::open(d1.c_str(), O_WRONLY | O_APPEND | O_CREAT, 0644); if (fd >= 0) ::close(fd); }
        struct stat st; if (::stat(d1.c_str(), &st) == 0) o = (uint64_t)st.st_size;
        while (std::getline(in, l)) { f.v.push_back(Pend{o, l}); o += l.size() + 1; }
        f.fd = ::open(d1.c_str(), O_WRONLY | O_CREAT, 0644);
        files.push_back(std::move(f));
      }
      const vrs_dbg d0 = stats();
      std::atomic<int> go{0}, bad{0}; std::atomic<uint64_t> calls{0}, maxus{0};
      std::vector<std::vector<uint32_t>> lat(files.size() * nt);
      std::vector<std::thread> th;
      for (size_t fi = 0; fi < files.size(); fi++) {
        std::vector<size_t> ord(files[fi].v.size()); for (size_t i = 0; i < ord.size(); i++) ord[i] = i;
        if (seed) { std::mt19937 g(seed + (unsigned)fi); std::shuffle(ord.begin(), ord.end(), g); }
        for (unsigned t = 0; t < nt; t++) th.emplace_back([&, fi, t, ord]() {
          std::vector<uint32_t>& my = lat[fi * nt + t];
          while (!go.load()) {}
          F& f = files[fi];
          for (size_t k = t; k < ord.size(); k += nt) {
            Pend& p = f.v[ord[k]];
            const auto a = std::chrono::steady_clock::now();
            if (vrs_insert(H, f.dst.c_str(), p.off, p.line.data(), p.line.size()) != 0) bad++;
            const uint64_t us = (uint64_t)std::chrono::duration<double, std::micro>(std::chrono::steady_clock::now() - a).count();
            uint64_t m = maxus.load(); while (us > m && !maxus.compare_exchange_weak(m, us)) {}
            my.push_back((uint32_t)us);
            calls++;
            pwrite_all(f.fd, p.line + "\n", p.off);
            if (vrs_written(H, f.dst.c_str(), p.off) != 0) bad++;
          }
        });
      }
      const auto t0 = std::chrono::steady_clock::now();
      go.store(1);
      for (auto& x : th) x.join();
      const double ms = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t0).count();
      for (auto& f : files) if (f.fd >= 0) ::close(f.fd);
      std::vector<uint32_t> all; for (auto& v : lat) all.insert(all.end(), v.begin(), v.end());
      std::sort(all.begin(), all.end());
      const vrs_dbg d1_ = stats();
      std::printf("OK threads=%zu calls=%llu bad=%d wall_ms=%.1f p50_insert_us=%u p99_insert_us=%u max_insert_us=%llu insert_left=%llu insert_waits=%llu\n", th.size(), (unsigned long long)calls.load(), bad.load(), ms,
                  all.empty() ? 0u : all[all.size() / 2], all.empty() ? 0u : all[all.size() * 99 / 100], (unsigned long long)maxus.load(), (unsigned long long)(d1_.insert_left - d0.insert_left), (unsigned long long)(d1_.insert_waits - d0.insert_waits));
    } else if (cmd == "FLUSHW") {  // FLUSHW <dst> <seed> <count>: write that many of the reserved lines with pwrite (shuffled by seed, 0 = in order), each followed by vrs_written
      std::string dst, fl; unsigned seed; size_t cnt; is >> dst >> seed >> cnt >> fl;  // fl = nowritten: do not call vrs_written
      auto& v = PEND[dst];
      std::vector<size_t> ord(v.size()); for (size_t i = 0; i < ord.size(); i++) ord[i] = i;
      if (seed) { std::mt19937 g(seed); std::shuffle(ord.begin(), ord.end(), g); }
      if (cnt > ord.size()) cnt = ord.size();
      const int fd = ::open(dst.c_str(), O_WRONLY | O_CREAT, 0644);
      int bad = 0; std::vector<char> gone(v.size(), 0);
      for (size_t k = 0; k < cnt; k++) { Pend& p = v[ord[k]]; pwrite_all(fd, p.line + "\n", p.off); if (fl != "nowritten" && vrs_written(H, dst.c_str(), p.off) != 0) bad++; gone[ord[k]] = 1; }
      ::close(fd);
      std::vector<Pend> keep; for (size_t i = 0; i < v.size(); i++) if (!gone[i]) keep.push_back(std::move(v[i]));
      v = std::move(keep);
      const vrs_dbg d = stats();
      std::printf("OK written=%zu rc_bad=%d left=%zu uw_lines=%llu uw_bytes=%llu\n", cnt, bad, v.size(), (unsigned long long)d.uw_lines, (unsigned long long)d.uw_bytes);
    } else if (cmd == "FLUSHX") {  // FLUSHX <dst> <i,j,..>: write every reserved line except those (indexes in the order reserved), vrs_written for each; the skipped ones stay unwritten (a crash hole)
      std::string dst, sk; is >> dst >> sk;
      std::vector<size_t> skip; { std::istringstream ss(sk); std::string t; while (std::getline(ss, t, ',')) if (!t.empty()) skip.push_back((size_t)std::stoul(t)); }
      auto& v = PEND[dst];
      const int fd = ::open(dst.c_str(), O_WRONLY | O_CREAT, 0644);
      int bad = 0; std::vector<Pend> keep;
      for (size_t i = 0; i < v.size(); i++) {
        if (std::find(skip.begin(), skip.end(), i) != skip.end()) { keep.push_back(std::move(v[i])); continue; }
        pwrite_all(fd, v[i].line + "\n", v[i].off); if (vrs_written(H, dst.c_str(), v[i].off) != 0) bad++;
      }
      ::close(fd); v = std::move(keep);
      std::printf("OK rc_bad=%d left=%zu\n", bad, v.size());
    } else if (cmd == "WRITTEN") {  // WRITTEN <path> <off>: vrs_written alone, prints its return code
      std::string p; unsigned long long o; is >> p >> o;
      std::printf("OK rc=%d\n", vrs_written(H, p.c_str(), (uint64_t)o));
    } else if (cmd == "TOUCH") {
      std::string p; is >> p; fs::create_directories(fs::path(p).parent_path());
      const int fd = ::open(p.c_str(), O_WRONLY | O_APPEND | O_CREAT, 0644); if (fd >= 0) ::close(fd);
      std::printf("OK touched\n");
    } else if (cmd == "ASM") {
      std::string p, out; is >> p >> out;
      char* j = nullptr; size_t n = 0;
      const int rc = vrs_assemble(H, p.c_str(), &j, &n);
      if (j && !out.empty()) { std::ofstream o(out, std::ios::binary | std::ios::trunc); o.write(j, (std::streamsize)n); }
      vrs_free(j);
      std::printf("OK rc=%d bytes=%zu\n", rc, n);
    } else if (cmd == "STATS") {
      const vrs_dbg d = stats();
      std::printf("OK items=%llu turns=%llu sessions=%llu lines_applied=%llu tail_lines=%llu restored_items=%llu shards_loaded=%llu shards_rebuilt=%llu lemma_e=%llu cells_hash=%016llx uw_lines=%llu uw_bytes=%llu uw_added=%llu uw_released=%llu uw_unknown=%llu holes_skipped=%llu nul_stops=%llu insert_left=%llu insert_waits=%llu pend=%llu\n",
                  (unsigned long long)d.items, (unsigned long long)d.turns, (unsigned long long)d.sessions, (unsigned long long)d.lines_applied, (unsigned long long)d.tail_lines,
                  (unsigned long long)d.restored_items, (unsigned long long)d.shards_loaded, (unsigned long long)d.shards_rebuilt, (unsigned long long)d.lemma_e, (unsigned long long)d.cells_hash,
                  (unsigned long long)d.uw_lines, (unsigned long long)d.uw_bytes, (unsigned long long)d.uw_added, (unsigned long long)d.uw_released, (unsigned long long)d.uw_unknown,
                  (unsigned long long)d.holes_skipped, (unsigned long long)d.nul_stops, (unsigned long long)d.insert_left, (unsigned long long)d.insert_waits, (unsigned long long)d.pend);
    } else if (cmd == "STATS2") {  // P-8
      const vrs_dbg d = stats();
      std::printf("OK late_events=%llu sweep_left=%llu reval_checked=%llu recounts=%llu count_retries=%llu ctr_n=%llu ctr_bytes=%llu obs_rebuilt=%llu a0_rebuilt=%llu retired_n=%llu retired_bytes=%llu freed_n=%llu settle_ok=%llu settle_bad=%llu insert_waits=%llu pend=%llu\n",
                  (unsigned long long)d.late_events, (unsigned long long)d.sweep_left, (unsigned long long)d.reval_checked, (unsigned long long)d.recounts, (unsigned long long)d.count_retries,
                  (unsigned long long)d.ctr_n, (unsigned long long)d.ctr_bytes, (unsigned long long)d.obs_rebuilt, (unsigned long long)d.a0_rebuilt, (unsigned long long)d.retired_n,
                  (unsigned long long)d.retired_bytes, (unsigned long long)d.freed_n, (unsigned long long)d.settle_ok, (unsigned long long)d.settle_bad, (unsigned long long)d.insert_waits, (unsigned long long)d.pend);
    } else if (cmd == "ASMLOOP") {  // ASMLOOP <path> <ms>: a thread calls vrs_assemble on that file every <ms> ms until ASMSTOP
      std::string p; unsigned ms = 1; is >> p >> ms;
      if (LOOP) { std::printf("ERR loop running\n"); std::fflush(stdout); continue; }
      LOOP = new Loop;
      LOOP->th = std::thread([p, ms]() {
        while (!LOOP->stop.load()) {
          char* j = nullptr; size_t n = 0;
          const auto a = std::chrono::steady_clock::now();
          const int rc = vrs_assemble(H, p.c_str(), &j, &n);
          const uint64_t us = (uint64_t)std::chrono::duration<double, std::micro>(std::chrono::steady_clock::now() - a).count();
          vrs_free(j);
          LOOP->calls++;
          if (rc == 0) LOOP->rc0++; else if (rc == 1) LOOP->rc1++; else LOOP->rcother++;
          uint64_t m = LOOP->maxus.load(); while (us > m && !LOOP->maxus.compare_exchange_weak(m, us)) {}
          std::this_thread::sleep_for(std::chrono::milliseconds(ms));
        }
      });
      std::printf("OK loop started\n");
    } else if (cmd == "ASMSTOP") {
      if (!LOOP) { std::printf("ERR no loop\n"); std::fflush(stdout); continue; }
      LOOP->stop.store(1); LOOP->th.join();
      std::printf("OK calls=%llu rc0=%llu rc1=%llu rcother=%llu maxus=%llu\n", (unsigned long long)LOOP->calls.load(), (unsigned long long)LOOP->rc0.load(), (unsigned long long)LOOP->rc1.load(), (unsigned long long)LOOP->rcother.load(), (unsigned long long)LOOP->maxus.load());
      delete LOOP; LOOP = nullptr;
    } else if (cmd == "STATS3") {  // stage 5 counters
      const vrs_dbg d = stats();
      std::printf("OK late_events=%llu y_max=%llu x_max=%llu y_total=%llu x_total=%llu revisit_tasks=%llu obs_rebuilt=%llu a0_rebuilt=%llu pass_retries=%llu bad_lines=%llu dup_starts=%llu runs=%llu run_max=%llu theta_maxgroup=%llu theta_mismatch=%llu pend=%llu recounts=%llu count_retries=%llu lines_in=%llu\n",
                  (unsigned long long)d.late_events, (unsigned long long)d.y_max, (unsigned long long)d.x_max, (unsigned long long)d.y_total, (unsigned long long)d.x_total, (unsigned long long)d.revisit_tasks,
                  (unsigned long long)d.obs_rebuilt, (unsigned long long)d.a0_rebuilt, (unsigned long long)d.pass_retries, (unsigned long long)d.bad_lines, (unsigned long long)d.dup_starts,
                  (unsigned long long)d.runs, (unsigned long long)d.run_max, (unsigned long long)d.theta_maxgroup, (unsigned long long)d.theta_mismatch, (unsigned long long)d.pend,
                  (unsigned long long)d.recounts, (unsigned long long)d.count_retries, (unsigned long long)d.lines_in);
    } else if (cmd == "HASH") {
      std::string p; is >> p; uint64_t x = 0; const int rc = vrs_dbg_session_hash(H, p.c_str(), &x);
      std::printf("OK rc=%d %016llx\n", rc, (unsigned long long)x);
    } else if (cmd == "BSTAT") {
      uint64_t d = 0, m = 0, t = 0; const int rc = vrs_dbg_border_stat(H, &d, &m, &t);
      std::printf("OK rc=%d days=%llu max_bucket=%llu turns=%llu\n", rc, (unsigned long long)d, (unsigned long long)m, (unsigned long long)t);
    } else if (cmd == "CELLS") {
      std::string f; is >> f; std::printf("OK rc=%d\n", vrs_dbg_dump_cells(H, f.c_str()));
    } else if (cmd == "OBSDUMP") {
      std::string p, f; is >> p >> f; std::printf("OK rc=%d\n", vrs_dbg_obs_dump(H, p.c_str(), f.c_str()));
    } else if (cmd == "UNITDUMP") {
      std::string f; is >> f; std::printf("OK rc=%d\n", vrs_dbg_unit_dump(H, f.c_str()));
    } else if (cmd == "OHASH") {
      std::string p; is >> p; uint64_t x = 0; const int rc = vrs_dbg_obs_hash(H, p.c_str(), &x);
      std::printf("OK rc=%d %016llx\n", rc, (unsigned long long)x);
    } else if (cmd == "CLOSE") {
      if (H) vrs_close(H); H = nullptr; std::printf("OK closed\n");
    } else if (cmd == "QUIT") {
      if (H) vrs_close(H); H = nullptr; std::printf("OK bye\n"); std::fflush(stdout); return 0;
    } else {
      std::printf("ERR unknown %s\n", cmd.c_str());
    }
    std::fflush(stdout);
  }
  if (H) vrs_close(H);
  return 0;
}
