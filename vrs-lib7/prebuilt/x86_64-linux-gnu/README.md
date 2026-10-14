# Prebuilt libvrs (round 7) for x86_64 Linux

`libvrs.a` here is the exact library linked into the deployed build of this branch. You can build Codex with it without the SWEGCA C++ core sources, which are not part of this repository.

| | |
|---|---|
| Members | `vrs_lib.o` (from `../../vrs_lib.cpp`), `evidence_rules.o`, `sha256.o`, `strong_types.o` (SWEGCA C++ core) |
| Compiler | GCC 16.2.1 for every member. `vrs_lib.o` used `-O2 -std=c++20 -mcx16 -pthread -fPIC`; the archive carries no debug info |
| Built on | glibc 2.43, x86_64 |
| SHA-256 | see `SHA256SUMS` |

`codex-rs/vrs/build.rs` links this directory by default. To use another build, set `VRS_LIB_DIR` to the directory holding your `libvrs.a`.

The archive needs a C++ runtime (`libstdc++`) at least as new as the one it was built with. On an older distribution, the link step may report missing `GLIBCXX_*` symbols. If that happens, use a newer toolchain or build `libvrs.a` yourself.
