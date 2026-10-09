# VI-27 diagnostic candidate and latest VI-28 publication audit

Status: **diagnostic candidate only, not real-library integration success**.
The refreshed patch is applied only to the untracked local source copy at
`l3check/library_candidate3/vrs_lib.cpp`. This agent did not compile, link, or run
it and did not write anything under `$WORK/vrsint`. The parent may build the isolated
copy for diagnosis; that result must remain separate from real-library results.
Only this report, the patch, and the hash manifest are committed.

The exact inspected owner inputs are:

| Input | SHA-256 |
| --- | --- |
| `$WORK/vrsint/vrs_lib.cpp` | `f741af0163ebc71d910321819ab4b8ff6aa2fc0fe2b88f7e36a09073d7a9388f` |
| `$WORK/vrsint/vrs.h` | `2336f4c191c53157190d7e6edabb517a670de0e346eb697f81b0084547e0a5ab` |
| `$WORK/vrsint/libvrs.a` | `75ce1177d15a8e01703aec8bb30fc2c7ac5192e7b581adbca059104bf6e3ff42` |
| Refreshed patch | `3165615c15583350ed90dbecd74fc8dc99925f97a081cf53d1c5a85af6c9b280` |
| Patched diagnostic source | `5057eea44557cab675cfc5a6204830735db1906ad465e30e076d4e4e74541645` |
| Local design document at inspection | `e38d39e22457c2a799952c1ab081a5b6de26dfbdce4aa8ee5e568049814c7f1b` |

The owner source is copied unmodified to the untracked
`l3check/library_candidate3/owner_f741af0.cpp`; the candidate header is an exact
copy of the inspected header. `git apply --check` passed against a temporary
copy of this owner source. Applying the patch there also produced bytes identical
to the prepared candidate. These are patch applicability checks, not C++ checks.
Protected source, header, and library hashes were rechecked before preparing the
candidate. They can change independently after this audit.

All owner-source line references below refer to **f741af0**, not older revisions.
Prior source/library identities remain in `vrs_library_candidate3.json`. Prior
`library_deferred3.cpp` / `library_deferred3.json` results are historical evidence;
they are not runtime results for the new owner binary or this candidate.

## VI-27 cause and candidate scope

The new owner publication change did not remove VI-27:

| Owner location | Behavior | Consequence |
| --- | --- | --- |
| 3097 | `make_sess` permanently sets `memmode` from initial file absence | Delayed persistent rollouts become indistinguishable from permanently ephemeral ones |
| 3324 | `vrs_insert` skips UW storage in `memmode` | No pending copy exists for the later persistence acknowledgement |
| 3343 | `vrs_written` returns -3 for a missing UW key | Normal delayed materialization fails |
| 879, 1667, 2583 | `memline` stores another original and bypasses UW on fetch | Merely adding UW leaves a permanent duplicate after acknowledgement |
| 2600, 3213 | Memory mode disables file-tail paths | Later file creation does not enable the ordinary file reader |
| 2166, 2194 | Memory mode disables shard creation and confirmed watermarks | Delayed persistent rows miss ordinary index persistence |
| 2250, 2252 | Memory mode excludes closed turns from B | Reference-turn membership depends on file creation timing |

The candidate preserves the latest owner's D8 implementation, `InNode` without
completion pointers, `want_count` scheduling, enqueue-and-return behavior,
`insert_left` accounting, `vrs_dbg` ABI, and all publication comments. It neither
restores the deleted completion wait nor silently substitutes the older source.
The C ABI is unchanged. The patch only makes the following storage changes:

1. Remove permanent `memmode` and duplicate `memline` originals. Every newly
   inserted key retains its bytes in the existing per-session CAS UW set.
2. Read UW first for every path, then the original file after acknowledgement.
   Source selection no longer depends on whether the file initially existed.
3. Keep `vrs_written` as the only normal release of a pending original. Ephemeral
   callers never acknowledge, so their pending originals survive for the handle
   lifetime. Persistent originals are released after their write acknowledgement.
4. Permit the ordinary file-tail reader for all paths. Missing files follow its
   existing open-failure return; live NUL-stop and restore-hole rules remain.
5. Include every closed turn in B, following D1 (`VRS_코덱스일체화_v1.md:101`) and
   D3-prime (352–356). This includes ephemeral turns and can change outputs. It
   is a semantic correction requiring owner review, not a bookkeeping claim.
6. Keep existing `wbuf` index records while the original file is absent, and let
   a later ordinary owner batch flush them after materialization. If index
   persistence is disabled, discard `wbuf` as before. The existence check only
   gates disk index persistence; it does not classify the session or choose raw
   bytes, and it never releases UW originals.

The byte-lifetime argument is limited to the caller's immutable-row contract:
`uw_add` retains the original at `(path, off)`. A protected UW reader copies it
before acknowledgement. A reader observing UW removal reads the already-written
and flushed file. An ephemeral row is never acknowledged. This does not prove
model visibility: assembly selects IDs from a published snapshot first, so bytes
present in UW cannot make an unpublished item appear in A.

The patch adds no lock, thread, queue, owner election, polling, or completion wait.
It reuses existing UW CAS operations and owner-only `wbuf`. This is not an E3-3
pass; the existing library still serializes per-session publication and contains
other waiting paths, detailed below.

## Latest VI-28 change: removed wait, remaining stale-success path

The latest owner removed `InNode::done`, the caller's stack completion atomic,
and the explicit yield-until-done loop. That fixes the dangling-pointer concern
that would arise from deleting only the old wait. It does **not** establish the
successful-insert visibility contract of P-3-prime.

Current source flow:

| Owner location | Operation |
| --- | --- |
| 845 | `InNode` has only offset, line, and next pointer |
| 3330 | Insert publishes its node into the session inbox by CAS |
| 3331 | A ready insert sets `want_count` |
| 3047–3051 | `drain` returns false immediately if another thread holds `busy` |
| 3332–3333 | Insert records `insert_left` on that false result and returns 0 |
| 3025–3032 | The owner takes a batch, feeds rows, then calls `post_batch` |
| 3017, 2800 | The owner eventually publishes a new immutable snapshot |
| 3217–3221 | Assembly reads the last snapshot; only `lin_pending` causes rc 1 |

A concrete permitted execution is enough to identify the source defect:

1. A ready session already has a nonempty published snapshot and `curA > 0`.
2. Thread O holds `busy`, has exchanged the inbox at 3025, and is descheduled.
3. Thread I inserts the next user row, wins the inbox CAS, loses `busy`, and
   returns 0 at 3333. No owner has yet applied that new row.
4. The same caller immediately assembles. Because `curA > 0`, the one-time
   file-read branch at 3213 does not run. The snapshot has no lineage pending
   condition and contains only the prior rows; assembly can return rc 0 without
   the just-accepted direct utterance.
5. O can publish the missing row later. That does not repair the request already
   assembled from the stale snapshot.

This is a source interleaving, **not an executed concurrency reproduction**.
Neither the candidate nor the new owner `insert_left` counter closes this gap.
The local contract says that on insert return the row is in S (442), closing-turn
contributions are counted within the call (452), and A corresponds to completed
inserts (454). D3 defines model input from the current S (109–110), and I5 requires
all direct utterances (26). Returning success before this publication violates
those contracts; classifying enqueue acceptance as completion changes them.

There is a second independent source path even without a competing owner:
`feed` at 2650–2653 places a row beyond the current byte cursor into `held`.
The batch can then publish an unchanged prefix and insert returns success. P-3
atomic reservation does not force callers to invoke FFI in reservation order:
a caller holding the earlier reservation may be descheduled. A later accepted
row can therefore be invisible until that earlier caller inserts. UW preserves
its bytes but not its membership in the snapshot. This is not the permitted
other-process live-file NUL rule; the same-process input already returned success.

The owner comments cite `§5.6 P-7` at 3325 and `§5.6 D8` at 337/2267. The inspected
local design ends at §5.5 and has no §5.6 or P-7. That unavailable reference cannot
establish a reviewed local change to the return contract. A pure aggregation
representation by itself also does not prove publication visibility: the live
path still invokes it through offset-ordered `feed` and one `busy` owner.

`insert_waits == 0` is not evidence that insertion never waits. The field is
initialized at 1076 and read at 3400, with no increment sites. Both insertion and
assembly can still yield waiting for a newly-created session pointer (3109,
3124); UW hazard acquisition can yield when all slots are occupied (1177–1182),
and assembly snapshot hazard acquisition likewise yields (2805–2810). The restore
worker separately loops on `busy` (3070). The old explicit completion loop is
gone, but a zero counter does not certify these paths or the absence of a single
per-session publishing owner (870, 3034–3051).

Rust cannot make snapshot membership true by waiting for disk flush, checking
`vrs_ready`, adding retries, or falling back to accumulated live history. Nor
would restoring the old completion wait solve the held-gap case or I6. The
library needs a publication procedure that meets both the accepted-set contract
and the no-wait/no-single-writer requirement. This storage candidate deliberately
does not attempt to substitute a new publication definition.

## Assumptions and limits requiring owner review

- `vrs_written(path, off)` is called only after writing and flushing exactly that
  previously inserted immutable row. The acknowledgement is a caller promise,
  not an independent disk verification.
- A live path is not replaced, truncated, unlinked, or reused for different rows;
  distinct ephemeral generations already have distinct Rust paths.
- Ephemeral originals remain in UW until handle destruction, as D1/P-4 require.
  When index persistence is configured, their unpersisted metadata also remains
  in `wbuf`; this constant-factor cost needs measurement.
- Persistent bytes can be acknowledged before the next owner batch flushes the
  accumulated index. A watcher or later insert provides that batch. Immediate
  process exit leaves originals to parse at startup; the candidate does not
  prove I8's five-second recovery bound for that case.
- Existing shard write failures, key idempotence, file replacement semantics,
  CAS reclamation, and snapshot consistency are preserved, not certified here.
- B now includes ephemeral closed turns. Expected outputs must be derived from
  D1/D3-prime and compared across early/late materialization, not loosened to
  accept whatever this candidate emits.

## Diagnostic and real-library validation still needed

The following are proposed checks; this agent did not execute them:

- Build the prepared candidate with the required CPU and job limits, then run
  the deferred-write reproduction. Require `insert=0, written=0` and identical
  direct utterances before file creation and after acknowledgement.
- Verify UW counters: one pending copy per key, release after acknowledgement,
  no `memline` duplicate; repeated acknowledgement retains the unchanged -3
  contract.
- Insert ephemeral rows, close turns, and assemble later. Verify B membership,
  original bytes, no rollout/shard creation, and no accidental acknowledgement.
- Materialize a delayed file with index persistence, let the ordinary watcher
  process it, reopen, and verify rows, ordinals, contributions, and assembly.
  Include immediate close after materialization and early-file/late-file pairs.
- Reproduce the busy-owner interleaving deterministically and the out-of-order
  reservation/insert gap. Compare the first assembly after successful return,
  not eventual assembly after waiting for background work.
- Check concurrent insert/fetch/written, live NUL gaps, restore holes, duplicate
  keys, lineage, and races with protected UW readers under memory/race tooling.
- Repeat relevant integration tests against an owner-built, hash-identified real
  library after its changes. Candidate success cannot substitute for this step
  or for the full E3-2/E3-3/I1–I8 evidence.
