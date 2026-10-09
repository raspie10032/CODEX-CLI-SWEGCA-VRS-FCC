# D4 live cache concurrency audit (source evidence)

Audited HEAD: `fb8f133f4492a9e6a1a846973c60adf8948534ac`, plus the current VI-31 working changes in `session/vrs_input.rs`. No product source was modified. No build or runtime test was run for this audit.

**Finding: real lost-update and stale-install windows in the D4 cache.** Model input still returns the assembled A directly; this finding does not prove that the lost cache record itself is omitted from a later model request.

## Evidence

| Location | Observed behavior |
| --- | --- |
| `VRS_코덱스일체화_v1.md:129` | D4 requires A at the last assembly plus records after that point. |
| `codex-rs/core/src/session/vrs_input.rs:101` | Synchronous FFI computes A without holding the session state mutex. This is appropriate for concurrent assembly. |
| `codex-rs/core/src/session/vrs_input.rs:84` | After FFI, the caller awaits separate cache installation. |
| `codex-rs/core/src/session/vrs_input.rs:202` | Installation takes the existing session mutex and unconditionally replaces history with A; there is no publication/snapshot token or suffix reconciliation. |
| `codex-rs/core/src/session/mod.rs:3483` | A record enters H while holding the session mutex. |
| `codex-rs/core/src/session/mod.rs:3497` | Only after releasing that mutex does the record await `persist_rollout_items`, which publishes to VRS. |
| `codex-rs/core/src/session/mod.rs:4245` | Publication can await `LiveThread::append_items`; the ephemeral path also obtains session state later. |
| `codex-rs/core/src/context_manager/history.rs:584` | Ordinary record append pushes an item without incrementing `history_version`. |
| `codex-rs/core/src/context_manager/history.rs:719` | Equal A installation is a revision no-op; changed replacement increments `history_version`. |
| `$WORK/vrsint/vrs.h:25` | The C assembly API returns JSON, not a snapshot generation or ingestion watermark. |

Allowed interleavings:

1. **Post-snapshot record lost:** A reads S; R appends x to H and publishes x; A obtains the mutex and replaces H with its earlier result. x is absent until another cache refresh even though D4 requires the suffix.
2. **Pre-snapshot pending publication lost:** R appends x to H, then suspends before VRS publication; A reads S without x and installs; R publishes x but never appends to H again. The next cache refresh is required to recover x.
3. **Stale assembly wins:** A_old reads an older S and is descheduled before installation; A_new reads newer S and installs; A_old later overwrites it. The session mutex makes each replacement atomic but does not make the snapshot/install pair atomic.

The parent should treat this as an L2/L3 cache publication defect (continuity consumers and I7), and record the chosen correction in §5.5. `vrs_history` uses `with_assembled_items(items)` at `vrs_input.rs:222`, so the model-bound result must continue to use A alone, regardless of the cache reconciliation choice.

## Smallest safe correction and its limit

An optimistic token under the **existing** session mutex can prevent data loss without holding that mutex through FFI or persistence:

- Track a separate cache/record revision and in-flight publication state. Begin publication tracking before the H append; finish it after VRS publication. Cancellation must leave the item protected or latch a recording error rather than falsely mark it published.
- Before FFI, capture the token. Install only when no publication was in flight at capture, none is in flight now, and the relevant record/cache revision has not changed. Advance the cache installation generation even for an equal-items installation, while preserving `ContextManager::history_version` semantics for guardian cursors.
- A conflicting cache update is discarded immediately; A is still returned to the model. There is no wait, retry loop, new lock, or fallback.

**This is only a safety fix, not by itself a complete D4/I7 implementation.** Repeated conflicts can prevent every cache replacement and let H grow indefinitely. A `history_version()` check alone is also incorrect because ordinary appends do not advance it. Do not report full D4/I7 completion from this guard alone.

## G-preserving completion without a quiet-period dependency

The smallest complete cache protocol needs both a generation and a bounded delta, rather than retrying until records stop:

1. Under the existing state mutex, assign each accepted record batch a local cache sequence and retain its envelopes as a delta; separately mark publication pending/completed. These numbers are private cache bookkeeping, not a new ordering dependency for VRS insertion or A.
2. Capture a refresh ticket and the local cut before FFI. The ticket never blocks another request. Keep the pending-at-cut identities so a record accepted before the cut but published during/after FFI cannot disappear.
3. On installation, reject a superseded refresh ticket. For a current ticket, install A plus the post-cut delta and pending-at-cut records, deduplicated by stable item identity with the assembler's representation taking precedence for items already present in A. Preserve original host metadata for surviving records. Do not pass this union to the model.
4. Retire completed delta entries covered by the committed cut; retain only post-cut and still-pending entries. Successful refreshes can now bound H even when records overlap every assembly. A stale/in-flight refresh must not pin the journal after a newer refresh has committed.
5. Clarify D4's operational cut in §5.5: cache t0 is the admitted refresh cut; locally accepted records whose publication crosses that cut belong to the cache suffix. The C API exposes no exact S snapshot watermark, so do not pretend a Rust start/end counter proves the actual C snapshot order. D3 and the model request remain exactly A, and I1–I8 stay fixed.

Required deterministic tests should control the three interleavings above, include an in-flight record accepted before the cut, verify duplicate identities are not re-appended, show a late older refresh cannot overwrite the admitted newer cache, and show repeated overlapped refreshes retire completed deltas. None was executed by this read-only audit.

## Implementation after the audit

The parent subsequently authorized source changes. VI-32 in §5.5 records the conservative D4 cache contract and the exact-watermark gap. `state/vrs_live_cache.rs` now implements the complete generation/delta protocol above. `VrsPublication` uses a per-batch atomic status to preserve failure/cancellation without adding a lock or requiring an async cleanup task. `SessionState::check_vrs_recording` latches that error before assembly and before installation.

The ordinary conversation and inter-agent recording paths reserve the journal entry under the existing state mutex with their H append, then publish outside that mutex. Goal updates continue to publish before changing live authorization and now use the common publisher for fileless VRS sessions. A destructive reset invalidates older refresh tickets and old delta payloads while preserving failed/unfinished publication status.

Reconciliation uses the original processed cache envelopes, not a second provenance-capture pass. It preserves current host metadata when that metadata was updated after recording, using the journal as a fallback. Stable IDs suppress overlap duplicates. For ID-less items, identical content cannot identify the source occurrence: an old item in A may look identical to a new unpublished record. Ambiguous ID-less overlaps are retained temporarily and retired at the next refresh covering publication. Equal-items refreshes still supersede old cache tickets without changing the guardian-visible history revision. Model input remains the unmerged A.

Eight deterministic tests were added under `state::vrs_live_cache::tests`, including 256 consecutive refreshes with an overlapping record on every refresh and an identical-content ID-less old/new record pair. These tests had **not been compiled or executed when this implementation was committed**; the parent owns serialized compilation and execution. Formatting and `git diff --check` were completed. The source inspection result does not replace I4/I7/I8 runtime evidence.
