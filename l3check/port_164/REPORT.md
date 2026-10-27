# upstream 0.164.0-alpha.11.1 VRS port L3 report

Date: 2026-10-27 KST. Branch: `p113`. Merge parent pending: `MERGE_HEAD=6905ece`
(`rust-v0.164.0-alpha.11.1`). No commit, push, reset, checkout, or stash was performed.

## Result

- L3 build/test/audit is complete. The required release binary is
  `$HOME/tmp/codex-p113-target/release/codex`, SHA-256
  `52266b8a1533e1d5a50b9fde8b73a4061160d683462140981b98ad36e26d42f7`, and reports
  `codex-cli 0.164.0-alpha.11.1`.
- All 79 merge conflicts are resolved (`git ls-files -u` = 0): 20 delete/modify
  compaction files remain deleted and 59 content conflicts retain upstream's unrelated behavior
  while restoring the VRS invariants.
- Required build, unit tests, test compilation, regenerated experimental schema, and schema
  fixture checks pass. Q1 has zero executable compaction paths, Q2 has no accumulated-history
  model-input consumer, Q3 has no request fallback, D3-double-prime's two switches are false, and
  no new serial structure was introduced.
- Q4 mock-provider smoke passes 4/4. The specified prior-port-style live runner passes S1-S5:
  all VRS receipts succeed, all rollout JSONL copies are structurally valid, compaction events are
  zero, S2 remembers S1, S3/S4 perform the required tool work, and S4A/S4B overlap in time.
- A separate diagnostic observation is recorded under Q5/Q6: on the current accumulated
  `~/.codex/sessions` state, S5's first request began at 6.665 s, above the historical optional
  `gates.py` 5 s observation. The same current-state run on the prior alpha.17.2 VRS binary began
  at 7.163 s, so this is not an 0.164-port regression. The user-specified prior runner
  `~/tmp/codex-port-work/smoke5.sh` does not use that latency value as an S5 pass condition.

## 4a. Conflict resolutions (79)

The authoritative list is `.git/MERGE_MSG`; it contains exactly 79 conflict paths. Reports
`~/tmp/p113-work/report_A.md`, `report_B.md`, and `report_C.md` were reconciled with the final
index and the L3 fixes below.

### Delete/modify conflicts kept deleted (20)

These files contain only removed local/remote/automatic/background/token-budget compaction,
new-context-window execution, or tests of those paths. Keeping them deleted implements D7/I1;
no unrelated helper remained trapped in them.

- App-server (1): `app-server/tests/suite/v2/compaction.rs`.
- Core implementation (11): `core/src/compact.rs`, `compact_model_fallback.rs`,
  `compact_remote_history.rs`, `compact_remote_v2.rs`, `compact_remote_v2_attempt.rs`,
  `compact_remote_v2_image_budget_tests.rs`, `compact_remote_v2_images.rs`, `compact_tests.rs`,
  `context/compaction_summary.rs`, `tasks/compact.rs`, and
  `tools/handlers/new_context_window.rs`.
- Core integration tests (6): `core/tests/suite/compact.rs`, `compact_program_tests.rs`,
  `compact_remote.rs`, `compact_resume_fork.rs`, `step_settings_compaction.rs`, and
  `window_headers.rs`.
- Guardian-v2 parent-compaction implementation/tests (2):
  `ext/guardian-v2/src/async_scorer/parent_compaction.rs` and
  `parent_compaction_tests.rs`.

### Content conflicts resolved (59)

The groups below enumerate every remaining conflict path; the counts sum to 59.

- Workspace/dependency policy (3): `Cargo.toml`, `Cargo.lock`, `deny.toml`. The 0.164 workspace
  and lock graph are retained, with the existing `vrs` member/`codex-vrs` edge and required
  license exceptions restored.
- App-server/protocol (5):
  `app-server-protocol/schema/precomputed/app-server-exports-experimental.json.zst`,
  `app-server-protocol/src/protocol/v2/thread.rs`,
  `app-server/src/request_processors/thread_lifecycle.rs`,
  `app-server/src/request_processors/thread_processor.rs`, and
  `app-server/tests/suite/v2/thread_fork.rs`. Upstream prediction/unload/MCP contracts remain;
  prediction forks use the referenced VRS lineage, live-history release remains bounded, and
  `thread/compact/start` remains invalid.
- Core agent/config/context/session/tool seams (21):
  `core/src/agent/control/sender_context.rs`, `agent/control/spawn.rs`, `config/mod.rs`,
  `config/windows_sandbox_config.rs`, `context/token_budget_context.rs`, `hook_runtime.rs`,
  `lib.rs`, `session/mod.rs`, `session/rollout_reconstruction.rs`, `session/session.rs`,
  `session/startup_prewarm.rs`, `session/step_activation_tests.rs`, `session/step_context.rs`,
  `session/tests.rs`, `session/turn.rs`, `session/turn_input.rs`, `state/session.rs`,
  `thread_manager.rs`, `tools/executed_tool_calls/request_metadata.rs`, `tools/registry.rs`, and
  `turn_metadata_tests.rs`. Upstream non-compaction behavior is retained; every model/fork input
  seam uses VRS, resume does not replay rollout history into the live model history, D3-double-
  prime disables both incremental-prefix switches, and removed compact/new-window APIs stay out.
- Core Guardian seams (9): `core/src/guardian/input_budget.rs`, `input_budget_tests.rs`, `mod.rs`,
  `request_budget.rs`, `review_request.rs`, `review_session.rs`, `review_session_setup.rs`,
  `tests.rs`, and `session/guardian_checkpoint.rs`. Budgeting and reviewer reuse keep upstream
  behavior over VRS assemblies; compaction recovery is absent; failures discard/fail closed.
- Core integration tests (9): `core/tests/suite/code_mode.rs`, `guardian_context_budget.rs`,
  `guardian_environments_tests.rs`, `guardian_retained_context.rs`, `guardian_review.rs`,
  `mod.rs`, `pending_input.rs`, `scenarios.rs`, and `tools.rs`. Non-compaction upstream coverage is
  retained; only tests whose subject is deleted compaction were removed or explicitly ignored.
- Exec server (1): `exec-server/src/environment.rs`; the upstream remote environment RPC timeout
  is retained unchanged and is unrelated to VRS/compaction.
- Guardian extensions (8): `ext/guardian-reviewer/src/pool.rs` plus guardian-v2
  `classification.rs`, `conversation.rs`, `conversation_tests.rs`, `decisions.rs`,
  `decisions_tests.rs`, `extension_tests.rs`, and `observation.rs`. Upstream rollback/session
  lifecycle remains; `parent_compaction` is removed and evidence comes from VRS snapshots.
- Recorder/client integration (3): `rollout/src/recorder.rs`,
  `thread-manager-sample/src/main.rs`, and `tui/src/app_server_session/workspace_roots_tests.rs`.
  The 0.164 boxed session metadata and workspace event shape are retained over the existing VRS
  reserved-line publication; sample config does not restore compaction settings.

### L3 fixes after text-conflict resolution

- R1: `core/src/session/startup_prewarm.rs:395-422` again obtains History input from
  `vrs_prompt_input`, passes the already-typed `BaseInstructions` directly, and applies
  `check_prompt_window` after `build_prompt`.
- R2: `core/src/session/mod.rs:1793-1844` reconstructs Guardian/world/window/previous-turn state
  but installs `Vec<ResponseItemEnvelope>::new()` as live history. It does not replay or prepare
  rollout image/audio history; the subsequent VRS restore/request assembly owns model history.
- R3 is audited under Q2 below: the pool rollback handoff consumes a snapshot captured by
  `guardian_fork_history()` from `vrs_history()`, never `clone_history` or a compaction checkpoint.
- Processed report-C handoffs: a reserved zero-byte rollout identity is distinguished from
  materialized metadata; its recorder assertion now expects that identity; thread/sample tests
  use paginated referenced forks without compaction scaffolding; the Guardian-v2 app-server
  compaction-only module was removed.
- Compile repairs preserved semantics: adapted `LivePlainReader`, boxed 0.164 session metadata,
  removed stale compaction-only calls, propagated fallible VRS snapshots, reconciled rollout
  dynamic-tools/sender retained-context types, removed duplicate inter-agent persistence, restored
  VRS publication completion, and fixed 0.164 `ThreadNotFound`/executed-tool-call API changes.
- The Q2/Q3 audit found one additional D5 defect in
  `core/src/agent/control/sender_context.rs:80-118`: nonresident sender store/VRS errors and timeout
  were converted to empty evidence. Only genuine not-found/no-path/ineligible-source cases now
  mean “no sender context”; store/VRS errors and timeout propagate as `CodexErr`.

## 4b. Q1 — executable compaction paths: 0

Method: scan every tracked production Rust source with the task's complete regular expression;
exclude test files/modules and only the named exceptions (`tools/src/json_schema/compaction.rs`,
`*_without_compaction`, `world_state/compact_permissions*`, TUI `exec_cell/compact.rs`). The scan
found 25 raw symbol matches and zero execution references after classification.

The 25 allowed compatibility matches are:

- `config/src/schema.rs:102-106` (2): exports the accepted `AsyncCompaction` config schema.
- `core/src/config/mod.rs:667-669,3358-3365,4485` (6): explicitly deprecated parsing and range
  validation for the old `features.async_compaction` threshold. There is no runtime consumer.
- `features/src/feature_configs.rs:190-193,245-246,574-584` (6): accepted Guardian parent and
  async-compaction TOML shapes/telemetry keys only.
- `features/src/lib.rs:20,439,903-938,1905,2120-2121` (9 matches; the declaration at line 903
  contains two matched symbols): feature/config registry compatibility. No compaction task or
  call target is present.
- `protocol/src/openai_models/guardian_v2.rs:41-43` (2): wire-compatible optional fields. Production
  search finds no consumer of `reuse_parent_compaction` or `max_parent_compaction_tokens`.

Therefore every remaining match is configuration/protocol compatibility, not compaction
execution. The live Q4/Q5 rollout scans independently found zero `compacted`,
`ContextCompacted`, or `context_compacted` events.

## 4c. Q2 — one model-input entrance; complete source inventory

### Syntactic census

Tests were excluded. Root-level test support was retained in the census when compiled in normal
code, then classified explicitly.

- `build_prompt(` has 5 call sites plus its single definition/literal:
  - `core/src/session/turn.rs:1234-1250`: the only normal sampling dispatch. Every first attempt
    and transport retry recomputes `vrs_prompt_input(...).await?` before `build_prompt`.
  - `core/src/session/startup_prewarm.rs:395-422`: History prewarm uses `vrs_prompt_input`; Base
    prewarm is intentionally empty. Window overflow is an error.
  - `core/src/guardian/input_budget.rs:100-127`: builds a request only to estimate the Guardian
    budget from `vrs_history`; this is not an alternate sampling history.
  - `core/src/session/vrs_input.rs:182-204`: builds an empty-input prompt only to reserve real wire
    overhead before VRS assembly; it contributes no history.
  - `core/src/prompt_debug.rs:102-121`: debug API projection only; it returns `prompt.input` and
    does not dispatch a model request. This is the sole live-history-shaped exception required by
    design A5.
  - `core/src/session/turn.rs:1147-1172` contains the only model `Prompt { ... }` literal. The other
    textual `Prompt {}` hits are hook/protocol enum variants, not `client_common::Prompt`.
- `for_prompt` has 2 production consumers:
  `core/src/session/vrs_input.rs:258-266` normalizes only freshly assembled VRS items; the other,
  `core/src/prompt_debug.rs:107-121`, is the non-dispatching debug API above.
- `clone_history()` has 11 raw hits outside files named as tests; one is inside the
  `#[cfg(test)]` block of `tools/handlers/extension_tools.rs` and is excluded. The remaining 10
  have zero model-request sinks:
  - `guardian/feedback.rs:29-43`: opt-in failed-review feedback serialization.
  - `guardian/review_session_setup.rs:166-168`: reads only `history_version` for reuse bookkeeping.
  - `prompt_debug.rs:107-121`: debug API result, no sampling dispatch.
  - `session/handlers.rs:359-364`: shutdown turn-count telemetry.
  - `session/mod.rs:1554-1559`: numeric token estimate; its only production caller is trace
    telemetry at `session/turn.rs:502-507`.
  - `session/mod.rs:1771-1781`: detects an external-context marker only to disable DB memory
    extraction eligibility; no history payload is sent.
  - `session/mod.rs:4587-4589`: forwarding helper to the private live D4 cache; it has no sink by
    itself.
  - `session/mod.rs:4895-4905`: token-usage recomputation only (production has no caller).
  - `core/src/test_support.rs:80-83`: public test-support diagnostic helper; no production caller.
  - `tools/context.rs:96-121`: finds only the originating tool-call ID/window for approval and
    Guardian control metadata; it does not forward response text.

This makes the model-input result precise: one normal generation entrance
(`turn.rs:1234-1250`), rebuilt from VRS on every attempt; four ancillary prompt builders, of which
two are VRS-based admission/prewarm, one has deliberately empty history, and one is a non-model
debug projection. There is no `clone_history` -> model request path.

### Parent, sender, fork, and resume entrances

Seven parent/sender families plus resume were traced end to end:

1. Guardian parent A10/A13: `core/src/guardian/review.rs:208-224` captures `vrs_history()` or
   returns a prompt-build error; `guardian/review_session.rs:435-456` uses that retained VRS
   snapshot to build the reviewer package.
2. Guardian reviewer A14/R3: `core/src/session/guardian_checkpoint.rs:11-37` constructs
   `guardian_fork_history()` from fallible `vrs_history()`; `guardian/review_session_setup.rs:228-289`
   captures and commits it; `ext/guardian-reviewer/src/pool.rs:201-236,309-312` passes only the
   previously committed snapshot to a replacement fork after rollback. No `clone_history`,
   accumulated parent history, or compaction checkpoint enters the handoff.
3. Ordinary agent full-history A20: `core/src/agent/control/spawn.rs:1117-1132` obtains the parent
   items from `vrs_history()` and fails on assembly error before making the child history.
4. V9-01 legacy subagent: `core/src/thread_manager.rs:1250-1291` uses resident `vrs_history()` or,
   for an unloaded parent, authorized `vrs_history_for_path()`; absence/path/assembly errors are
   returned. This closes the fork8 omission.
5. Sender A10/A13: `core/src/agent/control/sender_context.rs:68-118` uses the resident thread's
   fallible `conversation_history_snapshot()` (defined as `vrs_history()` at
   `session/mod.rs:4601-4608`) or authorized `vrs_history_for_path()` for a nonresident sender.
   The latter now propagates timeout/store/VRS failures.
6. Prediction/reference fork V8-01: `app-server/src/request_processors/thread_processor.rs:5344-5380`
   requires a paginated source and prepares a reference marker; `core/src/thread_manager.rs:1667-1715`
   preserves only lineage plus non-model state. The child sampling turn then enters the single
   `vrs_prompt_input` path.
7. New `thread/sample`: `app-server/src/thread_sample.rs:123-126` obtains a fallible VRS snapshot
   for the source revision/MCP decision and lines 208-225 use the same reference-fork path; the
   sample turn at lines 236-261 enters normal VRS sampling. It never installs the store's latest
   model context as a direct prompt.
8. Resume D4/R2: `core/src/session/mod.rs:1793-1844` installs an empty live response history while
   retaining Guardian/world/window/settings reconstruction. `session/vrs_input.rs:285-299` restores
   the D4 cache from VRS; regardless of that best-effort cache restore, the next model request
   reassembles through `vrs_prompt_input` and cannot read the cache as fallback.

The other §13.1 new history-copy family was async/background compaction and is absent under Q1.
Thus the §13.2 new site set and V9-01 are all covered, with zero missing model-input sites.

## 4d. Q3 — fallback paths: 0

- Live assembly: `core/src/session/vrs_input.rs:95-126` returns recording/path/wait/store/decode
  failures. `NotReady` waits through the existing bounded one-second cancellation point and any
  wait failure is returned; there is no alternative history source.
- Path assembly: `core/src/session/vrs_input.rs:156-175` has the same error-return behavior and no
  accumulated-history fallback.
- Decode guard: `core/src/session/vrs_input.rs:135-153` rejects malformed, unknown, and all
  compaction record variants before a request can be sent.
- Prompt admission: `core/src/session/vrs_input.rs:182-213` maps VRS failure to `CodexErr`, rejects
  empty assembly and context overflow, and returns only normalized assembled items.
- Dispatch propagation: `core/src/session/turn.rs:1234-1240` and
  `session/startup_prewarm.rs:401-406` use `await?`; Guardian parent/snapshot and fork sites listed
  in Q2 also return/convert the error rather than substituting live history.
- `restore_history_from_vrs` at `session/vrs_input.rs:285-290` is a non-model D4 cache refresh. Its
  logged best-effort failure cannot become a request fallback because normal sampling always calls
  `vrs_prompt_input` again.
- The audit-found sender defect is fixed at `agent/control/sender_context.rs:80-118`: timeouts and
  store/VRS failures now fail turn-input admission. Only authenticated “not found”, ineligible
  source, or no rollout path yields no optional sender fragment.

## 4e. D3-double-prime

- `core/src/session/step_context.rs:50-55`: `incremental_tools_enabled()` returns literal `false`.
- `core/src/session/world_state.rs:43-50`: `current_window_uses_incremental_tools()` returns literal
  `false` before reading history.
- The consumers are `guardian/input_budget.rs:119`, `session/startup_prewarm.rs:418-420`,
  `session/turn.rs:1218-1221`, `session/vrs_input.rs:189-195`, and the non-model debug projection.
  Therefore `build_prompt(..., false)` always supplies current step instructions/tools/output
  format and no incremental prefix is recorded in VRS history.
- The D3-double-prime incremental-tool scenario was not deleted:
  `prediction_fork_appends_mcp_removal_without_rewriting_history` remains compiled. Only its
  forbidden `AutoCompactionDisabled` setup was removed; the expected behavior was not rewritten.

## 4f. Q6 — no new serial structure in the port

- `git status`/`git diff HEAD` show no change under `vrs-lib7/` or `codex-rs/vrs/`. The current
  `vrs_lib.cpp` and Rust FFI are byte-identical to fork8. Both static libraries have SHA-256
  `c141357f8116c7429c33b187d79c24b99b66a957b92c823ce515f32f14b6c255`.
- The port-authored model/fork seams add no `Mutex`, `RwLock`, `Condvar`, `Barrier`, `OnceLock`,
  CAS, writer flush, ready poll, or process-global ordering. `spawn.rs:1117-1124` explicitly reads
  VRS without a rollout-writer barrier.
- Existing structures retained rather than introduced by this port:
  - `session/vrs_input.rs:112-123,162-171` retains fork8's VRS `NotReady` wait behavior.
  - `agent/control/sender_context.rs:80-114` retains upstream's five-second authorization/store
    timeout; the L3 fix only changes swallowed failures into returned errors.
  - `app-server/src/thread_sample.rs:128-131` retains upstream's parent rollout flush used by its
    source-consistency protocol. VRS source revision is captured before it, and no new VRS lock or
    barrier was added.
  - `thread_manager.rs:1652-1715` uses the already-designed active-turn marker for a referenced
    fork; Guardian pool locks/rollback atomics are upstream lifecycle structures.

Static Q6 therefore passes: the 0.164 port adds no serialization mechanism and does not alter
libvrs/FFI/assembly semantics. The current-home S5 timing observation is recorded in Q5 below and
was reproduced, more slowly, by the prior binary.

## Required build, tests, and schema

All Cargo commands used the mandated isolated target and `taskset -c 0-11`; `VRS_LIB_DIR` was
unset.

- Release build PASS:
  `env -u VRS_LIB_DIR CARGO_TARGET_DIR=$HOME/tmp/codex-p113-target taskset -c 0-11 $HOME/.cargo/bin/cargo build --release -p codex-cli`.
- Version PASS: `$HOME/tmp/codex-p113-target/release/codex --version` ->
  `codex-cli 0.164.0-alpha.11.1`.
- Unit tests PASS:
  `cargo test -p codex-prompts -p codex-models-manager`; prompts 46 passed, models-manager 56
  passed.
- Core test compilation PASS:
  `RUST_MIN_STACK=33554432 cargo test -p codex-core --no-run`.
- App-server test compilation PASS:
  `RUST_MIN_STACK=33554432 cargo test -p codex-app-server --no-run`.
- Schema regeneration PASS: `just write-app-server-schema --experimental`. The merged
  `app-server-exports-experimental.json.zst` is 167485 bytes, SHA-256
  `7e060d4789f45e51c8e18d12e1ba377d5026650eddf732fcf3597a1742ca55fa` (and deliberately differs
  from the temporary upstream-only conflict artifact `6fcc...`). Focused
  `schema_fixtures_tests` passed 4/4: TypeScript, JSON, stable precomputed, and experimental
  precomputed; the writer test remains intentionally ignored by upstream.

Changed/removed tests are limited to compaction semantics:

- Removed pure-compaction `turn_metadata_state_overlays_compaction_only_on_compaction_requests`
  and the stale `window_headers` module declaration/source.
- Ignored only the two transcript variants of
  `guardian_attributes_local_compaction_to_assistant`, because they execute deleted local
  compaction.
- Other compile adaptations retained their product assertions: fallible VRS snapshot callers,
  upstream `ResponseItem` fields, stable environment tools, model-change initial context, Guardian
  delta history, sender non-blocking completion, reasoning override recovery, cross-host sender
  context, and environment-backed tool opt-in all remain compiled.
- The D3-double-prime incremental/prediction test named above remains present and compiled.

## Q4 mock-provider release smoke

Command form:
`RELSMOKE_DIR=$PWD/l3check/port_164/release1 bash l3check/release1/run.sh $HOME/tmp/codex-p113-target/release/codex`.

Result: PASS 4/4. `gpt-6-astra` and `gpt-5.6-sol` model-provenance instructions preserve all clean
paragraphs and contain zero compaction guidance; resume also has zero forbidden sentences; Custom
instructions remain byte-verbatim and intentionally retain their user's compaction sentence.
Temporary rollouts contain zero compaction items. Evidence:
`l3check/port_164/release1_fcc113.txt` and `l3check/port_164/release1/`.

The first rerun's S_b mismatch was a stale personal-home fixture selection problem, not a product
result. `l3check/release1/run.sh` now deterministically takes the just-created complete
model-provenance rollout and appends the forbidden resume sentence to that copy; expectations were
not weakened. The corrected full-template run is the 4/4 result above; the failed fixture run is
preserved as `release1_fcc113_rerun.txt`.

## Q5 live backend smoke, S1-S5

Binary: `$HOME/tmp/codex-p113-target/release/codex` (hash above). The installed Home app 26.1021
companion was exposed only inside the isolated release target as
`release/codex-code-mode-host -> /usr/lib/chatgpt/resources/codex-code-mode-host`; both paths hash
to `8ae7c0ba6e1ddfb3b1b6210e0fd1b0860bb2c90d8b4ecfad44f27351b61b1c8a`. No `~/.codex`
configuration was changed. `l3check/smoke4/run.py` gained explicit output/work roots and copies the
matched rollout into each evidence directory.

Command form (each process remained inside CPU 0-11):

`taskset -c 0-11 python3 l3check/smoke4/run.py CASE --binary $HOME/tmp/codex-p113-target/release/codex --timeout 300 --output-root l3check/port_164/smoke4-live --work-root l3check/port_164/smoke4-work [--resume THREAD_UUID]`.

| Case | Result | Thread / proof | VRS receipts | Tools / files | Rollout checks |
|---|---|---|---:|---:|---|
| S1 (`S1_retry1`) | PASS | `01a17b23-a5b7-7232-b9f0-16c9f8000581`; final exactly `hello` | 4/4 | 1 read | parse/NUL/compaction failures 0 |
| S2 (`S2_retry1`) | PASS | resumed the exact S1 UUID; recalled both `a.txt` question and `hello` answer | 2/2 | 0 | failures 0; same thread UUID |
| S3 | PASS | 20 files all exact, 210 lines total | 34/34 | 11 calls | failures 0 |
| S4A | PASS | unique thread `...0689...`; 20 files/210 lines | 34/34 | 11 calls | failures 0 |
| S4B | PASS | unique thread `...066d...`; 20 files/210 lines | 34/34 | 11 calls | failures 0 |
| S5 | PASS by specified `smoke5.sh` gate | final exactly `hello` | 1/1 | 0 | failures 0 |

S4A/S4B began at the same millisecond and overlapped for 56.875 seconds; their cwd, thread UUID,
rollout copy, and receipt `thread` values are distinct. Across the accepted six cases: VRS
receipts 109/109 successful, VRS error lines 0, event errors 0, command failures 0, JSON parse
failures 0, NUL bytes 0, non-increasing ordinals 0, and compaction events 0.

Evidence is self-contained under `l3check/port_164/smoke4-live/{S1_retry1,S2_retry1,S3,S4A,S4B,S5}/`:
each directory contains `command.json`, `result.json`, `stdout.jsonl`, `stderr.txt`, `vrs.jsonl`,
and `rollouts/*.jsonl`. Work files are under `l3check/port_164/smoke4-work/`.

Two invalid setup attempts are preserved rather than hidden: initial S1 lacked the required
0.164 code-mode host companion and answered `읽기실패`; initial S2 passed the case label instead
of S1's UUID and therefore started a new thread. After correcting only those execution inputs, the
accepted S1/S2 cases above passed.

Latency observation: accepted S5 had VRS assembly 3.974433 s and request start 6.665 s; a repeat
was 4.723380 s / 6.602 s. Under the identical current Home/session state, prior alpha.17.2 binary
hash `9f78dea7...` measured 4.432423 s / 7.163 s
(`smoke4-live/S5_baseline_a17/`). This isolates the >5 s historical diagnostic to current shared
store startup/state rather than the 0.164 merge. It does not change the specified S1-S5 functional
gate, but it should be re-measured in L4 deployment conditions before claiming the full §13.0 Q6
latency clause.

## Boundaries

- No file under `vrs-lib7/` or `codex-rs/vrs/` was changed.
- No personal rollout, setting, credential, running app, or other worktree was modified or
  deleted. Live tests read the existing authenticated configuration and wrote only ordinary new
  test sessions plus the requested evidence copies.
- This is a local, uncommitted merge result. Publication, app replacement, terminal deployment,
  full app-server GUI smoke, Q7, and commit/push remain outside this D3 execution.
