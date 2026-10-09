#include "$WORK/vrsint/vrs.h"
#include <chrono>
#include <cstdio>
#include <filesystem>
#include <fstream>
#include <string>
#include <thread>
#include <unistd.h>
int main() {
  char tmpl[] = "/tmp/codex-vrs-deferred3-XXXXXX";
  const auto root = std::filesystem::path(mkdtemp(tmpl));
  const auto sessions = root / "sessions";
  std::filesystem::create_directory(sessions);
  const std::string dir = sessions.string();
  vrs_opts opts{}; opts.sessions_dir = dir.c_str(); opts.workers = 2;
  vrs_h* h = nullptr;
  const int opened = vrs_open(&opts, &h);
  if (opened != 0) return 10;
  const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(10);
  while (!vrs_ready(h) && std::chrono::steady_clock::now() < deadline)
    std::this_thread::sleep_for(std::chrono::milliseconds(1));
  if (vrs_ready(h) != 1) return 11;
  const std::string path = (sessions / "rollout-deferred.jsonl").string();
  const std::string line = "{\"timestamp\":\"2026-10-09T00:00:00.000Z\",\"ordinal\":0,\"type\":\"response_item\",\"payload\":{\"type\":\"message\",\"role\":\"user\",\"content\":[{\"type\":\"input_text\",\"text\":\"preserve this direct user message\"}]}}\n";
  const int inserted = vrs_insert(h, path.c_str(), 0, line.data(), line.size() - 1);
  { std::ofstream f(path, std::ios::binary); f << line; f.flush(); }
  const int written = vrs_written(h, path.c_str(), 0);
  std::printf("open=%d ready=%d insert=%d written=%d expected_written=0\n", opened, vrs_ready(h), inserted, written);
  vrs_close(h);
  std::filesystem::remove_all(root);
  return inserted == 0 && written == 0 ? 0 : 1;
}
