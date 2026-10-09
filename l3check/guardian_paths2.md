# VI-14 / VI-15 / VI-18 source implementation evidence

This note records source inspection and changes. No build or test was run by the
`guardian_paths` agent; the root agent coordinates serial baseline/current builds.
`rustfmt --edition 2024 --config skip_children=true` parsed the edited Rust files,
and `git diff --check` passed. These are not compilation or runtime evidence.

## VI-14: A20 parent fork context

`core/src/agent/control/spawn.rs::spawn_forked_thread` now obtains parent response
items through `Session::vrs_history`, which calls the single `vrs_input` entry.
The parent rollout load, materialization wait, and writer flush before assembly
are gone. Capability roots, reference turn context, and world-state baseline are
host metadata copied from the live parent. Full-history versus explicit last-N
fork selection and child-specific instruction handling apply to the assembled
parent items. No parent compaction records are copied. Assembly errors propagate
through the existing spawn `CodexResult`.

## VI-15: A14 snapshot errors

`Session::conversation_history_snapshot` and the public `CodexThread` wrapper
return `CodexResult<Arc<dyn ConversationHistorySnapshot>>`. A failed assembly no
longer creates an empty `ContextManager`. The error is propagated through:

- synchronous guardian prompt construction and review result;
- tool lifecycle notification, before invoking extensions, as a fatal tool error;
- sender provenance capture and start/steer admission (failed idle starts clear
  their reserved turn state);
- guardian-v2 authorization capture, classification failure, and retained-conversation
  request preparation (`LunaSamplerError::ContextAssembly`). No sample starts with
  substitute history; completed samples with unvalidated authorization are not cached.

Existing tests that expect a successful history snapshot or authorization capture
unwrap the newly fallible API. Their behavioral assertions remain unchanged.
`core/tests/suite/code_mode.rs` was excluded because it belongs to the root agent;
its two snapshot call sites were reported for follow-up there.

## VI-18: guardian reviewer inputs

All four production `clone_history` calls in `guardian/review_session.rs` were
replaced by VRS history snapshots: full/delta transcript selection, image
admission, follow-up reminder detection, and node REPL policy detection. Each
assembly failure is returned before submitting the reviewer request.

## Remaining production `clone_history` calls

Line numbers below were inspected after these edits; the root final inventory may
shift if other changes add lines. Test-only calls must be enumerated separately
by the final inventory script.

| Location | Why accumulated response items are not used for a model request |
| --- | --- |
| `core/src/guardian/feedback.rs:29` | Stores bounded failed-review feedback locally through `FailedReviewFeedback::store`; it does not sample a model. |
| `core/src/prompt_debug.rs:107` | Builds the debug API response. Design D3 explicitly excludes A5 from model requests. |
| `core/src/session/handlers.rs:346` | Counts user-turn boundaries for shutdown telemetry after shutting down the session runtime. |
| `core/src/session/mod.rs:1496` | Returns only a token estimate from `get_estimated_token_count`; response items are not returned as input. |
| `core/src/session/mod.rs:1704` | Detects externally injected context to mark memory mode polluted; no request input is built. |
| `core/src/tools/context.rs:105` | Finds the originating call ID for provenance and window metadata; the history itself is not sent. |
| `core/src/session/mod.rs:4265` | `Session::clone_history` delegates to the state copy; production consumers are the six rows above. |

## Scope of E3-3 evidence

These edits introduce no mutex, writer, or condition wait. VRS error handling uses
existing session locks and reviewer deadlines. The preexisting guardian-v2
conversation worker and its mutex were not introduced by this task. The writer
wait removed from A20 is not replaced with another barrier. The central
`vrs_input` writer-barrier removal is owned by the root agent.

## Existing inactive parent compaction fields

`ext/guardian-v2/src/async_scorer/observation.rs` already fixes `parent_compaction`
and its hash to `None`. Sampler/config/retained-conversation fields and related
code remain in the prior WIP. This note does not claim those definitions are
removed; the root agent was notified for D7 and test classification.

## Additional D3 / D7 audit fixes

`ContextManager::replace_assembled` now drops its old compatibility review
transcript. Otherwise legacy and independent Guardian modes selected
`review_history` instead of `items`, even though `items` had just been assembled
by VRS. A regression test covers all three Guardian modes and has been added
but not executed by this agent.

`guardian/request_budget.rs::prepare_prompt` now only checks the complete
request budget. The removed compaction restoration path appended retained
originals directly to the prompt after VRS assembly. `RetainedReviewContext` and
its compaction-only unit test were removed with that mechanism.

Classification (a), removed test:
`guardian::input_budget::tests::compacted_review_restores_originals_once_and_persists_the_request_prefix`.
Reason: its only behavior is restoring a simulated compacted reviewer window;
D7 deletes guardian compaction. This unit test is outside the `--test all`
integration baseline. Its removal is source-classified, not a claim about the
baseline/current failed-test difference.

## Root authorization and Guardian fork checkpoint

`AgentControl::get_guardian_package`, `root_user_authorization`, and
`CodexThread::guardian_root_snapshot` now return `Result<Option<...>>`. A tree
with no live root still yields `Ok(None)`; a live root whose VRS assembly fails
yields an error. Sync review preparation emits the turn error and aborts; prompt
building, cache authorization, and async classification propagate or report the
failure before starting a model request.

`Session::guardian_fork_history` now assembles with VRS and writes original
`RolloutItem::ResponseItem` entries into its fork snapshot. It carries current
turn-context, world-state, and token-usage metadata as their ordinary rollout
variants. It no longer creates a synthetic `RolloutItem::Compacted`, copies an
old retained transcript, or copies compaction-window metadata. Reviewer snapshot
commit now returns an error; the existing reviewer pool reports `SessionFailed`
and discards the reviewer when that assembly fails. Parent-compaction seeding of
new synchronous reviewers was removed.

Classification (a), additional removed test:
`guardian::review_session::tests::encrypted_parent_compaction_requires_original_item_id`
(two parameter cases). It only tests parent-compaction reuse, which D7 removes.
Classification (c), revised test:
`session::guardian_checkpoint::tests::guardian_checkpoint_preserves_live_context_without_storage`
was replaced with two storage-mode cases of
`guardian_checkpoint_preserves_assembled_originals_without_compaction`. It records
original items into VRS, checks the fork contains ordinary response items and no
compaction record, and checks world/turn/token metadata. The former legacy
compaction-transcript fixture and expectation were removed under D3/D7.
These unit tests were not run by this agent.

## D3 / P-6 source audit table

Paths below are relative to `codex-rs`. This table is source evidence only, and
line numbers may shift while the root agent completes its owned files.

| Place | Entry and propagation | Source assessment |
| --- | --- | --- |
| A1 | `core/src/session/turn.rs:427` calls `vrs_prompt_input`; the sampling block propagates `?`. | Uses A; no accumulated-history fallback. |
| A2 | `core/src/session/turn.rs:1211` calls `vrs_prompt_input` again after the first input is consumed. | Every sampling retry assembles again. |
| A4 | `core/src/session/startup_prewarm.rs:403` History calls `vrs_prompt_snapshot`; Base remains empty. | Error propagates before prewarm request. |
| A8 | `core/src/guardian/input_budget.rs:48,95` measures and selects from `vrs_history`. | Compatibility transcript fallback removed in `replace_assembled`. |
| A9 | `core/src/guardian/request_budget.rs:54` checks the prompt already assembled by A1/A2. | Old compaction restoration and direct append removed. |
| A10 | `core/src/guardian/review.rs:220` captures parent `vrs_history`; preparation reports its error. | Parent share uses A. |
| A13 | `core/src/guardian/review_session_setup.rs:255` prewarm uses A; `core/src/session/guardian_checkpoint.rs:13` commits reviewer fork items from A; root authorization uses `vrs_history`. | Raw VRS originals, no synthetic compact checkpoint; errors propagate. |
| A14 | `core/src/session/mod.rs:4281` fallible snapshot uses A; `core/src/tools/lifecycle.rs:37` returns fatal error before extensions run; async authorization is fallible. | Empty-snapshot fallback removed. |
| A15 | `core/src/realtime_context.rs:66` uses A; `core/src/realtime_conversation.rs:1513` maps assembly error to Codex error. | No history fallback. Explicit external startup text is a separate caller option. |
| A20 | `core/src/agent/control/spawn.rs:1008` uses `vrs_history`. | Parent stored-history read and writer wait removed. Explicit last-N fork policy still filters assembled items. |
| D4 | `core/src/session/mod.rs:1637,1696` installs assembly after resume/fork; `session/vrs_input.rs:119` installs each normal request assembly. | Root notified that prewarm and other `vrs_history` reads had not installed the result in live history at audit time. |
| D5 | `session/vrs_input.rs:51` maps status failures; guardian snapshots/fork commits/root packages preserve errors. | Root notified that malformed individual assembled items were still skipped at audit time. |
| D7 | `session/handlers.rs:245,654` reports manual compact as unsupported; guardian compact restore and compact fork creation removed. | Existing inactive guardian-v2 `parent_compaction` fields/logic remain; live observation supplies None. Global grep and full cleanup are root-owned. |

No impossibility requiring a design change was found in these paths. Unverified
builds/tests and remaining root-owned D4/D5 points are not marked as passed.
