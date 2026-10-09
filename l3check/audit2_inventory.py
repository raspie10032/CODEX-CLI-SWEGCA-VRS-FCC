"""Save the second task's source inventory without building or running tests."""
from collections import Counter
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "l3check"


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


sources = {
    name: (ROOT / name).read_text().splitlines()
    for name in git("ls-files", "codex-rs").splitlines()
    if name.endswith(".rs") and (ROOT / name).exists()
}


def find(pattern, prefix="codex-rs/"):
    regex = re.compile(pattern)
    return [
        dict(file=name, line=i, text=line.strip())
        for name, lines in sources.items() if name.startswith(prefix)
        for i, line in enumerate(lines, 1) if regex.search(line)
    ]


compaction = {
    symbol: find(re.escape(symbol))
    for symbol in (
        "run_auto_compact", "compact_remote_v2", "CompactTask",
        "replace_compacted_history", "model_auto_compact_token_limit",
    )
}
socket = find(r"UnixStream|CODEX_VRS_SOCK", "codex-rs/core/")
clones = find(r"clone_history\(\)")
production_reasons = {
    "guardian/feedback.rs": "Stores local failed-review feedback; no model sampling or prompt item construction.",
    "prompt_debug.rs": "Renders the debug response; excluded from model requests by D3 A5.",
    "session/handlers.rs": "Counts user-turn boundaries for shutdown telemetry.",
    "tools/context.rs": "Finds the originating call ID for provenance/window metadata; does not return history as prompt input.",
}
for hit in clones:
    relative = hit["file"].removeprefix("codex-rs/core/src/")
    if relative in production_reasons:
        hit.update(classification="non_request", reason=production_reasons[relative])
    elif relative == "session/mod.rs":
        text = hit["text"]
        surrounding = "\n".join(sources[hit["file"]][hit["line"] - 4:hit["line"] + 5])
        if "estimate_token_count" in surrounding:
            hit.update(classification="non_request", reason="Returns only the token-count estimate, not response items.")
        elif text == "state.clone_history()":
            hit.update(classification="helper", reason="Delegates to the state history copy; production consumers are the six non-request entries in this inventory.")
        else:
            hit.update(classification="non_request", reason="Checks for injected external context to mark memory mode polluted; does not construct model input from history.")
    elif "test" in relative or relative == "tools/handlers/extension_tools.rs":
        hit.update(classification="test", reason="Test assertion/setup in a test file or cfg(test) module; no production model request path.")
    else:
        hit.update(classification="unreviewed", reason="No claim that this is excluded from model requests.")

vrs_source = sources["codex-rs/vrs/src/lib.rs"]
input_source = sources["codex-rs/core/src/session/vrs_input.rs"]
report = dict(
    source_head=git("rev-parse", "HEAD"),
    evidence_type="source_inspection_only",
    compaction=compaction,
    core_UnixStream_or_CODEX_VRS_SOCK=socket,
    clone_history=clones,
    clone_class_counts=dict(Counter(h["classification"] for h in clones)),
    vrs_OnceLock_get_or_init_lines=sum("OnceLock" in s or "get_or_init" in s for s in vrs_source),
    vrs_input_flush_rollout_lines=sum("flush_rollout" in s for s in input_source),
)
(OUT / "inventory2.json").write_text(json.dumps(report, indent=2) + "\n")
(OUT / "clone_history2.tsv").write_text("file:line\tclassification\treason\n" + "".join(
    f"{h['file']}:{h['line']}\t{h['classification']}\t{h['reason']}\n" for h in clones
))
(OUT / "compaction2.txt").write_text("".join(
    f"{symbol}: {len(hits)} matching Rust lines\n" + "".join(
        f"{h['file']}:{h['line']}: {h['text']}\n" for h in hits
    ) for symbol, hits in compaction.items()
))
(OUT / "socket2.txt").write_text(f"core Rust UnixStream|CODEX_VRS_SOCK: {len(socket)} matching lines\n" + "".join(
    f"{h['file']}:{h['line']}: {h['text']}\n" for h in socket
))
changed = git("diff", "--name-only", "bfdcbaf61", "HEAD", "--", "codex-rs", "vrs_stub").splitlines()
(OUT / "files_changed2.txt").write_text("\n".join(changed) + "\n")
print(json.dumps(dict(
    compaction_counts={k: len(v) for k, v in compaction.items()},
    core_socket_count=len(socket), clone_count=len(clones),
    clone_classes=report["clone_class_counts"], product_files_changed=len(changed),
    vrs_OnceLock_get_or_init_lines=report["vrs_OnceLock_get_or_init_lines"],
    vrs_input_flush_rollout_lines=report["vrs_input_flush_rollout_lines"],
), indent=2))
