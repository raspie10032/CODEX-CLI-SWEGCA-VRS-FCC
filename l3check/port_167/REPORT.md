# upstream 0.167.0-alpha.3.2 VRS port L3 report

Date: 2026-11-11 KST. Branch: `p114`. Merge parent pending:
`MERGE_HEAD=c40729ea` (`rust-v0.167.0-alpha.3.2`). No commit, push, reset,
checkout, stash, or new merge was performed.

## Result

- The text resolution, required build/test compilation, generated-file checks, and the a-f
  source audits are complete. The final release binary is
  `$HOME/tmp/codex-p114-target/release/codex`; its final version/hash are recorded in the build
  section below.
- `.git/MERGE_MSG` contains exactly 80 conflict paths: 63 content conflicts plus 17
  modify/delete conflicts whose compaction-only files remain deleted. `git ls-files -u` is empty.
- R1 has zero executable compaction references. R2 has one normal sampling entrance and no
  accumulated-history-to-request route. R3 has zero request fallback: VRS/store/decode failures
  are returned. Both D3-double-prime switches return literal `false`. No new lock, wait, barrier,
  or ordering mechanism was introduced.
- Q4 could not reach the product assertion in this managed sandbox: Python was denied creation
  of the loopback mock-provider socket with `EPERM`. All four cases therefore timed out before a
  request reached the provider. This is reported as environment-blocked, not as 0/4 product
  evidence. The full output is `release1_fcc114.txt`.
- Real-backend smoke S1-S5 was deliberately not run; the task assigns that networked gate to the
  coordinator.

## 4a. Conflict resolutions (63 content + 17 delete/modify)

The authoritative path list is `.git/MERGE_MSG`. Reports `~/tmp/p114-work/report_A.md` through
`report_E.md` were reconciled with the final index/worktree and the build-stage fixes below.

### Delete/modify conflicts kept deleted (17)

Every path in this set is a compaction/new-context-window implementation, a test whose subject is
that deleted behavior, or a dedicated snapshot. No unrelated helper remained trapped in them.

- App-server (1): `app-server/tests/suite/v2/compaction.rs`.
- Core implementation and unit tests (9): `core/src/compact.rs`, `compact_remote_v2.rs`,
  `compact_remote_v2_attempt.rs`, `compact_remote_v2_image_budget_tests.rs`, `compact_tests.rs`,
  `session/async_compaction.rs`, `session/async_compaction_tests.rs`,
  `tools/handlers/new_context_window.rs`, and `new_context_window_spec.rs`.
- Core integration tests (2): `core/tests/suite/compact.rs` and `compact_remote.rs`.
- Core scenario snapshots (4):
  `astra_async_compaction_with_live_suffix.snap`,
  `incremental_tools_resume__legacy_resume_remote_compaction.snap`,
  `prediction_fork_preserves_context_above_compaction_threshold.snap`, and
  `retained_tool_outputs__retained_tool_output_survives_compaction_and_resume.snap` under
  `core/tests/suite/snapshots/all__suite__scenarios__*`.
- Guardian-v2 (1): `ext/guardian-v2/src/async_scorer/parent_compaction.rs`.

### Content conflicts resolved (63)

The groups below enumerate every content-conflict path; the counts sum to 63.

- Workspace/configuration policy (4): `.cargo/audit.toml`, `Cargo.toml`,
  `config/src/config_toml.rs`, and `deny.toml`. Upstream's 0.167 graph/GCP configuration and
  current advisory policy were retained together with the existing `vrs` member and inert
  compatibility parsing for removed compaction keys.
- App-server, generated protocol, and Python binding (9):
  `app-server-protocol/schema/precomputed/app-server-exports-{experimental,stable}.json.zst`,
  `app-server-protocol/schema/typescript/v2/Account.ts`,
  `app-server/src/request_processors/{thread_lifecycle,thread_processor}.rs`,
  `app-server/src/thread_sample.rs`, app-server tests `account_gcp.rs` and `thread_fork.rs`, and
  `sdk/python/src/openai_codex/generated/v2_all.py`. Upstream GCP, attach/source, sample, goal,
  and fork behavior remains; reference forks and snapshots fail closed through VRS; compact RPC
  remains unavailable.
- Core production/unit-test seams (27):
  `agent/control/{sender_context,spawn,user_authorization}.rs`, `codex_thread.rs`, `config/mod.rs`,
  `context_manager/history.rs`, Guardian `input_budget.rs`, `input_budget_tests.rs`, `prompt.rs`,
  `request_budget.rs`, `review.rs`, `review_session.rs`, `review_session_context.rs`,
  `review_session_setup.rs`, `review_session_tests.rs`, `hook_runtime.rs`, session `mod.rs`,
  `rollout_reconstruction.rs`, `startup_prewarm.rs`, `tests.rs`, `turn.rs`, `turn_input.rs`,
  `tasks/mod_tests.rs`, `thread_manager.rs`, `tools/spec_plan.rs`, `turn_timing.rs`, and
  `turn_timing_tests.rs`. Upstream non-compaction behavior is retained; model/fork/reviewer input
  uses VRS, resume does not replay the D4 cache into a request, and executable compaction stays
  disconnected.
- Core integration tests/snapshots (8): `client.rs`, `cyber_access_program.rs`, `gcp.rs`,
  `guardian_context_budget.rs`, `pending_input.rs`, `scenarios.rs`,
  `all__suite__gcp__gcp_model_picker.snap`, and
  `all__suite__scenarios__astra_kickoff_original_history.snap`. Non-compaction 0.167 coverage was
  retained; only compaction-subject cases/fixtures were removed or explicitly ignored.
- Guardian-v2 (8): `authorization.rs`, `classification.rs`, `decisions_tests.rs`,
  `extension_tests.rs`, `observation.rs`, `sampler.rs`, `sampler_tests.rs`, and `startup.rs`.
  0.167 reservation/conversation lifecycle remains, while parent-compaction selection/hash/reuse
  is absent and failures in the core VRS authorization snapshot propagate.
- Provider/recorder/audio (7): model-provider-info `lib.rs` and
  `model_provider_info_tests.rs`; model-provider `provider.rs`, `gcp/mod.rs`, and
  `gcp/gcp_tests.rs`; `rollout/src/recorder.rs`; and `utils/audio/src/lib.rs`. Upstream GCP and
  audio API changes are retained over FCC's reserved VRS ordinal/insert/written publication.

### Build-stage fixes after conflict text resolution

- F1/F2 processed every handoff in reports A-E: fallible `ScoreAuthorization` and Guardian VRS
  snapshots propagate errors; removed review-policy/reviewer-selection/parent-compaction API is
  gone; configuration compatibility remains without a runtime consumer; compile drift in tests,
  0.167 model metadata, and async image normalization was repaired without weakening assertions.
- The R2 audit found one new 0.167 direct Guardian entry at
  `core/src/codex_thread.rs:920-935`. It had read the accumulated `clone_history()` cache before
  reviewing an injected exec call. It now calls fallible `vrs_history()`, maps the error to
  `CodexErr`, and passes that exact assembly to `review_tool_call`.
- The R1 audit renamed the general usage accounting helper to
  `estimated_unreported_history_tokens` at `core/src/context_manager/history.rs:992,1006` so the
  prohibited compaction-era name has no production reference; the formula is unchanged.
- `core/src/session/step_activation_tests.rs` no longer contains the case asserting that the
  deleted `max_parent_compaction_tokens` setting changes Guardian authority. This was an execution
  semantics test, not a compatibility-parser test. Other non-compaction classification cases
  remain unchanged and compile.
- The broader semantic audit found the unused automatic-compaction fallback fragment type
  `AutoCompactFallbackPrompt` in `core/src/context/token_budget_context.rs`; it had no callers and
  was removed. Historical wire variants, decoder rejection, and config parser compatibility were
  retained.

## 4b. R1 - executable compaction paths: 0

Method: scan tracked `codex-rs` Rust, generated config schema, and model catalog with the full
task regular expression; exclude test code and only the named path/symbol exceptions. There are
69 raw token matches on 68 lines. They classify as 21 test-only compatibility matches and 48
production compatibility/schema/catalog matches; executable references are zero.

The 48 allowed non-execution matches are:

- `protocol/src/openai_models/guardian_v2.rs:42,44` (2): optional wire-compatible catalog fields;
  no core/extension runtime reads them.
- `features/src/feature_configs.rs:190-193,245-246` (6): deserialization and telemetry-key shape
  for old Guardian parent-compaction configuration.
- `features/src/lib.rs:20,419,479,945-980,2049-2050,2283-2284` (11 token matches): feature/config
  registry declarations only. Search finds no task, handler, or model-input consumer.
- `core/src/config/mod.rs:669-671,3392-3399,4545` (6): explicitly deprecated
  `[features.async_compaction]` parsing and range validation; the value is not passed into a
  compaction runner.
- `config/src/schema.rs:111-115` (2): generated-schema export for accepted old config.
- `core/config.schema.json:356,888-889,1080,1777,1783,2197,2215,7599-7600,7791` (11): generated
  serialization compatibility only.
- `models-manager/models.json:121-122,295-296,468-469,645-646,812-813` (10): null optional
  Guardian catalog fields; no execution consumer remains.

The 21 excluded test matches are `features/src/tests.rs` (6),
`core/src/config/config_loader_tests.rs` (12), and
`core/src/context_manager/history_tests.rs` (3). They validate parsing or pass documented `None`
arguments; they do not create a compaction task. `ResponseItem`/`RolloutItem` historical
compaction variants remain only for wire exhaustiveness and fail-closed decode/filtering, e.g.
`session/vrs_input.rs:143-150` rejects all such assembled records before a request.

A second semantic sweep covered names outside the supplied expression. In particular,
`core/src/state/auto_compact_window.rs` is byte-identical to FCC 1.1.3. Its reachable
`AutoCompactWindowIds`, restore, and reminder-claim operations preserve persisted context-window
identity and one-shot token-budget reminders; they do not rotate a window or invoke compaction.
Its server/estimated prefill snapshot methods have no non-test caller (the compiler also reports
them dead). Likewise, `model_auto_compact_token_limit` and `auto_compact_fallback_*` survive only
in config/model-catalog parsing and validation. The unused executable fallback fragment itself was
removed during this audit.

The final zero statement is therefore: no `run_*compact`, compact task/handler, context-window
reset, parent/reviewer compaction reuse, compact budget/fallback, or compact hook caller is
reachable in production. Every surviving match above is a parser/schema/catalog compatibility
surface, not compaction execution.

## 4c. R2 - one model-input entrance; complete source inventory

### Mechanical census

`l3check/audit3_inventory.py` was adapted to this tree: its library/source inputs now resolve to
the unchanged checked-in `vrs-lib7` artifacts, its old hazard-slot spelling was updated, its
fail-on-unknown clone table gained the two newly exposed metadata/token-accounting consumers, and
its outputs are isolated under `l3check/port_167/`. It completed successfully and recorded 78
`clone_history()` expressions: 68 test-only and the ten non-test entries classified below. The
machine-readable evidence is `inventory3.json`, `clone_history3.tsv`, `compression3.txt`, and
`socket3.txt`. The full task-pattern R1 scan and every production candidate's sink were also
checked independently rather than treating that older script's narrower symbol list as complete.

- `build_prompt(` has five production calls plus one definition/literal:
  - `core/src/session/turn.rs:1312-1347`: the sole normal sampling dispatch. Every initial attempt
    and transport retry calls `vrs_prompt_input(...).await?` inside the retry loop before
    `build_prompt` and window admission.
  - `core/src/session/startup_prewarm.rs:397-423`: History prewarm uses the same fallible
    `vrs_prompt_input`; Base prewarm is deliberately empty; window overflow is returned.
  - `core/src/guardian/input_budget.rs:106-125`: obtains `vrs_history`, normalizes images through
    the session image store, and builds a prompt only for request-budget accounting.
  - `core/src/session/vrs_input.rs:182-204`: an empty-input prompt reserves actual wire overhead
    before assembly; it supplies no history.
  - `core/src/prompt_debug.rs:107-121`: returns a debug API projection and performs no sampling
    dispatch. This is model-shaped diagnostic output, not a second model request entrance.
  - `core/src/session/turn.rs:1229-1257` is the only `client_common::Prompt` literal.
- `for_prompt` has two consumers: `session/vrs_input.rs:262-269` normalizes only a just-completed
  VRS assembly; `prompt_debug.rs:107-121` is the non-dispatching debug projection above.
- There are ten non-test `clone_history()` expression sites when the forwarding helper itself is
  counted. None passes response items to a model request:
  - `guardian/feedback.rs:29` serializes opt-in failed-review diagnostics.
  - `guardian/review_session_setup.rs:149-153` reads only `history_version` for reviewer reuse.
  - `session/handlers.rs:375` counts turn boundaries for shutdown telemetry.
  - `session/mod.rs:1573-1579` computes a numeric trace estimate;
    `session/mod.rs:1817-1827` changes only DB-memory eligibility after an external-context marker;
    `session/mod.rs:4789-4793` forwards to the private D4 cache; and
    `session/mod.rs:5109-5119` computes UI token-usage state only (the compiler reports this
    method dead in production; its in-tree callers are two unit tests).
  - `tools/context.rs:149` selects originating call/window identifiers for tool/Guardian control,
    not response text.
  - `prompt_debug.rs:107` is the non-dispatching diagnostic above.
  - `test_support.rs:82` has no production caller and exposes diagnostic test metadata only.
  The extra textual call under `tools/handlers/extension_tools.rs:506` is inside its `#[cfg(test)]`
  module and was excluded.

### Every parent, sender, resume, and stored-history family

1. Normal generation A1/A2: `session/turn.rs:1312-1347` rebuilds `A(S_t, thread)` on every stream
   attempt and sends only that input.
2. Guardian parent/reviewer: `guardian/review.rs:288-305`,
   `guardian/input_budget.rs:51-60,106-116`, `guardian/review_session.rs:265-288`, and
   `guardian/review_session_setup.rs:324-339` all obtain the parent/reviewer history through
   fallible `vrs_history`; no accumulated cache is substituted.
3. Next-reviewer fork snapshot: after a reusable completed review,
   `guardian/review_session_setup.rs:213-228` calls `session.guardian_fork_history()`;
   `session/guardian_checkpoint.rs:11-37` constructs those items from `vrs_history()`;
   `review_session_setup.rs:233-267` publishes them only after authorization validation; and
   `ext/guardian-reviewer/src/review_state.rs:51-91` stores/returns that VRS-derived
   `InitialHistory::Forked` to the next reviewer. No history-version recovery or parent-compaction
   checkpoint remains.
4. New 0.167 ordinary-agent fork seam A20: both
   `agent/control/spawn.rs:741` and `agent/host/spawn.rs:53-58` call the shared
   `agent/history.rs:210-527` `prepare_forked_history`. Resident parents use `vrs_history`
   (`275-283`); unloaded parents resolve an authorized rollout path then use
   `vrs_history_for_path` (`285-302`). Assembly/store failure returns `CodexErr`.
5. Agent resume: `agent/control/spawn.rs:295,1025` calls
   `agent/history.rs:133-206` `load_agent_model_context`. Any model-visible stored items are
   discarded at `189-205` and replaced with resident/path VRS items; only session/turn/world-state
   and dynamic-tool host metadata survives from storage.
6. Legacy subagent: `thread_manager.rs:1363-1404` uses resident `vrs_history` or authorized
   `vrs_history_for_path`; missing path/assembly is an error.
7. Sender context: `agent/control/sender_context.rs:64-120` uses a resident fallible VRS snapshot
   or a bounded authorized store lookup followed by `vrs_history_for_path`. Only genuine
   not-found, ineligible internal source, or no path means no optional sender fragment; storage,
   timeout, and VRS errors propagate.
8. Reference/prediction fork and `thread/sample`: app-server preparation may read metadata/model
   context, but reference lineage is installed through `thread_manager.rs:1734-1827`; the child's
   first and every later model request still enters `session/turn.rs:1312-1347` and reassembles
   VRS. `app-server/src/thread_sample.rs:122-128,323-326` uses fallible parent snapshots for
   revision/MCP checks, not direct request history.
9. Resume and ordinary app-server fork stored-history reads are not alternate request entrances.
   `session/mod.rs:1662-1744` uses stored rollout records for host reconstruction, seeds non-local
   originals into VRS when no local path exists, and performs only a D4 cache refresh; local
   sessions assemble the rollout path. Fork copies are persisted into the child's VRS before its
   next normal sample. No request reads those `StoredThread.history` values directly.

All seven production `read_thread(... include_history ...)` families were traced:

- `agent/history.rs:138-205`: stored model items are removed and replaced by VRS; host metadata
  only survives.
- `thread_manager.rs:1695-1710`: legacy initial history/host reconstruction; there is no direct
  request sink and the resulting session samples through VRS.
- `app-server/thread_processor.rs:3187-3221`: API `Thread`/turn projection only.
- `app-server/thread_processor.rs:3808-3827`: `thread/turns/list` projection only.
- `app-server/thread_processor.rs:4766-4797`: payload construction for resuming an already-loaded
  thread, not mutation of its model context.
- `app-server/thread_processor.rs:4948-5002`: cold-resume reconstruction; model requests use the
  local VRS path or non-local records first seeded into VRS.
- `app-server/thread_processor.rs:5491-5512`: ordinary legacy fork source snapshot; it is cut and
  persisted as the child lineage, then sampled only through the VRS entrance. Paginated/reference
  forks use the corresponding prepared lineage rather than direct dispatch.

The requested 0.167 seam details are therefore explicit:

- `agent/history.rs:210-527` and `agent/host/spawn.rs:53-58` are covered by item 4.
- The inherited-tool notice is created at `session/mod.rs:1788-1798` only after fork persistence;
  `record_conversation_items` records it into the child lineage, so it reaches a model only in a
  later VRS assembly. It is not appended to an already-built request.
- Image/audio normalization is downstream of VRS at
  `session/vrs_input.rs:202-215,262-269`: assembly completes, then the temporary ContextManager's
  `for_prompt(input_modalities, image_store).await` runs. Guardian budget normalization likewise
  begins from `vrs_history` at `guardian/input_budget.rs:51-60,106-116`.

Result: one normal generation entrance, five audited prompt-builder call sites, ten classified
non-test clone expressions, seven classified stored-history read families, and zero missing
model-input sites.

## 4d. R3 - fallback paths: 0

- Live assembly: `core/src/session/vrs_input.rs:70-126` returns recording/path/wait/store/decode
  failure. `NotReady` uses the existing bounded wait and retries the same VRS store; wait failure
  is returned.
- Path assembly: `session/vrs_input.rs:156-175` has the same error-return behavior and no live or
  accumulated-history alternative.
- Decode/admission: `session/vrs_input.rs:135-153` rejects malformed, unknown, and every
  compaction record; `182-215` maps assembly errors to `CodexErr`, rejects empty assembly and
  context overflow, and returns only normalized assembled items.
- Dispatch/prewarm: `session/turn.rs:1317-1347` and
  `session/startup_prewarm.rs:397-423` use `await?`; no error branch builds a prompt from the D4
  cache.
- `restore_history_from_vrs` at `session/vrs_input.rs:286-293` deliberately logs a best-effort D4
  cache refresh failure. It is not a request fallback because the next sample calls
  `vrs_prompt_input` again.
- F1: `guardian/score_authorization.rs:22-67` makes `is_current`, `current`, and `for_session`
  return `CodexResult`; both root package lookup and `conversation_history_snapshot` use `?`.
  `guardian/decision.rs` and guardian-v2 callers handle that failure instead of treating it as
  authorization.
- Direct Guardian review: `core/src/codex_thread.rs:920-935` now maps `vrs_history` failure to
  `CodexErr`; `guardian/review.rs:288-305` turns parent assembly failure into a prompt-build error;
  `guardian/review_session.rs:265-288` marks reviewer assembly failure as `SessionFailed` and
  discards the session.
- Fork/sender sites listed in R2 map/propagate VRS failure. In particular
  `agent/control/sender_context.rs:76-109` propagates store failure, VRS failure, and timeout; it
  does not convert them to empty evidence.

## 4e. D3-double-prime

- `core/src/session/step_context.rs:53-58`: `incremental_tools_enabled()` returns literal `false`.
- `core/src/session/world_state.rs:43-50`: `current_window_uses_incremental_tools()` returns
  literal `false` before reading any history.
- Consumers therefore always rebuild instructions/tools/output format for the current step; no
  incremental prefix switch is inferred from accumulated history.
- The result-changing incremental-tool scenarios were not deleted:
  `core/tests/suite/scenarios_incremental_tools.rs` retains
  `prediction_fork_keeps_inherited_tools`, the three changed-catalog cases, and two tool-removal
  cases; `scenarios_incremental_tools_resume.rs` retains both
  `legacy_resume_switches_only_after_window_replacement` variants and
  `disable_incremental_tools_at_next_window`.

## 4f. R6 - no new serial structure

- `git diff HEAD -- codex-rs/vrs vrs-lib7` is empty. Both directories are byte-identical to the
  FCC 1.1.3 reference tree; the Rust FFI and libvrs implementation were not changed.
- Comparing the current VRS input seam with FCC 1.1.3 finds no added `Mutex`, `RwLock`, `Condvar`,
  `Barrier`, `OnceLock`, CAS, writer flush, ready poll, sleep, or yield. Its source changes are the
  0.167 async image-store normalization/API adaptation, not synchronization.
- Comparing the four relevant 0.167 lifecycle files with upstream shows no added synchronization
  line. Existing structures were retained: Guardian review-session mutex/checkpoint publication,
  reviewer deadline wait, app-server background-task shutdown wait, `thread/sample` response
  oneshot mutex, and its upstream source-consistency `flush_rollout`.
- Agent fork/resume, sender, direct Guardian, and authorization fixes add only fallible
  `vrs_history`/`vrs_history_for_path` calls and error mapping. They add no writer barrier, global
  lock, polling loop, or ordering guarantee.

## Required build, tests, generated files, and changed tests

All Cargo commands used `CARGO_NET_OFFLINE=true`, the isolated
`CARGO_TARGET_DIR=$HOME/tmp/codex-p114-target`, OpenSSL 3.5.9 headers/libs from
`$HOME/tmp/openssl3-sdk`, `env -u VRS_LIB_DIR`, and `taskset -c 0-11`.

- Release build: the full post-audit rebuild passed (`Finished release ... 5m 33s`), followed
  after all linker sessions had quiesced by a standalone incremental verification with explicit
  exit 0 (`Finished release ... 0.57s`). Logs are `final_release_build_incremental.full.log` and
  `final_release_verification.full.log` under `~/tmp/p114-work/`.
- Version: `codex-cli 0.167.0-alpha.3.2`.
- Binary SHA-256: `306a88dbeef967375daf4ddeedcaa2bb4ac8efa2cad4a0d07d566ecf91061eb2`.
- Unit tests: `cargo test --offline -p codex-prompts -p codex-models-manager` passed 58/58 and
  59/59 (`~/tmp/p114-work/test_F2_prompts_models.full.log`).
- Test compilation: `RUST_MIN_STACK=33554432 cargo test --offline -p codex-core --no-run` passed
  on the final audited source, including removal of the parent-compaction activation case.
  `cargo test --offline -p codex-app-server --no-run` then passed on that same final source. The
  final logs are `final_core_test_no_run.full.log` (`Finished test ... 58.99s`) and
  `final_app_server_test_no_run.full.log` (`Finished test ... 2m 35s`) under
  `~/tmp/p114-work/`.
- Schema/bindings: the repository writer regenerated stable/experimental JSON, TypeScript,
  precomputed schema, Python v2 artifacts, and `core/config.schema.json`. Final generated targets
  are byte-identical to upstream 0.167. The coordinator supplied the two Python wheels that were
  unavailable in the original offline cache; `generate_python_coord.log` exits 0 and produced no
  worktree delta. This is no longer an unresolved network item.
- Schema fixture test: `cargo test --offline -p codex-app-server-protocol schema_fixtures` passed
  6 tests, failed 0, with the writer-only test ignored as upstream intends.

Changed/removed tests are limited to deleted compaction meaning or compile/API adaptation:

- Bundles A-E removed compaction-phase, new-context-window, parent-compaction reuse/checkpoint,
  async/background/remote compaction, and compact-hook cases; mixed tests retain all unrelated
  assertions. The complete per-file list is in `~/tmp/p114-work/report_F.md` under
  `F2 시험 변경·삭제 목록`.
- F2 compile adaptations only propagated fallible VRS results, updated 0.167 `CatalogModel` and
  async image-store calls, restored imports needed by retained non-compaction tests, and changed no
  expected behavior.
- F3 removed one stale `step_activation_tests.rs` case whose sole assertion was that deleted
  `max_parent_compaction_tokens` changes Guardian authority. No expected value was rewritten.
- The D3-double-prime incremental-tool scenarios listed in 4e remain compiled.

## 4g. Q4 mock-provider release smoke

Command form:

`RELSMOKE_DIR=$PWD/l3check/port_167/release1 bash l3check/release1/run.sh $HOME/tmp/codex-p114-target/release/codex`

Environment-blocked before product evidence. `mock_responses.py` failed in
`socket.socket(AF_INET, SOCK_STREAM, ...)` with `PermissionError: [Errno 1] Operation not
permitted`; the managed sandbox forbids even a `127.0.0.1` listening socket. Consequently all
four CLI cases waited for the absent provider and exited 124 at their 120-second limits:

| Case | Provider requests | Main-model requests | Result |
|---|---:|---:|---|
| S_a_astra | 0 | 0 | environment-blocked |
| S_a_sol | 0 | 0 | environment-blocked |
| S_b_resume | 0 | 0 | environment-blocked |
| S_c_custom | 0 | 0 | environment-blocked |

Temporary rollout scan reported zero compaction items, but that is not a substitute for the
required 4/4 template assertions because no request was served. Therefore “compaction guidance
zero” and “Custom byte-invariant” remain unmeasured in this sandbox and must be rerun by the
coordinator in an environment permitting loopback sockets. Raw evidence:
`l3check/port_167/release1_fcc114.txt`.

## Boundaries and handoff

- No file under `vrs-lib7/` or `codex-rs/vrs/`, no `~/.codex` data, no other worktree, and no
  running process was modified.
- This is a local, uncommitted merge result. The coordinator still owns staging/commit and the
  networked real-backend S1-S5 gate.
- F3 files are listed in `~/tmp/p114-work/report_F.md`. At final verification the implementation
  fixes were already in the index; the remaining F3-specific unstaged paths were
  `l3check/audit3_inventory.py` and `l3check/port_167/`, which the coordinator must stage.
