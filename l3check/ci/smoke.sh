#!/bin/bash
# CI smoke for this fork: one `codex exec` turn against a local mock provider.
# Passes when the turn exits 0, every request was assembled by VRS, and nothing was compacted.
# usage: smoke.sh <codex-binary>
set -euo pipefail
BIN=$1
HERE=$(cd "$(dirname "$0")" && pwd)
T=$(mktemp -d)
mkdir -p "$T/home" "$T/work" "$T/req"
cat > "$T/home/config.toml" <<EOF
model_provider = "mock"
[model_providers.mock]
name = "mock"
base_url = "http://127.0.0.1:18766/v1"
wire_api = "responses"
requires_openai_auth = false
supports_websockets = false
request_max_retries = 0
stream_max_retries = 0
EOF
python3 "$HERE/../release1/mock_responses.py" "$T/req" 18766 &
MOCK=$!
trap 'kill "$MOCK" 2>/dev/null || true' EXIT
sleep 1
if ! CODEX_HOME="$T/home" CODEX_VRS_LOG="$T/receipts.jsonl" timeout 120 \
  "$BIN" exec --skip-git-repo-check -C "$T/work" "say ok" > "$T/out.txt" 2>&1; then
  cat "$T/out.txt"
  exit 1
fi
echo "receipts:"
cat "$T/receipts.jsonl"
grep -q '"outcome":"assembled"' "$T/receipts.jsonl"
if grep -q -v '"outcome":"assembled"' "$T/receipts.jsonl"; then
  echo "a request was not assembled"
  exit 1
fi
if grep -r -q -E '"type":"compacted"|context_compacted' "$T/home/sessions"; then
  echo "compaction found"
  exit 1
fi
echo "requests: $(ls "$T/req"/*.json | wc -l)"
echo "PASS"
