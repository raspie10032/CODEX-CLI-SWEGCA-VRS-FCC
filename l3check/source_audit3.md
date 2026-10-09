# Round 3 source audit at 3530ac9a1

This audit reads tracked Rust source at `3530ac9a1c3fe78db45abbcf84c23dc4f5ed7059`.
Production source is unchanged from `8fdfd4f55`; the newer commit repairs four
unit-test error-kind assertions. No product source, snapshot expectations, build,
service, or test was changed or run by this audit. Existing reports remain intact.
The parent owns the final build/test comparison and REPORT3.

Run `python3 l3check/audit3_inventory.py` to regenerate the mechanically counted
artifacts. The script explicitly fails on a new unclassified production
`clone_history()` call. Its function labels are nearest preceding declarations,
not a Rust compiler call graph. The detailed reasons below were checked against
actual consumers. The combined source hash and external library identity are in
`inventory3.json`.

## Model-input boundary and remaining history clones

The audited claim is **no accumulated response-item history from these clones is
used as a fallback for production model Prompt/input**. This is narrower than
"no influence on model behavior." D4 explicitly permits tool-origin lookup,
world-state metadata, and token display (design lines 128–131). D3 excludes
finished-rollout memory extraction at line 126. Existing host metadata and control
values can influence later requests; they are not an alternate transcript source.

`clone_history3.tsv` records all **73** call sites with current file:line,
containing function, classification, indirect-effect flag, and individual reason:

| Group | Count | Boundary |
| --- | ---: | --- |
| Test modules | 65 | Assertions/fixtures, including one call inside the explicit cfg(test) extension-tools module. Tests can exercise model mocks; they are not production call sites. |
| Public test-support helper | 1 | `core/src/test_support.rs:81`; not cfg(test). All five in-tree callers are code-mode test assertions. It returns diagnostic metadata and never dispatches. External API consumers are outside this source audit. |
| Diagnostic, debug API, telemetry | 3 | Failed-review diagnostic buffer, debug prompt rendering, shutdown count. The debug API returns model-shaped input, but its path shuts down and returns without sampling. |
| TRACE numeric estimate | 1 | `session/mod.rs:1495` -> `turn.rs:487-493`, inside a TRACE-enabled guard. No branch/reminder consumes this value; token_status is a separate computation. |
| Forwarding helper | 1 | `session/mod.rs:4285` -> `state/session.rs:171-172`; safety depends on its enumerated consumers. |
| Indirect metadata/control | 2 | Details below. |

Two indirect effects are present and permitted by the stated boundary:

- `core/src/tools/context.rs:105` extracts a matching call's item ID, then adds
  its current window ID. `tools/lifecycle.rs:41-60` forwards the ID to extensions;
  Guardian V2 `wrapper_lag.rs:25-68` uses it to link nested tool wrappers, and
  `score.rs:163` discounts score lag. This affects score reuse/fallback control.
  Code-mode and MCP handlers also propagate the origin into execution/approval
  context. No response-item text is forwarded by this clone. D4 line 128 names
  this lookup explicitly.
- `core/src/session/mod.rs:1704` finds an external-context marker and calls
  `stream_events_utils.rs:168-183`, which marks persisted `memory_mode` polluted.
  `state/src/runtime/memories.rs:241` selects only enabled threads for later
  extraction. Thus model-work eligibility can change. This is not a model
  transcript fallback, and D3 line 126 excludes A17/A19 finished-rollout
  extraction from the thread-history contract.

The failed-review feedback path is
`core/src/guardian/feedback.rs:29` ->
`ext/guardian-reviewer/src/feedback.rs:85,105,118` ->
`feedback/src/guardian.rs:94`. The sink is a bounded opt-in feedback buffer.
The existing feedback buffer mutex is not a newly introduced assembly lock.

## D3 / P-6 caller table

Paths in this table are relative to `codex-rs/`. "A" means a fresh
`vrs_input` result, followed by the existing caller's prompt projection and host
metadata handling; this is not a claim that every transport sends identical
untransformed JSON. A missing/failed A is not replaced by H.

| Place | Current entry and failure behavior |
| --- | --- |
| A1 first attempt | `core/src/session/turn.rs:1196` calls `vrs_prompt_input` at the top of the sampling loop; `?` at 1202 exits before dispatch. Final request admission at 1224 precedes sampling at 1225. |
| A2 retry | The same loop begins at `turn.rs:1191`; every iteration assembles again at 1196 using the captured step model and same instructions. No retry reads H. |
| A4 History prewarm | `core/src/session/startup_prewarm.rs:407` assembles with `?`; final admission at 421 precedes prewarm at 434. Base at 403 keeps the explicitly permitted empty input. |
| A8 pending Guardian budget | `core/src/guardian/input_budget.rs:48` calls `vrs_history`; error propagates at 50. Instruction reuse is checked against A at 51. |
| A9 final Guardian budget | `input_budget.rs:95` calls `vrs_history`; error propagates at 97. A projects into the budget request at 98–119. Existing optional evidence policy is separate from an H fallback. |
| A10 Guardian review parent | `core/src/guardian/review.rs:220` supplies parent A. Failure returns prompt-build error at 223–228, before reviewer dispatch. |
| A13 Guardian prewarm parent | `core/src/guardian/review_session_setup.rs:255` supplies parent A to PreparedGuardianContext; `?` propagates. Reviewer requests subsequently enter A1/A2. |
| VI-18 reviewer mode | `core/src/guardian/review_session.rs:360` reads reviewer A; failure becomes SessionFailed at 366–373. |
| VI-18 reviewer images | `review_session.rs:449` uses reviewer A for image deduplication; `?` propagates. |
| VI-18 followup reminder | `review_session.rs:724` checks A, propagates at 725, then records missing reminder at 742. |
| VI-18 node policy | `review_session.rs:768` checks A, propagates at 769; no H check remains. |
| A14 scorer snapshot | `core/src/session/mod.rs:4297-4304` returns Result and calls A at 4301. `core/src/tools/lifecycle.rs:37-39` turns failure into fatal tool error before contributors run. `ext/guardian-v2/src/async_scorer/approval.rs:148-154` validates A even before the initial-CUA fast path; authorization.rs:30 also uses the fallible snapshot. Parent-compaction reuse code is absent. |
| A15 realtime context | `core/src/realtime_context.rs:66` obtains A before rendering current-thread text. `realtime_conversation.rs:1513-1516` propagates Err before treating a successful None as empty. Existing explicit configured startup-context overrides are not an assembly-error fallback. |
| A20 agent fork | `core/src/agent/control/spawn.rs:1008` gets parent A; error propagates at 1010. ResponseItems become seed rollout items at 1019–1023. Explicit LastNTurns and existing host usage-hint filtering act on this A (1032 onward), not the parent's accumulated rollout. Subsequent child requests enter A1/A2. |
| A18/A21/A22 separate threads | Normal requests enter A1/A2. Fileless insertion is `core/src/session/vrs_input.rs:288-307`; no-file live stores route there from `session/mod.rs:4270`. |
| A5 debug API | `core/src/prompt_debug.rs:107` intentionally remains a debug rendering consumer and has no sampling dispatch. It is included in clone_history3.tsv, not concealed. |
| A17/A19 extraction | Finished-rollout consumers are explicitly excluded by D3 at design:126. No live-history fallback was added. |
| A6/A7 compression | Required removed symbols are zero. Manual `compact_unsupported` emits BadRequest at `core/src/session/handlers.rs:245-255`; no summarization task is dispatched. |

## Common assembly, D4, and D5

- `core/src/session/vrs_input.rs:99-104` takes the existing SessionState mutex
  briefly to check sticky recording/publication errors and capture a cache cut.
  The guard is gone before path resolution and FFI at 107–112. A local path is
  preferred; no local file uses this Session's unique virtual generation.
- `vrs_input.rs:112-114` calls `assemble_with_budget` and rejects malformed,
  unknown, or obsolete compaction items at 123–141. A valid prefix of a malformed
  assembly is never accepted. `vrs_error_to_codex` at 54–62 maps not-ready to
  turn failure and over-window to ContextWindowExceeded.
- `vrs_prompt_input` at 148–173 reserves the current request's fixed cost and
  rejects empty model input. `check_prompt_window` at 179–187 checks the final
  normalized request, with the exact same captured step allowance. These are
  **byte-based estimates**, not tokenizer-exact I4 evidence.
- `vrs_input` at 73–78 installs a private cache copy and returns **unmerged A**.
  `vrs_history` at 255–258 also returns only A's items by calling
  `ContextManager::with_assembled_items` at `context_manager/history.rs:759`.
  That function replaces cloned items; retained host metadata is not an
  accumulated response-item fallback. Guardian compatibility review history is
  cleared at `history.rs:752-754`.
- `state/vrs_live_cache.rs:65-155` records a bounded overlapping delta, publishes
  status with atomics, captures refresh generations, rejects stale installation,
  and retires completed delta records. Existing SessionState mutex protection
  is used by `state/session.rs:175-210`. Neither the journal nor A waits for a
  pending publisher. VI-32 at design:512 documents the conservative cut and the
  lack of a C snapshot watermark. Runtime boundedness is not proved here.
- Ordinary records register the delta while holding the existing mutex at
  `session/mod.rs:3483`, publish outside it at 3495, then mark status at 3497.
  Recording errors are retained at 4270–4276, and cancelled publication marks
  its atomic state in `state/vrs_live_cache.rs:43-48`. Both pre-assembly and
  pre-installation checks reject sticky errors (`state/session.rs:189-210`).
- Resume metadata reconstruction sets response-item history to empty at
  `session/mod.rs:1742-1750`. It restores host metadata separately. Resume/fork
  call `restore_history_from_vrs` at 1638/1696; this initial installation logs a
  failure at `vrs_input.rs:248-249`, rather than forcing an immediate startup
  error. Subsequent model input reassembles and propagates failure; it cannot
  fall back to the replayed history.
- Fileless resume seeds original records into the Session-specific virtual S
  at `session/mod.rs:1585` and `vrs_input.rs:271-307`; path/insert/overflow errors
  poison later model admission. The fresh generation is not a fallback copy of
  H supplied directly to a request.

## E3-2 symbol and socket results

`compression3.txt` contains every matching tracked Rust occurrence:

| Symbol substring | Occurrences |
| --- | ---: |
| run_auto_compact | 0 |
| compact_remote_v2 | 0 |
| CompactTask | 0 |
| replace_compacted_history | 0 |
| model_auto_compact_token_limit | 21 |

The 21 remaining occurrences are four inert config/protocol fields (including
scope companions), one configuration comment, and 16 fixture/configuration-test
occurrences. There is no executable trigger among those matches. This count is
**tracked Rust**, not every generated schema/document in the repository.
Historical protocol/config/rollout compaction representations and window IDs
still exist for compatibility, diagnostics, or host identity; zero occurrences
of the five requested terms does not mean the word compaction vanished globally.

`socket3.txt` reports `UnixStream|CODEX_VRS_SOCK` = **0** both under all
`codex-rs/core/` Rust files and `codex-rs/core/src/`. Generic socket/WebSocket
strings are not a requirement and were not treated as failures.

## E3-3 Rust and external C boundaries

The three new production modules (`vrs/src/lib.rs`, `session/vrs_input.rs`,
`state/vrs_live_cache.rs`) contain no Mutex/RwLock/Condvar/Barrier/OnceLock type,
get_or_init, writer flush barrier, readiness poll, or sleep/yield wait. Five
`.lock()` occurrences in production `vrs_input.rs` refer to the **existing
SessionState mutex**, at lines 101, 236, 257, 280, and 292. They protect short
host-state access; FFI and writer completion are outside those guards.

Initialization is a startup operation at `arg0/src/lib.rs:236`.
`vrs/src/lib.rs:154-161` uses a single CAS to publish one immutable handle;
concurrent readers load it at 198–203 or return NotReady. They do not wait for
initialization or run it from a request. This is the VI-13 startup exception,
not a single-writer queue for insertion/assembly.

The P-3'' recorder reserves ordinal and offset in one AtomicU64 at
`rollout/src/recorder.rs:2115-2179`, retrying serialization only after CAS loss.
Successful callers insert at 2175 **before** queueing the existing writer at
1056–1073. Queue send backpressure and codex's existing Persist/Flush durability
operations remain. They are not an assembly barrier. Position writes and flush
are awaited **inside the preexisting writer** at 2228–2239; assembly has no
call to that path. Optional `CODEX_VRS_LOG` receipts perform synchronous
filesystem I/O (`vrs_input.rs:28-50`); this is diagnostic I/O, not a producer
readiness barrier. It is not claimed to be latency-free.

**End-to-end E3-3 does not pass.** The Rust FFI calls external C synchronously.
At the captured library source, `$WORK/vrsint/vrs_lib.cpp:3111-3114`
waits for another per-file owner to finish `vrs_insert` using a yield loop.
This is a real phase/owner wait below the Rust boundary. The current library
also returns -3 at line 3126 when `vrs_written` cannot find its retained copy.
The saved probe `library_deferred3.json` records
`open=0 ready=1 insert=0 written=-3 expected_written=0`, exit 1. This audit did
not rerun it. `inventory3.json` records the saved probe hash separately from the
currently read library hash; source and archive identity are not assumed equal.
`nm --defined-only` confirms vrs_open, vrs_insert, vrs_written, and vrs_assemble_b
are defined in the currently read archive. A symbol is not correctness evidence.

No release build, remaining-tests compilation, test-difference resolution,
I4 physical-window bound, I7 memory measurement, or I8 concurrency result is
claimed by this source audit.
