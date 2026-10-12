#!/usr/bin/env python3
"""Round 6, T6-2 hooks only in the debug build (-DVRS_DBG_HOOKS): hold ready (race injection), and ready < 0 imitation."""
import pathlib
import sys

p = pathlib.Path(sys.argv[1]) / "vrs_lib.cpp"
s = p.read_text(encoding="utf-8")


def rep(old, new, label):
    global s
    n = s.count(old)
    if n != 1:
        raise SystemExit(f"{label}: expected 1 match, found {n}")
    s = s.replace(old, new)


rep("    if (S.hold_ready.time_since_epoch().count() && std::chrono::steady_clock::now() < S.hold_ready) {  // T6-2 race injection: latch later\n"
    "      int a = 0;\n"
    "      if (S.hold_armed.compare_exchange_strong(a, 1)) std::thread([&S] { std::this_thread::sleep_until(S.hold_ready); maybe_ready(S); }).detach();\n"
    "      return;\n"
    "    }\n",
    "#ifdef VRS_DBG_HOOKS\n"
    "    if (S.dbg_fail_ready) { S.ready.store(-1, std::memory_order_seq_cst); bump_progress(S); return; }  // T6-2: the store failing\n"
    "    if (S.hold_ready.time_since_epoch().count() && std::chrono::steady_clock::now() < S.hold_ready) {  // T6-2 race injection: latch later\n"
    "      int a = 0;\n"
    "      if (S.hold_armed.compare_exchange_strong(a, 1)) std::thread([&S] { std::this_thread::sleep_until(S.hold_ready); maybe_ready(S); }).detach();\n"
    "      return;\n"
    "    }\n"
    "#endif\n",
    "maybe_ready hook")
rep("  std::atomic<int> hold_armed{0};\n",
    "  std::atomic<int> hold_armed{0};\n  bool dbg_fail_ready = false;  // test hook VRS_DBG_FAIL_READY (T6-2)\n",
    "field")
rep("  if (const char* hv = std::getenv(\"VRS_DBG_HOLD_READY_MS\")) S.hold_ready = std::chrono::steady_clock::now() + std::chrono::milliseconds(std::atoll(hv));  // T6-2 only\n",
    "#ifdef VRS_DBG_HOOKS\n"
    "  if (const char* hv = std::getenv(\"VRS_DBG_HOLD_READY_MS\")) S.hold_ready = std::chrono::steady_clock::now() + std::chrono::milliseconds(std::atoll(hv));  // T6-2 only\n"
    "  S.dbg_fail_ready = std::getenv(\"VRS_DBG_FAIL_READY\") != nullptr;\n"
    "#endif\n",
    "open hook")
p.write_text(s, encoding="utf-8")
print("patched b")
