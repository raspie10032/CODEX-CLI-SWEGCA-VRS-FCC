# Prebuilt libvrs (round 7) for x86_64 Linux

`libvrs.a` here is round 7 of the VRS assembly library, the one linked into the deployed build of this branch. You can build Codex with it without the SWEGCA C++ core sources, which are not part of this repository.

| | |
|---|---|
| Members | `vrs_lib.o` (from `../../vrs_lib.cpp`), `evidence_rules.o`, `sha256.o`, `strong_types.o` (SWEGCA C++ core) |
| Compiler | GCC 14.2.0 (Ubuntu 24.04) for every member, all with `-O2 -std=c++20 -mcx16 -pthread -fPIC`; the archive carries no debug info |
| Built on | Ubuntu 24.04, glibc 2.39, x86_64 |
| Needs | glibc 2.38 or newer and a `libstdc++` from GCC 13 or newer; CI links it on Ubuntu 24.04 |
| SHA-256 | see `SHA256SUMS` |

On 2026-10-20 `vrs_lib.o` was rebuilt from the current `vrs_lib.cpp` with the same compiler and flags, and the other three members were kept as they were. The source change fixes how relayed messages are told apart from the user's own (they are now recognized by the sender's route label, so a user message that starts with a Markdown link is no longer taken for a relay) and moves the index format to `VX07`. An older index is rebuilt once from the session records the first time the new build opens it.

Until 2026-10-15 this directory held a GCC 16.2.1 build of the same source. That build needed GCC 16's `libstdc++` (`GLIBCXX_3.4.35`), so it did not link on Ubuntu 24.04. The two builds were run on the same 462 stored sessions, and every assembled request came out identical; only the timing field differs.

`codex-rs/vrs/build.rs` links this directory by default. To use another build, set `VRS_LIB_DIR` to the directory holding your `libvrs.a`.
