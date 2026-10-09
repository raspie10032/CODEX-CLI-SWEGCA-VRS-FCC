"""Read-only source inventory; never compiles or executes product/tests.

The per-function clone classification is a manual call-path audit, not a general
Rust reachability analyzer. Unknown production calls fail generation explicitly.
"""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'l3check'


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT, text=True)


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


head = git('rev-parse', 'HEAD').strip()
sources = {name: (ROOT / name).read_text(encoding='utf-8')
           for name in git('ls-files', 'codex-rs').splitlines()
           if name.endswith('.rs') and (ROOT / name).exists()}


def hits(pattern, prefix='codex-rs/'):
    regex = re.compile(pattern)
    result = []
    for name, source in sources.items():
        if not name.startswith(prefix):
            continue
        for match in regex.finditer(source):
            line = source.count('\n', 0, match.start()) + 1
            result.append({'file': name, 'line': line,
                           'text': source.splitlines()[line - 1].strip()})
    return result


# Stable keys are file/function, not stale line numbers. Every call includes its
# current source line and nearest preceding fn declaration for human review.
notes = {
    ('guardian/feedback.rs', 'record_failed_review'): (
        'diagnostic', False,
        'Failed-review raw items serialize to bounded opt-in diagnostic JSON: '
        'ext/guardian-reviewer/src/feedback.rs:85,105,118 -> feedback/src/guardian.rs:94. '
        'The sink stores feedback records; no prompt/model dispatch consumes this copy.'),
    ('prompt_debug.rs', 'build_prompt_input_from_session'): (
        'debug_api_projection', False,
        'Projects H into build_prompt then returns prompt.input to the debug API; '
        'prompt_debug.rs:76-80 shuts down its temporary thread and returns the data. '
        'No sampling dispatch follows. This is model-shaped debug output (Q1 A5), '
        'not proof that the value has no possible external consumer.'),
    ('session/handlers.rs', 'shutdown'): (
        'telemetry', False,
        'Counts user boundaries for codex.conversation.turn.count at handlers.rs:351-355; '
        'then shuts down persistence. Response items are not passed to a request.'),
    ('session/mod.rs', 'get_estimated_token_count'): (
        'trace_only_numeric_estimate', False,
        'Returns Option<i64>; sole production caller is turn.rs:487 inside TRACE event_enabled '
        'and immediately logs it at 488-493. This particular clone does not drive the '
        'separate token_status/reminder logic. D4 permits token display.'),
    ('session/mod.rs', 'record_initial_history'): (
        'memory_eligibility_control', True,
        'Finds a FunctionCallOutput without call_id, then marks DB memory_mode polluted '
        '(stream_events_utils.rs:168-183; state/src/runtime/memories.rs:630-651). '
        'No response-item payload is forwarded, but future memory-extraction eligibility '
        'changes (memories.rs:241 enabled filter). D3 excludes A17/A19 finished-rollout '
        'extraction at design:126; this is indirect model-work influence, not zero influence.'),
    ('session/mod.rs', 'clone_history'): (
        'forwarding_helper', None,
        'Forwards to state/session.rs:171-172 (self.history.clone) under the existing Session '
        'mutex. It has no independent sink; consumers are all other rows in this inventory, '
        'including explicitly identified metadata/control paths.'),
    ('tools/context.rs', 'originating_call'): (
        'tool_origin_control', True,
        'Extracts only matching call item ID plus current window ID, never ResponseItem text. '
        'D4 explicitly permits tool-origin lookup (design:128). ID flows through '
        'tools/lifecycle.rs:41-60 to Guardian WrapperLag (ext/guardian-v2/src/async_scorer/'
        'wrapper_lag.rs:25-68; score.rs:163), affecting score reuse/fallback decisions; '
        'also passes through code-mode and MCP execution approval context. '
        'This is indirect control influence, not accumulated-history model input.'),
    ('test_support.rs', 'history_with_tool_call_metadata'): (
        'public_test_support_diagnostic', False,
        'Public test-support helper reads D4 diagnostic metadata and performs no request. '
        'All five in-tree callers are core/tests/suite/code_mode.rs assertions '
        '(2418,2613,2745,2889,3029). Module is public, NOT cfg(test); external callers '
        'are outside this repository reachability audit.'),
}
clone_rows = hits(r'\bclone_history\s*\(\s*\)')
for row in clone_rows:
    source = sources[row['file']]
    offset = sum(len(line) for line in source.splitlines(keepends=True)[:row['line'] - 1])
    functions = list(re.finditer(r'\bfn\s+([A-Za-z_][A-Za-z_0-9]*)\b', source[:offset]))
    function = functions[-1].group(1) if functions else '<none>'
    row['function'] = function
    relative = row['file'].removeprefix('codex-rs/core/src/')
    entry = notes.get((relative, function))
    if entry is not None:
        row['classification'], row['indirect_model_influence'], row['reason'] = entry
    elif row['file'].endswith(('_tests.rs', '/tests.rs')) or '/tests/' in row['file']:
        row.update(classification='test', indirect_model_influence=False,
                   reason=f'Test-only function/fixture {function}; reads/asserts host history in '
                          'a test module, no production model request sink. Test execution may '
                          'use model mocks; this is not a claim the test cannot send requests.')
    elif relative == 'tools/handlers/extension_tools.rs' and row['line'] > 226:
        row.update(classification='test', indirect_model_influence=False,
                   reason=f'Function {function} is inside #[cfg(test)] mod tests at '
                          'extension_tools.rs:225-226; fixture/assertion only.')
    else:
        raise RuntimeError(f'Unreviewed clone call: {row}')

symbols = ('run_auto_compact', 'compact_remote_v2', 'CompactTask',
           'replace_compacted_history', 'model_auto_compact_token_limit')
compression = {symbol: hits(re.escape(symbol)) for symbol in symbols}
for row in compression['model_auto_compact_token_limit']:
    path = row['file']
    if path in ('codex-rs/config/src/config_toml.rs',
                'codex-rs/app-server-protocol/src/protocol/v2/config.rs'):
        row['classification'] = 'inert_configuration_or_protocol_compatibility_field'
    elif path == 'codex-rs/protocol/src/config_types.rs':
        row['classification'] = 'configuration_compatibility_documentation'
    else:
        row['classification'] = 'compatibility_test_config_or_fixture'
sockets = {prefix: hits(r'UnixStream|CODEX_VRS_SOCK', prefix)
           for prefix in ('codex-rs/core/', 'codex-rs/core/src/')}

new_paths = ('codex-rs/vrs/src/lib.rs',
             'codex-rs/core/src/session/vrs_input.rs',
             'codex-rs/core/src/state/vrs_live_cache.rs')
production = {path: sources[path].split('\n#[cfg(test)]\nmod tests', 1)[0]
              for path in new_paths}
lock_patterns = {
    'new_lock_types_or_init_wait': r'\b(?:Mutex|RwLock|Condvar|Barrier|OnceLock)\b|get_or_init',
    'writer_barrier_or_ready_poll': r'flush_rollout|vrs_ready|yield_now|sleep\(|\.wait\(',
    'existing_session_mutex_access': r'\.lock\(',
    'atomic_CAS': r'compare_exchange|fetch_update',
}
synchronization = {}
for label, pattern in lock_patterns.items():
    synchronization[label] = []
    for path, source in production.items():
        for match in re.finditer(pattern, source):
            line = source.count('\n', 0, match.start()) + 1
            synchronization[label].append({'file': path, 'line': line,
                                           'text': source.splitlines()[line - 1].strip()})

library = Path('$WORK/vrsint/libvrs.a')
lib_source = Path('$WORK/vrsint/vrs_lib.cpp')
lib_text = lib_source.read_text(encoding='utf-8')
lib_hits = []
for number, line in enumerate(lib_text.splitlines(), 1):
    if ('while (!done.load' in line or 'if (!uw_del(S, *ss, off))' in line):
        lib_hits.append({'file': str(lib_source), 'line': number, 'text': line.strip()})
nm = subprocess.run(['nm', '--defined-only', str(library)], capture_output=True, text=True)
symbol_lines = [line for line in nm.stdout.splitlines()
                if re.search(r'\b(?:vrs_written|vrs_assemble_b|vrs_insert|vrs_open)$', line)]
source_digest = hashlib.sha256()
for path, source in sorted(sources.items()):
    source_digest.update(path.encode() + b'\0' + source.encode() + b'\0')

report = {
    'source_head': head,
    'captured_utc': datetime.now(timezone.utc).isoformat(),
    'scope': 'Tracked Rust files in current worktree; comments/fixtures counted by symbol grep. '
             'Call-path annotations manually reviewed; not a formal reachability proof.',
    'tracked_rust_files': len(sources),
    'tracked_rust_combined_sha256': source_digest.hexdigest(),
    'tracked_rust_dirty': git('diff', '--name-only', '--', '*.rs').splitlines(),
    'builds_or_tests_run_by_inventory': False,
    'compression': compression,
    'compression_counts': {key: len(rows) for key, rows in compression.items()},
    'socket': sockets,
    'socket_counts': {key: len(rows) for key, rows in sockets.items()},
    'clone_history': clone_rows,
    'clone_history_count': len(clone_rows),
    'clone_class_counts': dict(Counter(row['classification'] for row in clone_rows)),
    'indirect_model_control_clones': [row for row in clone_rows if row['indirect_model_influence']],
    'accumulated_response_item_fallback_found': False,
    'fallback_scope': 'Listed clone_history consumers and D3 entry points only; permitted host '
                      'metadata and control effects are explicit and are not claimed to have no influence.',
    'rust_new_path_synchronization': synchronization,
    'rust_wait_scope': 'Three new production modules only plus manually audited recorder CAS/write path. '
                       'Session Mutex and existing rollout queue/durability writer remain. '
                       'Synchronous FFI enters external C code; no end-to-end no-wait claim.',
    'c_library_separate_evidence': {
        'library': str(library), 'sha256': digest(library),
        'source': str(lib_source), 'source_sha256': digest(lib_source),
        'nm_exit_code': nm.returncode, 'defined_symbols': symbol_lines,
        'source_findings': lib_hits,
        'existing_runtime_probe': json.loads((OUT / 'library_deferred3.json').read_text()),
        'runtime_probe_reexecuted': False,
        'e3_3_global_pass': False,
    },
    'limitations': [
        'No build, test, readiness, or integration success follows from this inventory.',
        'Byte-based request estimates are not tokenizer-exact I4 proof.',
        'C insertion owner wait remains a source-level E3-3 conflict.',
        'The saved deferred-file probe reports written=-3; it was not rerun by this audit.',
        'D4 reconciliation uses conservative Rust cut semantics from VI-32, not an exact C snapshot watermark.',
    ],
}
if git('rev-parse', 'HEAD').strip() != head:
    raise RuntimeError('HEAD changed during inventory; regenerate from a stable snapshot')
(OUT / 'inventory3.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
(OUT / 'clone_history3.tsv').write_text(
    'file:line\tfunction\tclassification\tindirect_model_influence\treason\n' +
    ''.join(f"{r['file']}:{r['line']}\t{r['function']}\t{r['classification']}\t"
            f"{r['indirect_model_influence']}\t{r['reason']}\n" for r in clone_rows), encoding='utf-8')
for filename, groups in (('compression3.txt', compression), ('socket3.txt', sockets)):
    lines = [f'Source HEAD: {head}', report['scope']]
    for label, rows in groups.items():
        lines.append(f'\n{label}: {len(rows)} matching occurrences')
        lines.extend(f"{r['file']}:{r['line']}: {r['text']}"
                     + (f" [{r['classification']}]" if 'classification' in r else '') for r in rows)
    (OUT / filename).write_text('\n'.join(lines) + '\n', encoding='utf-8')
print(json.dumps({key: report[key] for key in ('source_head', 'clone_history_count',
                'clone_class_counts', 'compression_counts', 'socket_counts')}, indent=2))
