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
