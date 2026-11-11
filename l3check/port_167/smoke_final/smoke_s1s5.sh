#!/bin/bash
# G_114 R5 first half: smoke4 S1-S5 against the real backend with the given binary.
# usage: smoke_s1s5.sh <binary> <out dir name>
BIN=$1
D=$HOME/tmp/p114-work/smoke/$2
RUN=$HOME/tmp/codex-p114/l3check/smoke4/run.py
mkdir -p "$D" && cp "$RUN" "$D/run.py"
R() { taskset -c 0-11 python3 "$D/run.py" "$@" --binary "$BIN" --timeout 600 --output-root "$D/out" --work-root "$D/work" > "$D/$1.stdout" 2>&1; }
R S1
T=$(python3 -c "import json;print(json.load(open('$D/out/S1/result.json'))['thread_id'])")
R S2 --resume "$T"
R S3
R S4A & R S4B & wait
R S5
python3 - "$D/out" <<'PY'
import json, pathlib, sys
d = pathlib.Path(sys.argv[1]); allok = True
for c in ["S1", "S2", "S3", "S4A", "S4B", "S5"]:
    r = json.loads((d / c / "result.json").read_text(encoding="utf-8"))
    ok = (r["exit_code"] == 0 and not r["timed_out"] and r["vrs_receipts"] > 0 and not r["vrs_failed_receipts"]
          and not r["vrs_error_lines"] and not r["event_errors"] and not r["command_failures"] and bool(r.get("rollouts"))
          and all(x["compaction_events"] == 0 and not x["parse_errors"] and x["nul_bytes"] == 0 for x in r["rollouts"]))
    fin = (r["final_messages"] or [""])[-1]
    # Content checks added 11-11 after the first run passed while every tool call failed:
    # S1 must read the file, S2 must recall S1, S3/S4 must really execute >= 11 commands.
    if c == "S1": ok &= "hello" in fin.lower()
    if c == "S2": ok &= "a.txt" in fin and "hello" in fin.lower()
    if c in ("S3", "S4A", "S4B"): ok &= r["executed_commands"] >= 11 and "210" in fin
    allok &= ok
    print(c, "PASS" if ok else "FAIL", "exit", r["exit_code"], "receipts", r["vrs_receipts"], "failed", len(r["vrs_failed_receipts"]),
          "errors", len(r["event_errors"]), "cmds", r["executed_commands"], "| final:", (r["final_messages"] or [""])[-1][:120].replace("\n", " "))
print("ALL PASS" if allok else "SOME FAIL")
PY
