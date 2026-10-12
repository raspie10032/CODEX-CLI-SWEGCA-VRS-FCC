#!/usr/bin/env python3
"""Round 6, P-12 completed (T6-1 (c) failed: the watcher kept a link's spelling): every way a path enters the store is canonical,
links are not followed by the scans, the path-spelling stale rule (seeds were path hashes) is gone under D12."""
import pathlib
import sys

p = pathlib.Path(sys.argv[1]) / "vrs_lib.cpp"
s = p.read_text(encoding="utf-8")


def rep(old, new, label, count=1):
    global s
    n = s.count(old)
    if n != count:
        raise SystemExit(f"{label}: expected {count} match(es), found {n}")
    s = s.replace(old, new)


# canon_path: an existing file is its real path (a linked file too); otherwise the real path of its longest existing ancestor + the rest
rep("  const size_t sl = in.rfind('/');\n  if (sl == std::string::npos || sl == 0) return in;\n  size_t cut = sl;",
    "  if (char* r = ::realpath(in.c_str(), nullptr)) {  // the file exists: its one real path\n"
    "    std::string out(r);\n    std::free(r);\n    cache.emplace(in, out);\n    return out;\n  }\n"
    "  const size_t sl = in.rfind('/');\n  if (sl == std::string::npos || sl == 0) return in;\n  size_t cut = sl;",
    "canon exists")
rep("      if (cut == sl) cache.emplace(in, out);\n      return out;\n",
    "      return out;  // not cached: the file does not exist yet\n",
    "canon nocache")

# scan_new_dir: links are not followed (the target is met under its own name); files enter canonical
rep("    std::error_code e2;\n    if (it->is_directory(e2)) { addw(it->path().string()); continue; }  // the watch is in before the iterator lists the directory\n"
    "    if (!it->is_regular_file(e2) || it->path().extension() != \".jsonl\") continue;\n"
    "    Sess* ss = get_sess(S, it->path().string(), true);\n",
    "    std::error_code e2;\n    if (it->is_symlink(e2)) continue;  // P-12: a link is not a second name for the store\n"
    "    if (it->is_directory(e2)) { addw(it->path().string()); continue; }  // the watch is in before the iterator lists the directory\n"
    "    if (!it->is_regular_file(e2) || it->path().extension() != \".jsonl\") continue;\n"
    "    Sess* ss = get_sess(S, canon_path(S, it->path().c_str()), true);  // P-12\n",
    "scan_new_dir")
# watcher: a directory is watched under its real path (inotify gives one wd per inode: the last spelling would win)
rep("    const int wd = inotify_add_watch(fd, dir.c_str(), IN_MODIFY | IN_CLOSE_WRITE | IN_CREATE | IN_MOVED_TO);\n    if (wd >= 0) wd2dir[wd] = dir;\n",
    "    std::string real = dir;\n    if (char* r = ::realpath(dir.c_str(), nullptr)) { real = r; std::free(r); }  // P-12\n"
    "    const int wd = inotify_add_watch(fd, real.c_str(), IN_MODIFY | IN_CLOSE_WRITE | IN_CREATE | IN_MOVED_TO);\n    if (wd >= 0) wd2dir[wd] = real;\n",
    "addw")
rep("      std::error_code e2;\n      if (it->is_directory(e2)) addw(it->path().string());\n",
    "      std::error_code e2;\n      if (it->is_symlink(e2)) continue;  // P-12\n      if (it->is_directory(e2)) addw(it->path().string());\n",
    "watch scan")
rep("      Sess* ss = get_sess(S, path, true);\n      if (!ss) continue;\n      ask_ingest(S, *ss);\n",
    "      Sess* ss = get_sess(S, canon_path(S, path.c_str()), true);  // P-12\n      if (!ss) continue;\n      ask_ingest(S, *ss);\n",
    "watch event")
# open scan: links skipped (each file once, under its real name)
rep("      std::error_code e2;\n      if (it->is_regular_file(e2) && it->path().extension() == \".jsonl\") files.push_back(it->path());\n",
    "      std::error_code e2;\n      if (it->is_symlink(e2)) continue;  // P-12: a link is not a second name for the store\n"
    "      if (it->is_regular_file(e2) && it->path().extension() == \".jsonl\") files.push_back(it->path());\n",
    "open scan")
# D12: seeds no longer depend on the spelling of the root, so a root spelled or placed differently keeps its shards
rep("      S.stale_index = !old.empty();\n",
    "      S.stale_index = false;  // 6th stage D12: the seeds are the file ids, not path hashes; a moved or respelled root keeps its shards\n",
    "stale")
# debug APIs
rep("  Sess* ss = get_sess(S, path, false);\n  if (!ss) return -2;\n", "  Sess* ss = get_sess(S, canon_path(S, path), false);  // P-12\n  if (!ss) return -2;\n", "dbg apis", 3)
p.write_text(s, encoding="utf-8")
print("patched d")
