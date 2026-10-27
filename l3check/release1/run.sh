#!/bin/bash
# Release smoke (design doc 10.0 R1-R4, R7): real binary, local mock provider, a copy of the
# server model catalog from ~/.codex/models_cache.json. usage: run.sh <codex-binary>
set -u
BIN=$1
HERE=$(cd "$(dirname "$0")" && pwd)
T=${RELSMOKE_DIR:-$(mktemp -d)}
mkdir -p "$T/home" "$T/work" "$T/req"
python3 -c 'import json,os; d=json.load(open(os.path.expanduser("~/.codex/models_cache.json"),encoding="utf-8")); json.dump({"models":d["models"]},open("'"$T"'/catalog.json","w",encoding="utf-8"))'
cat > "$T/home/config.toml" <<EOF
model_provider = "mock"
model_catalog_json = "$T/catalog.json"
[model_providers.mock]
name = "mock"
base_url = "http://127.0.0.1:18765/v1"
wire_api = "responses"
requires_openai_auth = false
supports_websockets = false
request_max_retries = 0
stream_max_retries = 0
EOF
python3 "$HERE/mock_responses.py" "$T/req" 18765 &
MOCK=$!
sleep 1
export CODEX_HOME=$T/home
run() { # name, slug, mode, args...
  local name=$1 slug=$2 mode=$3; shift 3
  rm -f "$T"/req/req-*
  echo "== $name"
  timeout 120 taskset -c 0-11 "$BIN" exec --skip-git-repo-check -C "$T/work" -m "$slug" "$@" > "$T/$name.out" 2>&1
  echo "exit=$?"; tail -3 "$T/$name.out"
  python3 "$HERE/check_instructions.py" "$T/req" "$T/catalog.json" "$slug" "$mode" ${CUSTOM:-}
  mkdir -p "$T/keep/$name"; cp "$T"/req/req-* "$T/keep/$name/" 2>/dev/null
}
run S_a_astra gpt-6-astra new "say ok"
run S_a_sol gpt-5.6-sol new "say ok"
# S-b: turn the just-created model-provenance thread into a deterministic copy of
# an old stored thread whose base instructions still contain compaction wording.
# This keeps the smoke independent of the operator's ~/.codex rollout retention.
SRC=$(python3 - "$CODEX_HOME/sessions" <<'PY'
import json, pathlib, sys
for f in sorted(pathlib.Path(sys.argv[1]).rglob("*.jsonl"), key=lambda p: p.stat().st_size):
    p = json.loads(f.read_text(encoding="utf-8").splitlines()[0])["payload"]
    bi = p.get("base_instructions") or {}
    if p.get("originator") == "codex_exec" and isinstance(bi, dict) and (bi.get("provenance") or {}).get("model") == "gpt-5.6-sol":
        print(f)
        break
PY
)
python3 - "$SRC" <<'PY'
import json, pathlib, sys
path = pathlib.Path(sys.argv[1])
lines = path.read_text(encoding="utf-8").splitlines()
head = json.loads(lines[0])
head["payload"]["base_instructions"]["text"] += (
    "\n\nWhen that happens, you assume compaction occurred while you were working."
    "\n\nStored rollout continuation marker."
)
lines[0] = json.dumps(head, ensure_ascii=False, separators=(",", ":"))
path.write_text("\n".join(lines) + "\n", encoding="utf-8")
PY
TID=$(python3 -c 'import json,sys; print(json.loads(open(sys.argv[1],encoding="utf-8").readline())["payload"]["id"])' "$SRC")
echo "resume source size=$(stat -c %s "$SRC") id=$TID"
run S_b_resume gpt-5.6-sol resume resume "$TID" "say ok"
# S-c: user-supplied instructions stay verbatim
printf 'Custom instructions. Compaction does not end the task.\n' > "$T/custom.md"
CUSTOM=$T/custom.md run S_c_custom gpt-5.6-sol custom -c model_instructions_file="\"$T/custom.md\"" "say ok"
echo "== compaction items in temp rollouts"
grep -l -E '"type":"compacted"|ContextCompacted|context_compacted' -r "$CODEX_HOME/sessions" | wc -l
kill $MOCK
