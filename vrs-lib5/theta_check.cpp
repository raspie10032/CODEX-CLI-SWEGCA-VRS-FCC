// theta_check: T-int-1 on a whole corpus, independent of libvrs.
//   theta_check <sessions dir> [threads]
// For every .jsonl file (same discovery as 42f: recursive, extension .jsonl), every line (std::getline semantics: split at '\n', a last
// line without '\n' counts) it computes
//   chain : 42f's theta' = max(ts, previous theta' + 1)   (load(): lth <= last -> last + 1; chain over ALL lines, items or not)
//   D2    : theta* = ts + r, r = |{earlier lines of the same file with the same ts}|   (counted in a hash map: no adjacency assumed)
// and reports lines compared, mismatches (theta* != theta'), lines whose ts is below the largest ts seen before them in the file,
// the largest same-ts group, and groups larger than 1047 (the bound the proof of T-int-1 needs).
// ts is parse_ts of the first "timestamp":"..." value, copied from vrs9syn42f.cpp.
#include <algorithm>
#include <atomic>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <string>
#include <thread>
#include <unordered_map>
#include <vector>
#include <fcntl.h>
#include <unistd.h>

namespace fs = std::filesystem;
constexpr uint64_t TH_SEC = 1ull << 20;

std::string sval(const std::string& s, const char* key, size_t from = 0) {
  std::string pat = std::string("\"") + key + "\":\"";
  size_t p = s.find(pat, from);
  if (p == std::string::npos) return "";
  p += pat.size();
  size_t q = p;
  while (q < s.size() && !(s[q] == '"' && s[q - 1] != '\\')) q++;
  return s.substr(p, q - p);
}
int64_t days_from_civil(int64_t y, unsigned m, unsigned d) {
  y -= m <= 2;
  const int64_t era = (y >= 0 ? y : y - 399) / 400;
  const unsigned yoe = (unsigned)(y - era * 400);
  const unsigned doy = (153 * (m + (m > 2 ? -3 : 9)) + 2) / 5 + d - 1;
  const unsigned doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
  return era * 146097 + (int64_t)doe - 719468;
}
uint64_t parse_ts(const std::string& t) {
  if (t.size() < 19) return 0;
  int64_t Y = atoi(t.substr(0, 4).c_str()), M = atoi(t.substr(5, 2).c_str()), D = atoi(t.substr(8, 2).c_str());
  int64_t h = atoi(t.substr(11, 2).c_str()), mi = atoi(t.substr(14, 2).c_str()), se = atoi(t.substr(17, 2).c_str());
  int64_t ms = 0;
  if (t.size() > 20 && t[19] == '.') { std::string f = t.substr(20, 3); while (f.size() < 3) f += '0'; ms = atoi(f.c_str()); }
  int64_t sec = days_from_civil(Y, (unsigned)M, (unsigned)D) * 86400 + h * 3600 + mi * 60 + se;
  return (uint64_t)sec * TH_SEC + (uint64_t)ms * TH_SEC / 1000;
}

struct Tot {
  std::atomic<uint64_t> files{0}, lines{0}, mismatch{0}, decreasing{0}, maxgroup{0}, big_groups{0}, ts_zero{0}, unterminated{0};
};

void do_file(const fs::path& p, Tot& T) {
  const int fd = ::open(p.c_str(), O_RDONLY);
  if (fd < 0) { std::fprintf(stderr, "cannot open %s\n", p.c_str()); return; }
  std::unordered_map<uint64_t, uint32_t> cnt;
  uint64_t last = 0, maxts = 0, lines = 0, mism = 0, dec = 0, zero = 0, maxg = 0, big = 0;
  bool unterminated = false;
  auto one = [&](const std::string& line) {
    const uint64_t ts = parse_ts(sval(line, "timestamp"));
    uint64_t chain = ts;
    if (chain <= last) chain = last + 1;
    last = chain;
    if (ts == 0) zero++;
    if (ts < maxts) dec++;
    maxts = std::max(maxts, ts);
    const uint64_t r = cnt[ts]++;
    maxg = std::max<uint64_t>(maxg, r + 1);
    if (r + 1 == 1049) big++;  // counted once per group that exceeds 1048 lines
    if (ts + r != chain) mism++;
    lines++;
  };
  std::string buf; size_t start = 0, scan = 0;
  const size_t CH = size_t(1) << 24;
  for (;;) {
    const size_t old = buf.size();
    buf.resize(old + CH);
    const ssize_t got = ::read(fd, &buf[old], CH);
    if (got <= 0) { buf.resize(old); break; }
    buf.resize(old + (size_t)got);
    for (;;) {
      const size_t nl = buf.find('\n', std::max(scan, start));
      if (nl == std::string::npos) { scan = buf.size(); break; }
      one(buf.substr(start, nl - start));
      start = nl + 1; scan = start;
    }
    buf.erase(0, start); scan -= start; start = 0;
  }
  if (!buf.empty()) { one(buf); unterminated = true; }  // getline returns a last line without '\n' too
  ::close(fd);
  T.files++; T.lines += lines; T.mismatch += mism; T.decreasing += dec; T.ts_zero += zero; T.big_groups += big; T.unterminated += unterminated;
  uint64_t m = T.maxgroup.load();
  while (maxg > m && !T.maxgroup.compare_exchange_weak(m, maxg)) {}
  if (mism || dec) std::printf("file %s lines %llu mismatches %llu decreasing %llu\n", p.c_str(), (unsigned long long)lines, (unsigned long long)mism, (unsigned long long)dec);
}

int main(int argc, char** argv) {
  if (argc < 2) { std::fprintf(stderr, "usage: theta_check <sessions dir> [threads]\n"); return 2; }
  const unsigned nt = argc > 2 ? (unsigned)std::atoi(argv[2]) : 12;
  std::vector<fs::path> files;
  for (auto& e : fs::recursive_directory_iterator(argv[1])) if (e.is_regular_file() && e.path().extension() == ".jsonl") files.push_back(e.path());
  std::sort(files.begin(), files.end());
  Tot T; std::atomic<size_t> next{0};
  std::vector<std::thread> ws;
  for (unsigned w = 0; w < nt; w++) ws.emplace_back([&] { for (size_t i; (i = next.fetch_add(1)) < files.size();) do_file(files[i], T); });
  for (auto& t : ws) t.join();
  std::printf("theta_check %s: files %llu, lines compared %llu, mismatches (theta* != theta') %llu, lines with ts below an earlier ts %llu, "
              "largest same-ts group %llu, groups above 1048 lines %llu, lines with ts 0 %llu, files without final newline %llu\n",
              argv[1], (unsigned long long)T.files.load(), (unsigned long long)T.lines.load(), (unsigned long long)T.mismatch.load(),
              (unsigned long long)T.decreasing.load(), (unsigned long long)T.maxgroup.load(), (unsigned long long)T.big_groups.load(),
              (unsigned long long)T.ts_zero.load(), (unsigned long long)T.unterminated.load());
  return T.mismatch.load() || T.decreasing.load() || T.big_groups.load() ? 1 : 0;
}
