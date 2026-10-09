# L3 VRS model-context source audit (round 3)

Evidence boundary: source review at commits `09d9a83`, `ffa90c2af`, and `dac14ff77`.
This note does not claim runtime tests or release build success. Root owns serialized
builds/tests and the final report. Line numbers refer to the current shared checkout
when this note was generated; subsequent coordinated edits can move them.

## D3 / P-6 route table

All model-history routes below converge on `core/src/session/vrs_input.rs:63`.
There is no accumulated-history fallback in these routes.

| D3 place | Rust route and error behavior |
| --- | --- |
| A1 first attempt | `core/src/session/turn.rs:427` -> `vrs_prompt_input`; error exits turn before dispatch. |
| A2 retry | `core/src/session/turn.rs:1210` reassembles on every retry; `?` propagates failure. The first iteration consumes the A1 assembly. |
| A4 History prewarm | `core/src/session/startup_prewarm.rs:403` -> `vrs_prompt_snapshot`; `?` propagates failure; Base prewarm retains the explicitly allowed empty input. |
| A8 / A9 guardian budgets | `core/src/guardian/input_budget.rs:48,95` -> `vrs_history`; errors map through `vrs_error_to_codex`. |
| A10 / A13 parent reviewer context | `core/src/guardian/review.rs:220`, `review_session_setup.rs:255` -> parent `vrs_history`; failures return reviewer errors. Own reviewer turns use A1/A2. |
| VI-18 four guardian consumers | `core/src/guardian/review_session.rs:359,448,723,767` -> reviewer `vrs_history`; every error propagates through `?`/review session error result. Reminders and image deduplication inspect the assembly. |
| A14 scorer | `core/src/session/mod.rs:4280` snapshot returns `CodexResult`; `core/src/tools/lifecycle.rs:37` maps failure to fatal tool error before contributors run. Root authorization and reviewer snapshots also propagate errors. `guardian-v2` no longer has parent-compaction request fields, hash checks, prefix injection, or reuse-key dependence. |
| A15 realtime startup | `core/src/realtime_context.rs:66` -> `vrs_history`; `core/src/realtime_conversation.rs:1513` maps assembly failure to turn error. `None` startup context is only a successful empty-context case, not an assembly-error fallback. |
| A20 agent fork | `core/src/agent/control/spawn.rs:1006` -> parent `vrs_history`; maps failure to turn error and seeds selected original ResponseItems plus host metadata. Last-N fork filtering remains the existing explicit fork mode applied to the assembly. Child turns use A1/A2. |
| A18 / A21 / A22 separate threads | Their model requests use `run_turn` A1/A2. Ephemeral recording is `core/src/session/vrs_input.rs:193`; errors invalidate future assembly. |
| A17 / A19 memory extraction | Design explicitly excludes finished-rollout extraction consumers from I2; no migration to live-history model input was introduced. |
| A6 / A7 compaction | Deletion audited by the separate D7 owner; no new summary request path here. |

## Closed implementation defects and decisions for document section 5.5

- **Partial assembly accepted** — L3; blocks G through I2/I3/I5. Previously,
  one JSON conversion failure only warned and skipped that item. At
  `core/src/session/vrs_input.rs:106`, decoding now fails the entire assembly for
  malformed data, unknown `Other`, or obsolete compaction items. No partial
  request can be sent. Two unit tests assert valid-prefix rejection and unknown /
  compaction rejection; they do not relax any model-input expectation.
- **Recording failure discarded by higher callers** — L3; blocks G through
  I3/I5. Recorder errors reached `persist_rollout_items` but many callers ignored
  its boolean return. `core/src/session/mod.rs:4240` now stores the first error in
  the existing SessionState, and `vrs_input.rs:89` rejects all later assembly for
  that live session. The message requires reopening the session; no retry can
  pretend an unrecorded input exists. The original insertion error still returns
  to the record caller. This uses only the preexisting session Mutex and adds no
  global lock, writer, or writer-completion wait. A unit test injects the sticky
  failure and verifies prompt construction returns the error before model input.
- **D4 refresh omitted by snapshots/prewarm** — L3; blocks I7. Successful
  `vrs_input.rs:63` now refreshes the live cache for every consumer, including
  snapshot and prewarm. Prompt construction consumes the assembly directly.
  Resume/fork restoration no longer calls `flush_rollout` before assembly
  (`session/mod.rs:1635,1693`). Existing durability operations elsewhere remain
  codex-owned and are not dependencies inside the assembly function.
- **Read-only assembly changed history identity** — L3; delays G by invalidating
  retained guardian cursors without new evidence. At
  `core/src/context_manager/history.rs:709`, an identical assembled item set and
  already-cleared compatibility transcript preserve history_version. Changed
  evidence still increments it. The added regression test checks both cases.
- **Guardian-v2 parent compaction machinery survived** — L3; blocks I1/I2.
  `ext/guardian-v2/src/async_scorer/sampler.rs:159` constructs setup/evidence only;
  obsolete compaction request/hash/compatibility branches and dependent plumbing
  are removed. Existing config input fields remain inert compatibility parsing.

## Test changes requiring root execution

Added:

- `session::vrs_input::tests::malformed_assembly_does_not_keep_the_valid_prefix`
- `session::vrs_input::tests::unsupported_assembly_is_an_error_instead_of_an_omission`
- `session::vrs_input::tests::recording_failure_prevents_assembly_before_any_model_request`
- `context_manager::history::tests::repeated_assembly_preserves_the_history_revision`

Class (a), removed because these only test obsolete parent-compaction reuse
(D3 A14, document line 121; D7, document lines 141-144):

- `async_scorer::sampler_tests::sampler_reuses_parent_compaction_only_for_matching_model_hashes`
- `async_scorer::extension_tests::contributor_reuses_the_latest_compatible_parent_compaction`
- `async_scorer::extension_tests::legacy_contributor_reuses_the_latest_compatible_parent_compaction`

Class (c), `complete_budget_counts_setup_checkpoint_images_and_trusted_evidence`
renamed to `complete_budget_counts_setup_images_and_trusted_evidence`. The fixture's
obsolete encrypted checkpoint was removed, and a no-compaction assertion added.
The existing >10,000-token setup assertion and exact budget boundaries (+255
reject, +256 accept) are unchanged. The Decisions adapter's obsolete separate
parent-compaction argument/assertion was removed along with that removed API;
unsupported roles and external-image rejection remain.

No listed test was run by this subagent. `rustfmt --edition 2024 --config
skip_children=true` parsed changed files, and `git diff --check` passed.

## Remaining clone_history calls

`l3check/clone_history_context3.tsv` lists all 72 tracked Rust invocations with
file:line and a reason. Production consumers are numeric token estimates, debug
API rendering, shutdown telemetry, memory-mode bookkeeping, tool-origin identity,
and opt-in failed-review diagnostics. The helper forwards to these consumers.
The remainder are tests. The feedback route was followed through
`ext/guardian-reviewer/src/feedback.rs:85,105` to
`feedback/src/guardian.rs:94`: a bounded JSON record enters a process-local
feedback buffer, not a model request.

This is a manually audited call-path inventory, not a dynamic reachability proof.
The final report must combine it with actual compilation and test outcomes.

## Follow-up D1 audit: no-file live stores

- **Non-local live store omitted from S** — L3; blocks I2/I5. A `LiveThread`
  is not proof of a file-backed recorder: `thread-store/src/live_thread.rs:391`
  returns no local path for `InMemoryThreadStore` and remote backends, and
  `thread-store/src/in_memory.rs:650` only appends to its own history. At
  `core/src/session/mod.rs:4240`, successful non-local appends now also publish
  to the same virtual VRS path selected by assembly. Local file appends remain
  owned by the recorder and are not inserted twice. Append, path lookup, and
  VRS insertion errors all poison the session through the existing D5 error
  field. No writer flush or new lock is introduced. Added regression test
  `session::tests::in_memory_live_thread_publishes_model_items_to_vrs` checks
  a user request plus tool call/output survives into the assembly. No build or
  test has been run by this subagent for this change.

## Follow-up D4 audit: internal execution metadata capture

- **Diagnostic capture incorrectly requested a fresh model assembly** — L3;
  blocks the internal metadata assertions while model tool output delivery still
  succeeds. `core/src/test_support.rs:74` previously called the A14 snapshot
  after `TurnComplete`; the library is then allowed to select a different
  context from its now-closed turn. This test-only diagnostic helper now reads
  the bounded D4 live cache H, which the design explicitly reserves for non-model
  consumers (document lines 128–131). The production conversation snapshot still
  reassembles A and propagates errors. Existing result-metadata assertions remain.
- **D4 replacement lost execution success** — L3; blocks diagnostic correctness.
  `protocol/src/models.rs:2178` explicitly excludes tool `success` from serialized
  model data. `core/src/context_manager/history.rs:684` now preserves that field
  by surviving response item identity, alongside existing harness metadata. The
  retained data is bounded by the currently assembled records; it is dropped
  when an item leaves the assembly. `vrs_input` still returns the assembler's
  vector directly, without copying live metadata into model input. Added the
  two cases of
  `context_manager::history::tests::assembly_keeps_bounded_diagnostic_success_without_changing_wire_input`:
  both success and failure must survive, serialized wire JSON must remain
  exactly unchanged, and removing the record must remove the diagnostic copy.
  No build or test has been run by this subagent for this change.

The refreshed clone inventory has 73 calls, including the new test-only capture
consumer. Its per-call line locations include the current session changes.
