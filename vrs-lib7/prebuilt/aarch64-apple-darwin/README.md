# Prebuilt libvrs (round 7) for Apple Silicon macOS

This archive links the same round-7 assembler and SWEGCA core used by the Linux
release, with native macOS file events and wait/wake operations.

Rebuilt on 2026-10-20 with FCC 1.1.2's sender-route relay detection and VX07
index format. The three SWEGCA core source files are unchanged from the first
macOS preview; `vrs_lib.o` includes the upstream 1.1.2 changes and Darwin adapter.

- Target: `aarch64-apple-darwin`; requires macOS 14.4 or newer.
- Compiler: Apple clang 21.0.0, `-O2 -std=c++20 -mmacosx-version-min=14.4 -pthread -fPIC`.
- Members: `vrs_lib.o`, `evidence_rules.o`, `sha256.o`, `strong_types.o`.
- Link dependencies: libc++, CoreServices, CoreFoundation and the system C library.
- Integrity: see `SHA256SUMS`.

The SWEGCA core source is not included in this repository, matching the Linux
prebuilt distribution. `build-macos.sh` can rebuild the archive when that source
is available. A Codex build uses the checked-in archive by default and does not
need those private sources. `VRS_LIB_DIR` can select another compatible archive.

The macOS adapter uses FSEvents for recursive creation, append and rename events,
and Darwin's `os_sync_wait_on_address_with_timeout` for readiness waits. Dropped
file event batches trigger a rescan. Watcher startup failure or root replacement
is an error. The assembly algorithm and its over-budget error are unchanged.
