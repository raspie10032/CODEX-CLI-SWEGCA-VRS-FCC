#!/bin/bash
# Fetch the Codex-built rusty_v8 archive and binding that codex-code-mode-host links, the way
# .github/actions/setup-rusty-v8 does, and check them against the manifest checksums committed in
# third_party/v8. Prints the two variables to export before `cargo build -p codex-code-mode-host`.
# usage: fetch_rusty_v8.sh <repo root> <out dir>
set -euo pipefail
ROOT=$1
mkdir -p "$2"
OUT=$(cd "$2" && pwd)
TARGET=x86_64-unknown-linux-gnu
version=152.2.0
profile=ptrcomp_sandbox_release
base_url="https://github.com/openai/codex/releases/download/rusty-v8-v${version}"
archive_name="librusty_v8_${profile}_${TARGET}.a.gz"
binding_name="src_binding_${profile}_${TARGET}.rs"
checksums_name="rusty_v8_${profile}_${TARGET}.sha256"
trusted="${ROOT}/third_party/v8/rusty_v8_${version//./_}_release_manifests.sha256"
curl -fsSL "${base_url}/${checksums_name}" -o "$OUT/${checksums_name}"
expected=$(grep -F "  ${checksums_name}" "$trusted" | cut -d ' ' -f 1)
actual=$(sha256sum "$OUT/${checksums_name}" | cut -d ' ' -f 1)
if [ "$expected" != "$actual" ]; then
  echo "manifest checksum mismatch: expected $expected got $actual" >&2
  exit 1
fi
curl -fsSL "${base_url}/${archive_name}" -o "$OUT/${archive_name}"
curl -fsSL "${base_url}/${binding_name}" -o "$OUT/${binding_name}"
if [ "$(wc -l < "$OUT/${checksums_name}")" -ne 2 ]; then
  echo "expected exactly two checksums in ${checksums_name}" >&2
  exit 1
fi
(cd "$OUT" && tr -d '\r' < "${checksums_name}" | sha256sum --check --quiet -)
echo "RUSTY_V8_ARCHIVE=$OUT/${archive_name}"
echo "RUSTY_V8_SRC_BINDING_PATH=$OUT/${binding_name}"
