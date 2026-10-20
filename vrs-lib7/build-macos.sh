#!/bin/bash
# Build the native library from the original SWEGCA core sources.
# Usage: build-macos.sh <swegca_cpp directory> [output directory]
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
CORE=${1:?swegca_cpp source directory required}
OUT=${2:-"$HERE/prebuilt/aarch64-apple-darwin"}
mkdir -p "$OUT/obj"
CXX=${CXX:-clang++}
FLAGS=(-O2 -std=c++20 -mmacosx-version-min=14.4 -pthread -fPIC -Wall -Wno-unused-function -Wno-unused-variable -I "$CORE")
for unit in evidence_rules sha256 strong_types; do
  "$CXX" "${FLAGS[@]}" -c "$CORE/swegca_architecture/$unit.cpp" -o "$OUT/obj/$unit.o"
done
"$CXX" "${FLAGS[@]}" -c "$HERE/vrs_lib.cpp" -o "$OUT/obj/vrs_lib.o"
ar rcs "$OUT/libvrs.a" "$OUT/obj/vrs_lib.o" "$OUT/obj/evidence_rules.o" "$OUT/obj/sha256.o" "$OUT/obj/strong_types.o"
file "$OUT/obj/vrs_lib.o"
shasum -a 256 "$OUT/libvrs.a"
