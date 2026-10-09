"""Capture source evidence only; this does not build or run tests."""

from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "l3check"


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True)


files = git("ls-files", "codex-rs").splitlines()
sources = {
    name: (ROOT / name).read_text().splitlines()
    for name in files
    if name.endswith(".rs") and (ROOT / name).exists()
}


def matches(pattern, prefix="codex-rs/", flags=0):
    regex = re.compile(pattern, flags)
    return [
        {"file": name, "line": index, "text": text.strip()}
        for name, lines in sources.items()
        if name.startswith(prefix)
        for index, text in enumerate(lines, 1)
        if regex.search(text)
    ]


compaction = {
    symbol: matches(re.escape(symbol))
    for symbol in (
        "run_auto_compact",
        "compact_remote_v2",
        "CompactTask",
        "replace_compacted_history",
        "model_auto_compact_token_limit",
    )
}
socket = {
    "core_src_UnixStream_or_CODEX_VRS_SOCK": matches(
        r"UnixStream|CODEX_VRS_SOCK", "codex-rs/core/src/"
    ),
    "core_src_literal_socket_case_insensitive": matches(
        "socket", "codex-rs/core/src/", re.IGNORECASE
    ),
    "core_all_UnixStream_or_CODEX_VRS_SOCK": matches(
        r"UnixStream|CODEX_VRS_SOCK", "codex-rs/core/"
    ),
}
clones = matches(r"clone_history\(\)")
notes = {
    ("guardian/feedback.rs", 29): (
        "non_request", "Writes local review feedback, not a model request."
    ),
    ("guardian/review_session.rs", 385): (
        "unresolved_model_influence", "Selects full/delta review transcript mode."
    ),
    ("guardian/review_session.rs", 448): (
        "unresolved_model_influence", "Reads retained images when preparing review input."
    ),
    ("guardian/review_session.rs", 721): (
        "unresolved_model_influence", "Controls developer reminder injection."
    ),
    ("guardian/review_session.rs", 764): (
        "unresolved_model_influence", "Controls node REPL policy injection."
    ),
    ("prompt_debug.rs", 107): (
        "non_request", "Debug prompt rendering; excluded by design A5."
    ),
    ("session/handlers.rs", 346): (
        "non_request", "Counts turns for shutdown telemetry."
    ),
    ("session/mod.rs", 1496): (
        "non_request", "Returns a token-count estimate, not response items."
    ),
    ("session/mod.rs", 1704): (
        "non_request", "Marks memory mode polluted by external context."
    ),
    ("session/mod.rs", 4262): (
        "helper", "Delegates to state history; safety depends on its callers."
    ),
    ("tools/context.rs", 105): (
        "non_request", "Finds the originating tool-call item ID."
    ),
    ("tools/handlers/extension_tools.rs", 460): (
        "test", "Inline test assertion; not production model input."
    ),
}
for hit in clones:
    path = hit["file"]
    key = (path.removeprefix("codex-rs/core/src/"), hit["line"])
    if key in notes:
        hit["classification"], hit["reason"] = notes[key]
    elif "tests" in Path(path).parts or "tests" in Path(path).stem:
        hit["classification"] = "test"
        hit["reason"] = "Test assertion/setup only; not a production request path."
    else:
        hit["classification"] = "unreviewed"
        hit["reason"] = "No claim that this cannot reach a model request."

failed = (OUT / "failed_tests.txt").read_text().splitlines()
suite = (OUT / "suite_real.log").read_text()
statuses = re.findall(
    r"^test (\S+) \.\.\. (ok|FAILED|ignored)(?:,.*)?$", suite, re.MULTILINE
)
rerun = (OUT / "rerun_failed.log").read_text()
prior_deleted_tests = [
    path
    for path in git("diff", "--name-only", "--diff-filter=D", "3da13917bdc", "HEAD").splitlines()
    if "/tests/" in path or "tests" in Path(path).stem
]
report = {
    "head": git("rev-parse", "HEAD").strip(),
    "branch": git("branch", "--show-current").strip(),
    "source_scope": "Tracked Rust files in the current working tree, including incoming dirty edits",
    "compaction": compaction,
    "socket": socket,
    "clone_history": clones,
    "clone_class_counts": dict(Counter(item["classification"] for item in clones)),
    "prior_failures": {
        "file_entries": len(failed),
        "unique_entries": len(set(failed)),
        "suite_announced": re.search(r"running (\d+) tests", suite).group(1),
        "suite_statuses": dict(Counter(status for _, status in statuses)),
        "suite_result_lines": re.findall(r"^test result:.*$", suite, re.MULTILINE),
        "suite_exit_lines": re.findall(r"^EXIT.*$", suite, re.MULTILINE),
        "rerun_result_lines": re.findall(r"^test result:.*$", rerun, re.MULTILINE),
    },
    "previous_wip_deleted_test_files": prior_deleted_tests,
    "incoming_dirty_source_sha256": {
        name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        for name in (
            "codex-rs/core/tests/suite/code_mode.rs",
            "codex-rs/vrs/src/lib.rs",
        )
    },
}
(OUT / "current_inventory.json").write_text(json.dumps(report, indent=2) + "\n")
for name, groups in (("current_compaction.txt", compaction), ("current_socket.txt", socket)):
    lines = []
    for label, hits in groups.items():
        lines.append(f"{label}: {len(hits)} matching lines")
        lines.extend(f"{h['file']}:{h['line']}: {h['text']}" for h in hits)
    (OUT / name).write_text("\n".join(lines) + "\n")
(OUT / "current_clone_history.tsv").write_text(
    "file:line\tclassification\treason\n"
    + "\n".join(
        f"{h['file']}:{h['line']}\t{h['classification']}\t{h['reason']}" for h in clones
    )
    + "\n"
)
print(json.dumps({
    "compaction_counts": {key: len(value) for key, value in compaction.items()},
    "socket_counts": {key: len(value) for key, value in socket.items()},
    "clone_history_total": len(clones),
    "clone_class_counts": report["clone_class_counts"],
    "prior_failures": report["prior_failures"],
}, indent=2))
