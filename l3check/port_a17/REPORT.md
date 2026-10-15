# alpha.17.2 VRS port L3 report

## 4a. Conflict resolutions (36)

### Previously resolved DU conflicts (reconstructed from the index and three-way inputs)

- `codex-rs/core/src/compact.rs` — kept deleted: upstream only refactors compaction replacement history, prefix/context injection, fallback inputs, and compaction token recomputation; all are D7/I1 compaction behavior and no non-compaction helper needed extraction.
- `codex-rs/core/src/compact_model_fallback.rs` — kept deleted: upstream only narrows model fallback for failed compaction attempts; the VRS fork has neither compaction nor its fallback path.
- `codex-rs/core/src/compact_remote_v2.rs` — kept deleted: upstream changes remote-v2 compaction context rebuilding/model fallback and replacement history; all remain forbidden remote compaction behavior.
- `codex-rs/core/src/compact_remote_v2_attempt.rs` — kept deleted: upstream adds incremental-tool-aware base instructions/tools to a remote compaction request only; D3-prime also disables incremental tools and the whole request is forbidden by I1.
- `codex-rs/core/src/compact_tests.rs` — kept deleted: tests only the removed local compaction implementation and replacement-history semantics.
- `codex-rs/core/src/compact_token_budget.rs` — kept deleted: upstream moves step/world-state preparation for token-budget compaction; this remains a forbidden compaction trigger/path.
- `codex-rs/core/src/tasks/compact.rs` — kept deleted: upstream moves manual compact step/world-state preparation into `CompactTask`; the task itself is removed and exports no unrelated helper.
- `codex-rs/core/tests/suite/compact.rs` — kept deleted: integration coverage is exclusively for the removed compaction behavior.
- `codex-rs/core/tests/suite/compact_program_tests.rs` — kept deleted: integration coverage is exclusively for the removed compaction program/lifecycle.
- `codex-rs/core/tests/suite/compact_remote_trimming.rs` — kept deleted: integration coverage is exclusively for removed remote-compaction history trimming.
- `codex-rs/core/tests/suite/compact_resume_fork.rs` — kept deleted: integration coverage is exclusively for removed compact/resume/fork projection semantics; VRS resume/fork assembly is audited separately.

### Resolved in this continuation

- `codex-rs/Cargo.toml` — kept upstream alpha.17.2 workspace/package graph and re-added the fork's `vrs` member plus `codex-vrs` workspace dependency; no ordering or runtime serialization change.
- `codex-rs/Cargo.lock` — reset the conflicted old-alpha.2 package versions to the upstream alpha.17.2 lock baseline; Cargo will add only the merged `codex-vrs` graph during the required build.
- `codex-rs/core/src/agent/control/spawn.rs` — retained upstream fork modes/metadata filtering but replaced parent rollout materialization and compaction-checkpoint inheritance with fallible `vrs_history()` assembly (D3 A20), with no writer flush barrier.
- `codex-rs/core/src/guardian/input_budget.rs` — kept upstream guardian evidence budgeting around the VRS-assembled model input, removed checkpoint/compaction recovery state, and made over-budget required evidence fail the request instead of compacting or truncating it.
- `codex-rs/core/src/guardian/prompt.rs` — kept upstream guardian transcript/package construction and propagated the fork's fallible assembled-history and guardian-package reads instead of silently using unavailable context.
- `codex-rs/core/src/guardian/review_session.rs` — retained upstream reviewer reuse/deadline flow but removed auto-compaction/checkpoint recovery and compaction settings from reuse identity; every reviewer/parent model context is freshly VRS-assembled and snapshot errors propagate.
- `codex-rs/core/src/guardian/review_session_setup.rs` — retained upstream reviewer pool/startup lifecycle while deleting parent-compaction recovery/restart selection; prewarm now obtains fallible VRS history and no new wait/lock/barrier was introduced.
- `codex-rs/core/src/guardian/review_session_tests.rs` — kept all non-compaction reviewer tests and removed only three upstream tests whose subjects were concurrent/encrypted compaction checkpoint reuse or compaction-scope cache invalidation; listed below as D3-prime/D7 semantic changes.
- `codex-rs/core/src/guardian/tests.rs` — merged upstream `GuardianTranscriptHistory` typing with fallible VRS snapshots; preserved the new prompt-cache/prior-review test by narrowing it to its two non-compaction reviews and removed only its compact/reset expectations.
- `codex-rs/core/src/session/mod.rs` — kept upstream session/settings/world-state/persistence changes, reattached VRS seeding/restoration/publication and recording-error propagation, kept request-time compaction-guidance removal, and removed compact/new-window execution plus token-budget recomputation paths.
- `codex-rs/core/src/session/rollout_reconstruction.rs` — retained upstream metadata/rollback/world-state reconstruction but stopped replaying rollout or legacy compaction replacement history into model input; D4 installs the VRS assembly separately.
- `codex-rs/core/src/session/tests.rs` — preserved new settings, MCP-attribution, and retained-step coverage by removing only their compaction scaffolding; removed two pure compaction tests and ignored the pre-existing compaction-fallback runtime test whose execution no longer exists.
- `codex-rs/core/src/session/tests/guardian_tests.rs` — converted the upstream compaction-initial-context test into an ordinary initial-context test, preserving its guardian developer-message and persistent-mode isolation assertions without a compaction path.
- `codex-rs/core/src/session/turn.rs` — retained upstream turn/tool/world-state flow, removed pre/mid/post-turn and guardian-budget compaction triggers, and moved fresh fallible `vrs_prompt_input()` plus window validation inside the sampling retry loop so A1 and every A2 rebuild A(S_t,g).
- `codex-rs/core/src/session/turn_input.rs` — retained upstream start/steer reservation behavior, removed the obsolete compact-task steering arm, and propagated fallible sender-history capture through all pending-input paths so VRS failure cannot be ignored.
- `codex-rs/core/src/state/session.rs` — retained upstream session state while restoring the bounded VRS live-cache publication/cut/install state and sticky recording error; removed compaction history replacement and new-window mutation methods.
- `codex-rs/core/tests/suite/guardian_context_budget.rs` — kept guardian budget and instruction-order coverage but changed oversized evidence expectations from reviewer compaction/truncation to D5 fail-closed with zero compaction requests; removed only compaction-specific parameter cases.
- `codex-rs/core/tests/suite/guardian_review.rs` — kept the upstream guardian review suite except the new `guardian_review_recovers_after_compaction` cases, whose entire subject is parent/reviewer checkpoint compaction recovery removed by D7.
- `codex-rs/core/tests/suite/retry_after.rs` — retained all HTTP retry coverage and explicitly ignored only five remote-compaction retry/backoff cases because their request path is absent under D7/I1.
- `codex-rs/core/tests/suite/skills_extension.rs` — preserved the upstream cloud/executor catalog stability test by removing its post-turn compaction request and reindexing it as an across-turns-and-resume VRS test; catalog allocation assertions remain.
- `codex-rs/core/tests/suite/snapshots/all__suite__scenarios__astra_kickoff_original_history.snap` — kept the fork's original-history scenario snapshot; the conflicting upstream side was a remote-compaction-window snapshot containing trigger/summary items forbidden by D7.
- `codex-rs/core/tests/suite/subagent_notifications.rs` — retained upstream fork-mode/context-baseline coverage, removed compacted-parent variants and synthetic `Op::Compact`, and asserted that VRS-assembled child history contains no inherited `Compacted` record.
- `codex-rs/core/tests/suite/tools.rs` — preserved strict tool-collision and environment-tool coverage, removed the pre-sampling-compaction duplicate case plus the pure compaction-error test, and repaired the adjacent duplicated test attribute.
- `codex-rs/ext/guardian-v2/src/async_scorer/decisions.rs` — retained upstream scoring/body construction but removed `parent_compaction` input and its compatibility rejection; guardian-v2 now consumes only the VRS-assembled evidence and instructions.
- `codex-rs/rollout/Cargo.toml` — retained upstream rollout dependencies and re-added `codex-vrs` plus the existing ctor test dependency required by VRS publication/recorder integration.

## D3′ incremental-tools decision

- `core/src/session/step_context.rs::uses_incremental_tools()` now always returns `false`, with the required VRS fork / design section 11.1 D3′ comment. The `incremental_tools` feature key remains accepted by configuration but has no request-prefix/history effect.
- Upstream tests intentionally left in place but expected to differ under D3′: `core/tests/suite/scenarios_incremental_tools.rs::incremental_tools_append_changed_catalog_without_rewriting_history` (both test cases: `incremental_tools` and `incremental_tool_removals`) and their two scenario snapshots. They assume the prefix/tools are accumulated in history; the fork rebuilds the complete base instructions, tool definitions, and output format on every request.

## Upstream test-source compile repairs

- `core/tests/suite/pending_input.rs`: changed `TurnInputSubmission::Started { turn_id }` to `{ turn_id, .. }` so the new `root_turn_id` field is accepted without weakening the assertion.
- `core/tests/suite/mcp_turn_metadata.rs`: changed the invalid `TurnEnvironmentSelections` construction to the field's actual `TurnEnvironmentRequests::new(...)`, converting the selected environment with `.request()`.
- The same two source changes were already present and verified in comparison worktree `$WORK/codex-a17-base`; no additional baseline edit was made in this continuation. Its Cargo lock was also already dirty from Cargo's workspace-version refresh.

## Build and compile-fix log

- First required release build reached `codex-core` and exposed 14 merge-interface errors. Fixes: removed the obsolete guardian `should_compact` re-export; imported upstream-moved `ReasoningEffortPin`; used `persisted_rollout_item(...).as_ref()` so ephemeral VRS sees the same transformed durable records; bound upstream's `fork_mode` and removed the no-longer-existing `LastNTurns` arm; treated guardian-root lookup failure as a cache miss rather than dereferencing `Result<Option<_>>`.
- Command: `env -u VRS_LIB_DIR CARGO_TARGET_DIR=$WORK/codex-port-target taskset -c 0-11 $HOME/.cargo/bin/cargo build --release -p codex-cli`
- Result: PASS. Last line: `Finished release profile [optimized + debuginfo] target(s) in 7m 49s`; built binary reports `codex-cli 0.162.0-alpha.17.2`.
- Cargo regenerated `Cargo.lock` from the upstream baseline: workspace crates are `0.162.0-alpha.17.2`, and the merged `codex-vrs` package/dependency edges are present.

## Required test log

- Command: `env -u VRS_LIB_DIR CARGO_TARGET_DIR=$WORK/codex-port-target taskset -c 0-11 $HOME/.cargo/bin/cargo test -p codex-prompts -p codex-models-manager`
- Result: PASS. `codex-models-manager`: 54 passed, 0 failed; `codex-prompts`: 46 passed, 0 failed.
- First `codex-core --no-run` attempt found two merge-only test-source errors beyond the two known upstream baseline errors: restored `std::sync::atomic::Ordering` for the retained reviewer respawn assertion and made the strict-tool-collision test builder mutable for upstream's `build_with_auto_env(&mut self)` API. Both are test-only compile repairs and preserve the assertions.
- Command: `env -u VRS_LIB_DIR RUST_MIN_STACK=33554432 CARGO_TARGET_DIR=$WORK/codex-port-target taskset -c 0-11 $HOME/.cargo/bin/cargo test -p codex-core --no-run`
- Result after the two test-source repairs: PASS. Last line set includes `Finished test profile ... in 1m 04s` and executables for the lib tests, `tests/all.rs`, MCP trace propagation, and response headers.
- Command: `env -u VRS_LIB_DIR RUST_MIN_STACK=33554432 CARGO_TARGET_DIR=$WORK/codex-port-target taskset -c 0-11 $HOME/.cargo/bin/cargo test -p codex-app-server --no-run`
- Result: PASS. Last line set includes `Finished test profile ... in 2m 13s` and the app-server lib/main/helper plus `tests/all.rs` executables.
