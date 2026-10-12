#!/usr/bin/env python3
# makes vrs_t_insert5.cpp from libsrc/vrs_t_insert.cpp for stage 5.
#  - shard magic VX05
#  - T5-3 (idem), fixed before the run: the record set of the double-insert shard equals the single-insert shard with EVERY record type (items, meta, ts, turns, contributions)
#    except the R_WM marks (type 6); the cells hash and the assembled answer of the double run equal the single run's (bytes).
s = open('$WORK/vrsint5/libsrc/vrs_t_insert.cpp', encoding='utf-8').read()

def rep(a, b):
    global s
    assert s.count(a) == 1, (s.count(a), a[:70])
    s = s.replace(a, b)

rep('magic != 0x32305856u', 'magic != 0x35305856u')
# contributions are part of the record set now (only R_WM, type 6, is left out)
rep('''static std::vector<std::string> frame_set(const std::string& shard, bool with_contrib) {''', '''static std::vector<std::string> frame_set(const std::string& shard, bool with_contrib) {  // stage 5: with_contrib = false leaves out types 5 and 7; type 6 (R_WM) is always left out''')
# assembled answer
rep('''  void close() { if (h) vrs_close(h); h = nullptr; }''', '''  std::string asmb(const std::string& p, int* rc_out = nullptr) {
    char* j = nullptr; size_t n = 0; const int rc = vrs_assemble(h, p.c_str(), &j, &n);
    std::string o = j ? std::string(j, n) : std::string(); vrs_free(j);
    // the "us" field is the time of the call
    const size_t u = o.rfind(",\\"us\\":"); if (u != std::string::npos) o.resize(u);
    if (rc_out) *rc_out = rc; return o;
  }
  void close() { if (h) vrs_close(h); h = nullptr; }''')
rep('''  struct Res { vrs_dbg d; uint64_t hash; std::string shard; };''', '''  struct Res { vrs_dbg d; uint64_t hash; std::string shard; std::string ans; };''')
rep('''    Res r{lib.stats(), lib.hash(path), slurp(rel_shard(idir, sdir, path))};
    if (second_pass) {''', '''    Res r{lib.stats(), lib.hash(path), slurp(rel_shard(idir, sdir, path)), lib.asmb(path)};
    if (second_pass) {''')
rep('''      Res r2{lib.stats(), lib.hash(path), slurp(rel_shard(idir, sdir, path))};''', '''      Res r2{lib.stats(), lib.hash(path), slurp(rel_shard(idir, sdir, path)), lib.asmb(path)};
      check(r2.ans == r.ans && !r.ans.empty(), tag + ": second pass: assembled answer unchanged (" + std::to_string(r.ans.size()) + " bytes)");''')
rep('''  check(frame_set(a.shard, false) == frame_set(b.shard, false), "each line inserted twice in a row: the shard holds the same records as with a single insert (" + std::to_string(frame_set(b.shard, false).size()) + " records, marks left out)");''', '''  check(frame_set(a.shard, true) == frame_set(b.shard, true), "T5-3: each line inserted twice in a row: the shard holds the same records (all types, R_WM left out) as with a single insert (" + std::to_string(frame_set(b.shard, true).size()) + " records)");
  check(a.d.cells_hash == b.d.cells_hash && a.d.cells_n == b.d.cells_n, "T5-3: each line inserted twice in a row: the cells (hash, count) equal the single insert's");
  check(a.ans == b.ans && !a.ans.empty(), "T5-3: each line inserted twice in a row: the assembled answer equals the single insert's byte for byte (" + std::to_string(a.ans.size()) + " bytes)");''')
rep('''  check(frame_set(rel_shard(i3, sdir, path), false) == frame_set(rel_shard(work + "/a_single/i", sdir, path), false), "c: item / meta / task_started / turn records: same multiset as the insert-built shard");''', '''  check(frame_set(rel_shard(i3, sdir, path), false) == frame_set(rel_shard(work + "/a_single/i", sdir, path), false), "c: item / meta / task_started / turn records: same multiset as the insert-built shard");
  check(d3.cells_hash == a.d.cells_hash, "c: cells from a parse from scratch == insert-built cells");''')
open('$WORK/vrsint5/vrs_t_insert5.cpp', 'w', encoding='utf-8').write(s)

# the stage-4 check compared frame_set(a.shard) where a.shard is the CONTENT of the shard, while frame_set reads a path: both sides were empty (vacuous). Parse the content.
s = open('$WORK/vrsint5/vrs_t_insert5.cpp', encoding='utf-8').read()
s = s.replace('''static std::vector<Frame> read_frames(const std::string& shard) {
  std::vector<Frame> out; const std::string b = slurp(shard);''', '''static std::vector<Frame> read_frames_buf(const std::string& b) {
  std::vector<Frame> out;''', 1)
s = s.replace('''// the records of a shard as a sorted multiset;''', '''static std::vector<Frame> read_frames(const std::string& shard) { return read_frames_buf(slurp(shard)); }
// the records of a shard as a sorted multiset;''', 1)
s = s.replace('''struct Lib {''', '''static std::vector<std::string> frame_set_buf(const std::string& content, bool with_contrib) {
  std::vector<std::string> v;
  for (auto& f : read_frames_buf(content)) if ((with_contrib || (f.type != 5 && f.type != 7)) && f.type != 6) v.push_back(std::string(1, (char)f.type) + f.pl);
  std::sort(v.begin(), v.end());
  return v;
}

struct Lib {''', 1)
s = s.replace('frame_set(a.shard, true) == frame_set(b.shard, true)', 'frame_set_buf(a.shard, true) == frame_set_buf(b.shard, true) && !frame_set_buf(a.shard, true).empty()')
s = s.replace('std::to_string(frame_set(b.shard, true).size())', 'std::to_string(frame_set_buf(b.shard, true).size())')
open('$WORK/vrsint5/vrs_t_insert5.cpp', 'w', encoding='utf-8').write(s)
