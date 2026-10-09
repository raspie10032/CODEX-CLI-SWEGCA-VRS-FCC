# VI-27 library candidate and VI-28 publication audit

Status: **review candidate only**. The patch has not been applied to the owner tree,
compiled, linked, or executed. No replacement library was built. The inspected owner
source still has both defects. `vrs_library_candidate3.json` records exact source,
header, library, and patch hashes and the successful `git apply --check` on an
isolated temporary copy. That check establishes patch applicability only.

During this audit the owner independently updated the source to SHA-256
`c468087b1e7ef0e2c34f3199283e7ea97d76a4f583749abac59d4322076d0732` and the
real library to `cc81fe7547cb8e9f1e0f1f06355ca661bec54ca41cb56c88fda15f8e383c0479`.
The same candidate also passes `git apply --check` on a temporary copy of that
updated source. Its VI-27 insertion condition is now line 3326 and VI-28 wait is
line 3337; both remain in the source. The old runtime reproduction is not a
runtime result for this updated binary. No owner file was written by this agent.

The existing `library_deferred3.cpp` / `library_deferred3.json` reproduction is the
runtime evidence: insertion before the file exists returns 0, the caller writes
and flushes the bytes, and `vrs_written` returns -3. This audit did not rerun it.

## Source cause and why one changed condition is insufficient

All source locations below refer to the unmodified owner source
`$WORK/vrsint/vrs_lib.cpp`, SHA-256
`21ba6146899e8d1b9673e1f78f74d5c9be3d4abd525eb915947d43d5cee485ea`.

| Location | Existing behavior | Consequence for delayed creation |
| --- | --- | --- |
| 2875 | `make_sess` sets permanent `memmode` from initial file nonexistence | A normal delayed rollout is mistaken for a permanently ephemeral thread |
| 3102 | `uw_add` runs only outside `memmode` | No pending copy exists for `vrs_written` to release |
| 3126–3127 | `vrs_written` rejects an absent UW key with -3 | The normal persist/materialize acknowledgement fails |
| 1643, 2360 | `memline` keeps another full original and `fetch` bypasses UW | Adding UW alone would leave a permanent duplicate after acknowledgement |
| 2377, 2991 | Memory mode excludes disk-tail ingestion | Later file creation never enables the ordinary live reader |
| 2142, 2170 | Memory mode excludes shard writes and confirmed watermarks | Delayed persistent sessions never acquire the normal index path |
| 2222–2225 | Memory mode excludes closed turns from B | Ordinary delayed sessions are absent from the reference-turn set |

The last exclusion also conflicts with the explicit current definitions:
`VRS_코덱스일체화_v1.md:101` includes ephemeral rows in S, and line 353 defines B
as all closed turns of S. Therefore the candidate changes B membership as a
required semantic correction. This can change outputs; it is not a harmless
bookkeeping edit and must be reviewed and tested against the definition.

## Review candidate

`vrs_library_candidate3.patch` changes only the C++ implementation; the C ABI is
unchanged.

1. Remove permanent `memmode` and its duplicate `memline` originals. Every newly
   inserted key retains its bytes in the existing per-session CAS UW set.
2. `fetch` reads UW first for all paths, then the original file when UW no longer
   holds the key. No source selection depends on whether the file existed when
   the session was created.
3. Keep `vrs_written` as the only normal release of a UW original. Ephemeral
   callers never issue that acknowledgement, so their originals remain available
   for the handle lifetime. Acknowledged persistent rows stop retaining a UW copy.
4. Use the ordinary file-tail reader for any path; a missing file causes the
   existing `open` failure return. The live NUL stop and restore-hole rules remain.
5. Include every closed turn in B, following D1 and D3-prime.
6. Defer disk index flushing while the original file does not exist. Keep the
   existing owner's accumulated index records in its existing `wbuf`; flush on a
   later ordinary owner batch after materialization. This avoids persisting an
   ephemeral index and avoids discarding the prefix of a delayed file's index.
   With index persistence disabled, discard `wbuf` as before. Neither this check
   nor a later flush releases a UW original; only `vrs_written` does that.

The source-level byte-lifetime argument is narrow and concrete. After insertion,
`uw_add` owns the original at `(path, off)`. A reader that wins before acknowledgement
copies the bytes through `uw_get` under the existing UW hazard protection. A reader
that observes removal reads the flushed original file. Removal is valid because
the caller promises that the bytes are already written and flushed before invoking
`vrs_written`. A path that never materializes has no acknowledgement, so the pending
original remains. No permanent second `memline` copy survives materialization.

The candidate introduces no lock, thread, queue, owner election, busy loop, or
completion wait. It reuses the existing owner-only `wbuf` and the existing UW CAS
operations. This is **not** an E3-3 pass: those existing library operations have the
unresolved serialization described below.

## Assumptions and limitations requiring owner review

- A successful `vrs_written(path, off)` is called only after writing and flushing
  exactly that previously inserted immutable row. The candidate does not try to
  prove a caller's disk write from the acknowledgement itself.
- A live path is not replaced, truncated, unlinked, or reused for different bytes.
  Distinct ephemeral generations already have distinct paths on the Rust side.
- All raw ephemeral rows remain in UW until handle destruction, as D1/P-4 require.
  The patch also retains their unpersisted index records in `wbuf` when an index
  directory is configured. This increases the volatile metadata constant factor
  compared with the old `memmode` branch. It must be measured; it is not a claim
  that ephemeral memory is bounded independently of its own retained rows.
- A persistent row's raw bytes can be released by `vrs_written` before the next
  owner batch flushes `wbuf`. The watcher or later normal insertion supplies that
  batch; the patch does not add a synchronous flush or wait. If the process exits
  first, the originals are present and startup can parse them, but the candidate
  alone does not prove the 5-second restart condition for that case.
- The `access` check controls only whether to persist an index. It no longer
  classifies a path permanently or chooses the raw source. The patch preserves
  existing handling of shard write failures after a file exists; it does not
  claim to fix every shard I/O/error-propagation defect.
- B now includes ephemeral closed turns, as the design requires. Differential
  expected results must be derived from D1/D3-prime, not relaxed to accept whatever
  the candidate produces. Owner review must include comparisons before and after
  materializing the same persistent rows.
- UW CAS contention/reclamation and the owner publication mechanism are reused,
  not certified by this inspection. The source's `uw_slot` retries when all hazard
  slots are occupied (1152–1157), and `get_sess` waits for pointer publication
  (2887, 2902). They remain additional E3-3 audit concerns.

## Owner validation still required

These are proposed checks, not executed checks:

- Rerun `library_deferred3.cpp` against the rebuilt real library. Require
  `insert=0, written=0`, and then assemble the same direct utterance both before
  creation and after acknowledgement.
- Check UW debug counters before/after acknowledgement: one added live copy,
  one release, no retained duplicate; a second acknowledgement remains -3 under
  the unchanged C API contract.
- Insert multiple rows into a never-created ephemeral path. Assemble them after
  later rows and closed turns. Verify no rollout or shard file was created and
  the pending bytes remain.
- Insert a delayed persistent file with `index_dir` enabled, materialize it, let
  the ordinary watcher process it, and reopen. Verify original rows, ordinals,
  closed turns, contributions, and assembly across restart. Include materialize
  then immediate close before another owner batch.
- Compare a file created before insertion with the same rows created afterward;
  verify the intended B membership and reference-turn results. Include a fork of
  the delayed path and an ephemeral lineage parent where the definition applies.
- Exercise concurrent insert/fetch/written on separate and shared paths, including
  acknowledgement concurrent with a protected UW read, reordered disk writes,
  live NUL holes, restart holes, and duplicate insertion. Run memory/race tooling
  in the owner's supported environment. Do not read a failed test as proof that
  its expected result should change.

## VI-28 cannot be hidden by Rust

The current `vrs_insert` publishes an `InNode` carrying a pointer to its own stack
`std::atomic<int> done` (3105–3109), calls `drain` (3110), and then yields until the
pointer is signaled (3113). `drain` (2829–2832) returns immediately when another
thread owns `Sess::busy`. That other owner later takes the inbox, feeds rows and
sets `want_count`, then publishes the batch and finally stores through every saved
completion pointer (`run_batch`, 2802–2811).

Deleting only the loop is unsafe for two separate reasons:

1. The caller's `done` goes out of scope while a later owner still holds its
   address. `run_batch` can then write through a dangling stack pointer.
2. Even if completion pointers are removed too, successful return would no longer
   mean the row and any closed-turn contribution are published. `assemble_impl`
   reads the last immutable snapshot (2994–3002), which can omit that row. Returning
   stale success violates P-3-prime's successful-insert contract and D3/I5.

The current wait also does not establish full out-of-order publication: `feed`
(2428–2431) puts a row beyond the current cursor into `held`; `run_batch` still
signals its completion after `post_batch`. Thus the wait is not proof that a
successfully inserted row beyond a missing earlier row already participates in A.
This follows from source inspection; this audit did not run a concurrency repro.

Rust cannot supply the missing library linearization point. `vrs_ready` only
reports startup readiness, `vrs_written` only acknowledges disk ownership, and a
Rust counter does not expose which immutable C++ snapshot contains which rows or
contributions. Waiting for writer flush, retrying until publication, serializing
all inserts, or falling back to live history would violate the fixed contract.
Moving the FFI call to another worker merely moves the wait.

The library owner must revise its publication procedure so accepted rows and their
required derived state have the promised visibility without waiting for a separate
owner. That includes the per-session owner and ordered `held` structures, not just
line 3113. The VI-27 candidate deliberately does not claim to solve VI-28 and does
not remove the wait or alter the ABI. The real owner library must be rebuilt and
relinked, and both publication and byte-lifetime checks must pass before reporting
E3-3 or the integration as complete.
