#!/usr/bin/env python3
# makes vrs_t_live5.cpp from libsrc/vrs_t_live.cpp (stage 4 driver): adds ASMLOOP / ASMSTOP / STATS3 (T5-2, T5-5); nothing else changes
import re
s = open('$WORK/vrsint5/libsrc/vrs_t_live.cpp', encoding='utf-8').read()
s = s.replace('#include <atomic>\n', '#include <atomic>\n#include <mutex>\n', 1)
glob = '''
struct Loop { std::thread th; std::atomic<int> stop{0}; std::atomic<uint64_t> calls{0}, rc0{0}, rc1{0}, rcother{0}, maxus{0}; };
static Loop* LOOP = nullptr;
'''
s = s.replace('static vrs_dbg stats()', glob + 'static vrs_dbg stats()', 1)
cmds = '''    } else if (cmd == "ASMLOOP") {  // ASMLOOP <path> <ms>: a thread calls vrs_assemble on that file every <ms> ms until ASMSTOP
      std::string p; unsigned ms = 1; is >> p >> ms;
      if (LOOP) { std::printf("ERR loop running\\n"); std::fflush(stdout); continue; }
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
      std::printf("OK loop started\\n");
    } else if (cmd == "ASMSTOP") {
      if (!LOOP) { std::printf("ERR no loop\\n"); std::fflush(stdout); continue; }
      LOOP->stop.store(1); LOOP->th.join();
      std::printf("OK calls=%llu rc0=%llu rc1=%llu rcother=%llu maxus=%llu\\n", (unsigned long long)LOOP->calls.load(), (unsigned long long)LOOP->rc0.load(), (unsigned long long)LOOP->rc1.load(), (unsigned long long)LOOP->rcother.load(), (unsigned long long)LOOP->maxus.load());
      delete LOOP; LOOP = nullptr;
    } else if (cmd == "STATS3") {  // stage 5 counters
      const vrs_dbg d = stats();
      std::printf("OK late_events=%llu y_max=%llu x_max=%llu y_total=%llu x_total=%llu revisit_tasks=%llu obs_rebuilt=%llu a0_rebuilt=%llu pass_retries=%llu bad_lines=%llu dup_starts=%llu runs=%llu run_max=%llu theta_maxgroup=%llu theta_mismatch=%llu pend=%llu recounts=%llu count_retries=%llu lines_in=%llu\\n",
                  (unsigned long long)d.late_events, (unsigned long long)d.y_max, (unsigned long long)d.x_max, (unsigned long long)d.y_total, (unsigned long long)d.x_total, (unsigned long long)d.revisit_tasks,
                  (unsigned long long)d.obs_rebuilt, (unsigned long long)d.a0_rebuilt, (unsigned long long)d.pass_retries, (unsigned long long)d.bad_lines, (unsigned long long)d.dup_starts,
                  (unsigned long long)d.runs, (unsigned long long)d.run_max, (unsigned long long)d.theta_maxgroup, (unsigned long long)d.theta_mismatch, (unsigned long long)d.pend,
                  (unsigned long long)d.recounts, (unsigned long long)d.count_retries, (unsigned long long)d.lines_in);
'''
s = s.replace('    } else if (cmd == "HASH") {', cmds + '    } else if (cmd == "HASH") {', 1)
open('$WORK/vrsint5/vrs_t_live5.cpp', 'w', encoding='utf-8').write(s)
