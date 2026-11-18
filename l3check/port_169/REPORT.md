# upstream 0.169.0-alpha.11.1 VRS port L3 source-audit report

Date: 2026-11-18 KST. Branch: `p116`. Pending merge parent:
`MERGE_HEAD=cb1bc0ae` (`rust-v0.169.0-alpha.11.1`). This F3 run did not run Cargo,
the release1 harness, or any Git state-changing command.

## Result and scope

- Required source audits 4a-4f are complete. Conflict resolution, deletion policy, executable
  compaction removal, the single VRS model-input entrance, fail-closed error propagation, D3-double-
  prime, and V114-01 were checked in the merged tree rather than inferred from the older port.
- The final designated production-pattern scan has zero executable compaction references after the
  task's named compatibility exceptions. One residue found by this audit, the unreachable
  `WorkKind::Compaction` execution-kind branch, was removed.
- Every model-history consumer found by the mechanical census is either VRS-derived or is not a
  model input. No accumulated live-history-to-provider route and no fallback after VRS failure was
  found.
- Both prefix/incremental-tool switches return a literal disabled value. The tool spec additionally
  gates incremental exec with a literal false switch.
- Every whole-list replacement increments the list generation and resets the usage boundary. A
  sampling request records `(input length, list generation)` and usage applies that length only
  when the generation still matches. No new FCC lock, wait, barrier, or ordering mechanism was
  introduced by this port.
- Build, test execution, generated-file verification, and Q4/release1 belong to F2/the coordinator
  in this split run. This report deliberately does not claim their outcome.

## 4a. Conflict and deletion resolutions

The initial authoritative list is `~/tmp/p116-work/p116-conflicts.txt`: 53 content conflicts and
15 modify/delete conflicts. The five resolution reports A-E, the C3 continuation, their handoffs,
and the final worktree were reconciled. All 53 content paths are accounted for by the groups below.

### Content conflicts resolved: 53

- Workspace/dependency policy (3): `codex-rs/Cargo.lock`, `codex-rs/Cargo.toml`, and
  `codex-rs/deny.toml`. Upstream 0.169 versions and dependency graph are retained together with the
  FCC `vrs` member and `codex-vrs` dependencies.
- App-server and its integration test (3):
  `app-server/src/request_processors/thread_processor.rs`, `app-server/src/thread_sample.rs`, and
  `app-server/tests/suite/v2/thread_sample.rs`. Account-scoped resume, in-progress sampling, and
  other non-compaction 0.169 behavior remain. Compact RPC execution is unavailable; reference
  fork/sample history is VRS-derived and failures propagate.
- Core production and unit-test seams (32):
  `agent/control/sender_context.rs`; `client.rs`; context-manager `history.rs`,
  `history_tests.rs`, and `mod.rs`; Guardian `decision.rs`, `input_budget.rs`,
  `input_budget_tests.rs`, `mod.rs`, `request_budget.rs`, `review_session.rs`,
  `review_session_setup.rs`, `review_session_tests.rs`, and `tests.rs`; `lib.rs`; session
  `guardian_checkpoint.rs`, `guardian_checkpoint_tests.rs`, `handlers.rs`, `mod.rs`,
  `rollout_reconstruction.rs`, `session.rs`, `startup_prewarm.rs`, `step_context.rs`, `tests.rs`,
  `turn.rs`, and `world_state.rs`; state `auto_compact_window.rs` and `session.rs`;
  `tasks/mod.rs`; `tools/executed_tool_calls/request_metadata_tests.rs`; and `turn_timing.rs` plus
  `turn_timing_tests.rs`. Upstream audio, runtime-auth, context-window identity, tool, and timing
  changes remain; executable compaction/new-window rotation and parent-compaction reuse do not.
- Core integration/dependency/snapshot paths (8): `core/tests/common/Cargo.toml`,
  `guardian_retained_context.rs`, `remote_env.rs`, `rollout_budget.rs`, `scenarios.rs`,
  `scenarios_preparation.rs`, `subagent_notifications.rs`, and
  `all__suite__scenarios__astra_kickoff_original_history.snap`. Non-compaction assertions were
  retained; tests whose subject is deleted compaction were removed or explicitly ignored by the
  test-owning run rather than having their expectations weakened.
- Guardian-v2 (3): `approval.rs`, `extension_tests.rs`, and `startup.rs`. Fallible VRS snapshots
  and authorization stay fail-closed; parent-compaction selection/reuse is absent.
- Rollout recorder (2): `rollout/src/recorder.rs` and `recorder_tests.rs`. Upstream cursor,
  context-window, attachment, and account-scoped metadata changes coexist with FCC VRS reservation
  and publication ordering.
- Thread store (2): `thread-store/Cargo.toml` and `thread-store/src/local/paginated_fork.rs`.
  Upstream paginated lineage behavior remains; referenced forks carry the VRS lineage and do not
  synthesize a compacted model history.

### Modify/delete conflicts kept deleted: 15

All 15 are compaction implementation, async-compaction tests, dedicated compaction integration
tests, or dedicated snapshots; no unrelated helper was left trapped in them.

- Core implementation/unit tests (9): `core/src/compact.rs`, `compact_model_fallback.rs`,
  `compact_remote_history.rs`, `compact_remote_v2.rs`, `compact_remote_v2_attempt.rs`,
  `compact_remote_v2_installation.rs`, `compact_remote_v2_installation_tests.rs`,
  `session/async_compaction.rs`, and `session/async_compaction_tests.rs`.
- Core integration tests (2): `core/tests/suite/compact.rs` and `compact_remote.rs`.
- Dedicated scenario snapshots (4):
  `astra_async_compaction_with_live_suffix.snap`,
  `incremental_tools_resume__legacy_resume_remote_compaction.snap`,
  `prediction_fork_preserves_context_above_compaction_threshold.snap`, and
  `retained_tool_outputs__retained_tool_output_survives_compaction_and_resume.snap`.

### New upstream compaction-only files deleted before text resolution: 9

The coordinator's `coord_116.sh` records this exact set:

- `app-server/tests/suite/v2/snapshots/all__suite__v2__thread_sample__sample_compacted_parent_with_pending_tool_call.snap`
- `core/src/compact_pending_input.rs`
- `core/src/compact_remote_v2_media.rs`
- `core/src/compact_remote_v2_media_budget_tests.rs`
- `core/src/session/compaction_replay_tests.rs`
- `core/tests/suite/snapshots/all__suite__scenarios__audio_file__measured_audio_compaction_and_cold_resume.snap`
- `core/tests/suite/snapshots/all__suite__scenarios__audio_file__uploaded_audio_compaction_and_cold_resume.snap`
- `core/tests/suite/snapshots/all__suite__scenarios__budget_context__host_budget_context_after_compaction.snap`
- `core/tests/suite/snapshots/all__suite__scenarios__injected_agent_mail__injected_agent_message_interrupting_sampling_survives_mid_turn_compaction.snap`

### Post-resolution production fixes included in the audit

- The coordinator's successful pre-F3 check repaired 0.169 API drift without changing FCC
  semantics: `session/reasoning_effort.rs` and `session/startup_prewarm.rs` use sampling request
  effort without the removed `RequestEffortUsage` argument; `session/handlers.rs` initializes
  `ErrorEvent.rejected_audio_file_ids`; `session/session.rs` passes account scope to thread creation
  and passes `ContextWindowId` directly.
- F3 found `utils/critical-path/src/lib.rs` still carrying `WorkKind::Compaction` and an
  execution-kind distribution branch. No producer remained, but the literal violated T1. This was
  an L3 residue affecting `G_116/T1`; the variant and branch were removed. The now exhaustive
  execution-kind enum and dispatcher are at `lib.rs:14-31,102-114`. The analytical
  `compaction_ms` schema remains for backward-compatible analytics. The
  unit test `nested_serial_dependencies_preserve_exclusive_categories` was changed only to
  exercise the same nested serial/exclusive-attribution accounting with an overhead interval,
  without the deleted compaction work kind.
- `l3check/audit3_inventory.py` now writes its artifacts under `l3check/port_169`, recognizes the
  0.169 request-time audio bookkeeping `clone_history()` site, and remains fail-closed for any
  unknown clone consumer.

## 4b. T1 - executable compaction paths: 0

Method: scan the new tracked `codex-rs` Rust, generated config schema, and model catalog with the
full task expression; exclude test code and only the named compatibility exceptions. After the
`WorkKind::Compaction` fix there are 52 production-source lines matching the supplied expression.
All 52 are non-execution compatibility surfaces:

- `config/src/schema.rs:111,115` (2): generated config-field export for accepting old settings.
- `core/config.schema.json:356,854-857,1067,1811,1817,2297,2315,7924-7927,8137` (13): generated
  JSON-schema entries. They parse/document old configuration; they do not register a task or
  handler.
- `core/src/config/mod.rs:690,692,3398-3405,4575` (6): deprecated async-compaction and Guardian
  parent-compaction parsing/range validation. Reverse-consumer search finds no runner, task,
  model-input, or reviewer-reuse consumer.
- `features/src/feature_configs.rs:207,210,262-263,608,618` (6): deserialization and telemetry-key
  shapes for old configuration only.
- `features/src/lib.rs:20,441,505,507,978,1009,1013,2148-2149,2394-2401` (13): feature catalog,
  alias, and compatibility declarations. No production path consumes them to execute compaction.
- `models-manager/models.json:121-122,295-296,468-469,645-646,812-813` (10): optional Guardian
  catalog fields, currently null; no core/extension runtime reader remains.
- `protocol/src/openai_models/guardian_v2.rs:42,44` (2): optional response-deserialization fields
  for wire compatibility only.

The full pattern also has test-only compatibility matches in six files:
`core/src/config/config_loader_tests.rs`, `core/src/session/file_audio_tests.rs`,
`core/tests/suite/guardian_history.rs`, `core/tests/suite/scenarios_guardian_reconsideration.rs`,
`features/src/tests.rs`, and `rollout-trace/src/reducer/conversation_tests.rs`. They do not affect
the production zero conclusion.

Named exceptions were checked semantically rather than simply hidden:

- `analytics/src/facts.rs:252`, `events.rs:1193`, `reducer.rs:3976,4062`, and
  `turn_critical_path.rs:35-74`, plus `core/src/turn_timing.rs:118,436-451` and
  `turn_timing/report.rs:22-24`, preserve the historical `compaction_ms` analytical slot. With the
  compaction phase/work kind gone, no runtime branch adds duration to it.
- `app-server/src/request_processors/thread_processor.rs:5731` and
  `thread-store/src/local/paginated_fork.rs:59-70`, with `thread-store/src/types.rs:248,269,285`,
  carry the upstream `preview_before_compaction` storage shape. It is fork-preview compatibility,
  not a compaction trigger or model-input substitute.
- `history/src/lib.rs:126,337`, `history/src/compaction_resume_metadata.rs:20-23`, and
  `history/src/rollout_payload.rs:352` retain the historical read/wire fields
  `compaction_without_file_error_sources` and
  `CompactionResumeMetadata.rejected_audio_file_ids`. They are decoded compatibility data; they do
  not install or execute a compacted history.
- `tools/src/json_schema/compaction.rs`, `_without_compaction` names,
  `world_state/compact_permissions*`, TUI `exec_cell/compact.rs`, and
  `workspace_presets_compact` are the task's explicit lexical exceptions and do not enter the core
  model-history execution path.

Final T1 statement: there is no reachable `run_*compact`, compact task/handler, context-window
rotation, pre/post compact hook, parent/reviewer compaction reuse, compact media/budget/fallback,
or compaction work-kind producer in production.

## 4c. T2 - one VRS model-history entrance, complete consumer census

### Mechanical counts

`l3check/audit3_inventory.py` completed and wrote `inventory3.json`, `clone_history3.tsv`,
`compression3.txt`, and `socket3.txt` in this directory.

- `clone_history()` expressions: 79 total = 68 test-only + 1 public test-support diagnostic + 10
  production expressions. Every production expression is classified below; none supplies provider
  input.
- `build_prompt(`: five production call sites plus its definition. A lexical production-source
  scan has 19 `Prompt {` lines; 18 are type/impl syntax or unrelated hook/TUI/protocol enum
  variants. The only `client_common::Prompt` construction is `session/turn.rs:1320`.
- `for_prompt*`/`normalize_for_prompt` lexical consumers: six. One is the implementation's
  `for_prompt` to `for_prompt_annotated` delegation and one is an inline test; the four external
  production call sites comprise three VRS-backed consumers and one non-dispatching prompt-debug
  projection.
- `vrs_history()` calls: 16 plus the method definition. `vrs_history_for_path()` calls: four plus
  the method definition.
- `conversation_history_snapshot()` call expressions: 16, including forwarding implementations.
  Each reaches the Session implementation backed by `vrs_history()` or consumes an already
  VRS-derived `ContextManager`.
- Literal production `read_thread(... include_history: true ...)` family: 11 across core,
  app-server, thread-store, and the external migration utility. They load API/resume/fork/migration
  state. They do not dispatch it to a model; all later model sampling uses the VRS entrance.

### Prompt builders and direct request constructors

1. Normal sampling: `core/src/session/turn.rs:1407-1426` calls fallible
   `vrs_prompt_input(...).await?` inside the outer sampling/retry loop before `build_prompt`.
   `turn.rs:1313-1320` is the sole actual `Prompt` literal. The built prompt is passed through
   `turn.rs:1475-1491` and dispatched at `turn.rs:2463-2479`. Transport retries therefore rebuild
   `A(S_t, thread)`; no accumulated-history prefix is reused.
2. Startup prewarm: `core/src/session/startup_prewarm.rs:398-424`. `History` prewarm uses the same
   fallible VRS input. `Base` prewarm intentionally sends no conversation history.
3. Guardian request-budget accounting: `core/src/guardian/input_budget.rs:95-103,150-181` gets a
   VRS history, normalizes that assembly, and builds a request only to measure budget.
4. VRS overhead reservation: `core/src/session/vrs_input.rs:228-240` builds an empty-history prompt
   to measure wire overhead, then subtracts it before assembling VRS. It is not an alternate
   history source.
5. Prompt debug: `core/src/prompt_debug.rs:114-130` returns model-shaped diagnostic data and does
   not call a provider.

`core/src/client.rs:1162-1176,1295-1315` serializes the already-built prompt; it does not choose or
construct history. The separate Guardian-v2 sampler request at
`ext/guardian-v2/src/async_scorer/sampler.rs:191-215` receives its evidence through
`core/src/tools/lifecycle.rs:39-43,69`; the Session snapshot implementation at
`core/src/session/mod.rs:5125-5132` calls `vrs_history()`. Realtime startup similarly assembles VRS
at `core/src/realtime_context.rs:59-68` before passing it to
`core/src/realtime_conversation.rs:1736-1743`.

### `for_prompt` and rejected-audio projection

- Live assembly copies the current rejected file-ID set and file-audio durations into the fresh
  normalization manager at `core/src/session/vrs_input.rs:248-254`, then normalizes only the VRS
  items at `vrs_input.rs:256-264,311-318`.
- `core/src/context_manager/history.rs:647-678` runs file-audio projection as the last prompt
  normalization stage. `history_rejected_audio.rs:216-251` removes only audio parts whose
  `file_id` is rejected, drops a user message only when it becomes empty, and preserves all other
  items and aligned metadata.
- Path assembly reads the rollout once and unions every
  `turn_complete.error.rejected_audio_file_ids` at
  `core/src/session/vrs_input.rs:176-180,183-211` before installing/normalizing the assembly.
- The two Guardian budget projections at `guardian/input_budget.rs:95-103,150-158` consume VRS
  snapshots. `prompt_debug.rs:114-130` is the only non-dispatching projection.

### All production `clone_history()` consumers

The ten production expressions, with the forwarding helper counted, are:

- `core/src/guardian/feedback.rs:29`: failed-review diagnostic serialization.
- `core/src/guardian/review_session_setup.rs:151`: reads only `history_version`.
- `core/src/session/handlers.rs:389`: counts turn boundaries for shutdown telemetry.
- `core/src/session/mod.rs:1645`: numeric trace estimate.
- `core/src/session/mod.rs:1892`: DB-memory eligibility control.
- `core/src/session/mod.rs:5112`: private forwarding helper.
- `core/src/session/mod.rs:5443`: UI token-usage recomputation.
- `core/src/session/turn.rs:1457`: request-time accepted/rejected audio bookkeeping after
  `prompt.input` was already completed at line 1426; it is explicitly not model input.
- `core/src/tools/context.rs:149`: tool-origin item/window lookup.
- `core/src/prompt_debug.rs:114`: non-dispatching debug projection.

`core/src/test_support.rs:82` is the one public test-support-only diagnostic expression.
`core/src/tools/handlers/extension_tools.rs:517` is inside a `#[cfg(test)]` block. No production
clone carries accumulated response items into a provider request.

### Parent, sender, fork, resume, and stored-history paths

- `core/src/agent/history.rs:133-206` (`load_agent_model_context`) discards stored model-visible
  items and replaces them with resident-session VRS (`164-169`) or authorized path VRS
  (`171-185`). Its resume callers therefore do not replay stored model history as request input.
- `core/src/agent/history.rs:210-311` (`prepare_forked_history`) uses resident or path VRS.
  `core/src/agent/control/sender_context.rs:72-124` does the same for an authenticated sender.
  `core/src/thread_manager.rs:1503-1542` applies the same rule to the legacy subagent path.
- Guardian parent/reviewer paths use VRS at `core/src/guardian/review.rs:288-305`,
  `review_session.rs:266-295`, `review_session_setup.rs:322-338`, and
  `session/guardian_checkpoint.rs:11-37`.
- App-server sampling checks its parent revision from a fallible VRS snapshot at
  `app-server/src/thread_sample.rs:129-139,350-362`; the child's actual request still goes through
  normal `turn.rs` VRS sampling.
- Full-history store reads in `agent/history.rs:138-160` are immediately replaced by VRS. The
  legacy fork read at `thread_manager.rs:1834-1850` persists lineage before normal VRS sampling.
  App-server reads in `thread_processor.rs:3223-3257,3848-3867,4812-4835,4997-5048,5537-5557,
  5772-5797` serve API projection, resume payload/initial history, or fork persistence. The
  `load_latest_model_context` use at `5617-5648` reads multi-agent/settings metadata, not provider
  history. Thread-store helpers implement those reads; external-agent migration imports/persists
  them. None is a second model-input entrance.

### Extension `web.run`, cold resume, and inherited authorization

- `core/src/tools/handlers/extension_tools.rs:66-82` reserves native web-search fallback before
  conversion. `extension_tools.rs:238-245` then passes only fallible `vrs_history()` as the
  extension conversation history. A VRS error becomes a tool error; there is no clone fallback.
- `core/src/session/session.rs:1167` invokes `SearchOwner::restore` during initialization.
  `core/src/model_search.rs:147-159` scans `InitialHistory::{Resumed,Forked}` ResponseItem metadata
  for `native_search_fallback_used`; `history/src/lib.rs:423-429` confirms both initial-history
  variants expose their rollout items. `session/mod.rs:3940-3943` checkpoints the metadata before
  `session/mod.rs:4027` records the VRS history, so cold resume can restore it.
- The new test `core/tests/suite/guardian_retained_context.rs:826-880`,
  `inherited_instruction_authorization_after_cold_resume`, constructs a Forked inherited user
  envelope, persists it, resumes it, and checks the VRS snapshot's preserved user message and
  retained authorization. The audited production path supports that assertion.

Final T2 statement: every model-history consumer is VRS-derived or is not model input. Missing
sites: 0. Accumulated-history provider fallback: 0.

## 4d. T3 - fallback paths: 0; assembly failure is an error

- `core/src/session/vrs_input.rs:56-65` maps `OverWindow` to
  `ContextWindowExceeded`, `NotReady` to a fatal “request was not sent” error, and all other VRS
  failures to a fatal assembly error.
- Live assembly and D4-cache installation use `?` at `vrs_input.rs:68-95`; no previous assembly or
  `clone_history()` is substituted.
- Path assembly explicitly documents and implements no accumulated-history fallback at
  `vrs_input.rs:159-179`. Wait-task failure, VRS failure, rejected-audio rollout-read failure, and
  decode failure are returned.
- Budget failure, VRS failure, and an empty assembly stop the request at
  `vrs_input.rs:236-246`. `turn.rs:1414-1420` propagates this result before constructing/sending a
  prompt.
- Parent, sender, Guardian, and extension callers described in 4c propagate `Result`; none catches
  a VRS error and substitutes stored/live accumulated history.

## 4e. D3-double-prime - incremental request state is disabled

The two requested comments and their behavior are present. The old `session/context.rs` path no
longer exists in 0.169; its seam is now `session/step_context.rs`.

- `core/src/session/step_context.rs:58-60`: “request prefixes are rebuilt for every sample” is
  followed by `incremental_tools_feature() -> None`.
- `core/src/session/world_state.rs:60-65`: “do not inspect accumulated history for prefix state” is
  followed by an immediate `false`, before any state lock or history read.
- `core/src/tools/spec_plan.rs:1121-1128`: a literal
  `incremental_tools_enabled = false` is ANDed into `incremental_exec_enabled`, so the code-mode
  exec definition cannot be incrementally omitted.
- The normal request loop at `session/turn.rs:1407-1426` rebuilds VRS input and prompt prefix on
  every attempt. The incremental-tool scenarios therefore remain meaningful D3-double-prime
  regression tests and were not deleted by F3.

## 4f. T6 and V114-01 - no new serialization; generation boundary is sound

### No new FCC serialization structure

A production-source synchronization scan compared every lock/wait/barrier/channel/permit/order
candidate in the merged core/app-server/thread-store/rollout sources with both FCC 1.1.5
(`codex-fresh`) and upstream 0.169 (`codex-u169`). Candidates present in neither reference: 0.
Thus this port introduces no new mutex, wait, barrier, semaphore, channel, or serializing
mechanism. Existing upstream locks and FCC VRS publication atomics retain their prior roles.

### Every whole-list replacement

- `core/src/context_manager/history.rs:805-824` (`remove_first_item`) increments
  `usage_list_generation`, then calls `reset_last_usage_boundary()` after removing the logical
  first call/output unit.
- `history.rs:831-906` (`replace_assembled_with_suffix`) is the VRS D4-cache replacement. On a
  real list change, lines `898-902` install the list, increment the generation, and reset the
  boundary. An identical list returns at `893-897`; that is a read/no-op, not a replacement.
- `history.rs:916-935` (`replace_annotated`) installs a full annotated list, increments the
  generation at `931`, and resets the boundary at `932`.
- `replace_compacted`/`replace_compacted_history` do not exist in production.

`replace_assembled_with_suffix` changes only items/review/version/generation fields. It does not
assign or clear `retained_context`, `rejected_audio_file_ids`, or `file_audio_durations`; those
fields therefore survive a VRS cache refresh. Its host-only item metadata preservation is explicit
at `history.rs:842-875`. By contrast, the destructive restore API `replace_annotated` intentionally
clears retained context; it is not the VRS assembly refresh path.

### Request cut and response-generation comparison

- `core/src/session/turn.rs:1422` captures `(input_item_count, input_list_generation)` immediately
  after building the VRS input. `turn.rs:1475-1488` passes that exact pair into the sampling
  request, whose contract records the generation at `turn.rs:2356-2367`.
- Completed non-resampling usage supplies the captured generation at
  `turn.rs:3039-3048`; internal resampling uses `SpendingOnly` rather than pretending its stale
  request covered the current list.
- `core/src/session/mod.rs:5366-5388` passes the captured generation through
  `state/session.rs:354-368` to `ContextManager::update_token_info_for_list`.
- `core/src/context_manager/history.rs:1097-1114` compares response generation with the current
  `usage_list_generation`. On mismatch it reuses the previous safe covered count. On match it
  clamps via the known model-output boundary and request length; the later
  `saturating_sub` keeps the boundary inside the current list.

This is V114-01: a shorter replacement list plus usage from an older generation cannot move the
coverage boundary past the current list. The focused regression is
`context_manager/history_tests.rs::shorter_assembly_and_stale_usage_count_keep_the_boundary_in_range`;
test execution is reported by F2, not asserted by this F3 source audit.

## F3 files changed

- Production: `codex-rs/utils/critical-path/src/lib.rs`.
- Unit test aligned with the removed execution kind:
  `codex-rs/utils/critical-path/src/critical_path_tests.rs`.
- Audit tooling/evidence: `l3check/audit3_inventory.py`,
  `l3check/port_169/{inventory3.json,clone_history3.tsv,compression3.txt,socket3.txt}`, and this
  report.
- Progress log: `~/tmp/p116-work/report_F3.md`.

## Non-Cargo validation performed by F3

- `l3check/audit3_inventory.py` reran successfully after the final edits: 79 classified
  `clone_history()` expressions, zero listed executable compaction primitives, and zero core
  socket-path matches.
- The final full designated-pattern scan has 52 production compatibility lines, all covered by
  the classifications in 4b; the executable subset (`WorkKind::Compaction`, compaction phase/task,
  runner, and replacement primitives) is zero.
- `git diff --name-only --diff-filter=U` is empty. Tracked conflict open/close markers
  (`<<<<<<< ` / `>>>>>>> `) are zero.
- `git diff --check` over the F3-edited production, test, inventory, and report files is clean.
  The whole staged merge's `git diff --cached --check` is not clean because upstream-carried
  trailing whitespace exists in two snapshot fixtures and several patch fixture files; F3 did not
  alter those unrelated upstream artifacts.

