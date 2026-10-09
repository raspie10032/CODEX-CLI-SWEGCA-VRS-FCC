# VI-31: request-specific physical-window admission

Source audit and implementation, 2026-10-09. No build or tests were executed by this audit agent; the parent owns serial compilation and test execution.

## Defect

The earlier FFI only exposed `vrs_assemble`, and process options selected the library default (258,400 estimated tokens). A1/A2 passed only input modalities to `vrs_prompt_input`. Thus a captured smaller model, a model override, or a request with substantial instructions/tools/schema could send an assembly larger than its own allowance. The previous `context_window_token_status` is called after successful sampling (`core/src/session/turn.rs`, post-sampling state) and reads previously observed API usage. The `ContextWindowExceeded` branch after `try_run_sampling_request` is a backend error handler, not pre-network admission. Synchronous guardian had a local check, but ordinary requests did not.

## Implemented change

- `codex-rs/vrs/src/lib.rs:273`: `assemble_with_budget(path, Option<u64>)` calls `vrs_assemble_b` for explicit budgets. `Some(0)` is `OverWindow`, never the process default. No shared budget is mutated. `nm $WORK/vrsint/libvrs.a` reported `T vrs_assemble_b`; the stub now exports the same symbol but is not runtime evidence.
- `codex-rs/core/src/session/vrs_input.rs:66`: all consumers retain one shared `vrs_input`; diagnostic/history snapshots use `None`. Actual model input uses `Some(remaining_budget)`.
- `codex-rs/core/src/session/vrs_input.rs:137`: the captured `StepContext` determines the current model allowance using the existing `effective_input_token_limit`. Constructing an empty final-format Responses request reserves the base instructions, advertised tools and output schema. Responses Lite's moved prefix items are counted in their actual representation. An exhausted allowance returns `ContextWindowExceeded` before assembly/network; required input exceeding the remaining allowance returns the same error via C rc 2.
- `codex-rs/core/src/session/turn.rs:1196`: A1 and every A2 retry use the same loop and the same base instructions object that will build the request. No first-attempt path uses the process default. `turn.rs:1224` checks the completed, normalized request before sampling.
- `codex-rs/core/src/session/startup_prewarm.rs:407,421`: history prewarm uses the same per-request assembly; all prewarm prompts (including base-only) receive final admission before the prewarm request. The existing early WebSocket connection handshake is separate from transmitting model input.
- `codex-rs/core/src/session/vrs_input.rs:168`: final admission includes input, instructions, tools and response text schema, and rejects an oversized result without dropping evidence or loosening a threshold. The guardian estimator at `core/src/guardian/request_budget.rs:37` is shared, and its existing reviewer-specific margin/check is preserved.

No new locks, shared mutable budget, writer, writer flush, readiness polling, or phase barriers were added. Existing Session locks used by metadata/history remain.

## Evidence boundary

These are the existing byte-based token estimates, not a model tokenizer. `core/src/context_manager/history.rs:633` explicitly calls its estimate coarse and a lower bound. Its `estimate_item_token_count` divides estimated model-visible bytes by four and uses modality heuristics; libvrs's `codex_tokens` also uses byte heuristics. The implementation fixes the missing model/window binding and fixed request overhead. It does not establish an exact physical token upper bound or by itself prove I4's zero overflows. That remains a limitation for L4, not an altered pass threshold. No G/I condition was changed.

## Added regression tests (execution delegated to parent)

- `session::vrs_input::tests::request_window_is_per_call_and_preserves_required_input`: a required direct user item succeeds with a large captured model, fails with a smaller model, and succeeds intact again with the larger model. Exercises explicit C budget propagation and rejects required-input loss or process-wide budget mutation.
- `session::vrs_input::tests::request_window_reserves_base_instructions_before_assembly`: fixed instructions alone exceed the captured window in normal and Responses Lite formats, rejected before attempting to form model input.
- `session::vrs_input::tests::final_admission_counts_tools_and_schema_in_both_wire_formats`: empty prompt is admitted; tool descriptions and output schema each independently trigger local rejection for both representations.
- Existing no-startup FFI test additionally checks an explicit positive budget remains `NotReady` without opening, and zero is `OverWindow` without selecting a default.

Existing recording failure and non-local resume failure tests were updated only to pass the new captured-step/base-instructions parameters; their failure assertions are preserved. `rustfmt` parsing and `git diff --check` passed. Runtime/build status must be read from REPORT3.

## Follow-up: what the byte-bound concern establishes

The captured-model and fixed-cost wiring was re-read after the fixture fixes.
`vrs_prompt_input` uses the captured `StepContext` and the same instructions
object as the subsequent prompt; the final check runs after normalization and
Guardian preparation. Both normal and Responses Lite request builders include
tools and schema. No remaining omitted model override, process-default budget,
or missing tools/schema binding was found in this route.

The unresolved issue is the strength of the cost function. It is not an upper
bound capable of enforcing the physical-window part of D5:

- `guardian/request_budget.rs:37-50` sums the content estimator plus byte-based
  instructions/tools/schema estimates. `context_manager/history.rs:633-634`
  explicitly describes the inherited history estimate as a coarse lower bound.
- `history.rs:1123-1135` estimates a Message from its content only. Roles and
  message framing add zero, and an empty Message adds zero independently of the
  number of other items. Nonempty text uses ceiling(bytes / 4), rather than a
  tokenizer or a documented tokenizer-independent upper bound.
- This is a source witness for the **final Rust estimator's omission**, not a
  complete end-to-end overflow reproduction. External C `codex_tokens` also
  gates selection and counts serialized payload framing. Its own bytes / 4 and
  image/encrypted-content heuristics still do not supply a physical upper bound.
- The guard can therefore certify only that these estimates fit. A real
  tokenizer/backend overflow was not reproduced in this audit. Calling the
  source-level guard an exact prevention mechanism would be incorrect; calling
  this an observed I4 failure would also exceed the evidence. I4 additionally
  requires the specified long-running experiment.

Preserving the old numerical formula while removing waits does not close this
accounting limitation. A stronger admission rule needs a justified cost bound
for each model input modality and opaque payload, or an authoritative tokenizer
and framing contract. An arbitrary safety margin is not proof and must not be
selected from failing test results. This audit did not loosen or tighten a
threshold, change tests, or issue a model request.
