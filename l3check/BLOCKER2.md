# P-3′ reservations do not preserve the existing paginated history contract

Status: **blocked**. Evidence: source inspection, not a reproduced runtime failure.
Implementation and tests were stopped upon confirming this contract conflict.
Existing edits were committed for review; no alternative design was implemented.

## Exact conflict

`VRS_코덱스일체화_v1.md:439–443` requires the caller to obtain an ordinal with
one atomic `fetch_add`, serialize the line, and obtain its byte offset with a
separate atomic `fetch_add(len)`. The implementation follows those steps at
`codex-rs/rollout/src/recorder.rs:2075`, `:2079`, and `:2080`.

Two concurrent recording callers can legally execute:

1. A obtains ordinal 1, then is preempted during serialization.
2. B obtains ordinal 2, serializes, and reserves offset x.
3. A finishes serialization and reserves offset x + len(B).
4. Both writes complete successfully at their reserved offsets.

The file now has physical ordinal order `…, 2, 1`. These are successfully
inserted and written records, not NUL holes or permanently lost queue entries.
Changing atomic memory order or writer scheduling cannot repair the relationship
between already allocated ordinals and byte offsets.

## Existing consumers require matching ordinal and byte prefixes

| Location | Contract and consequence |
| --- | --- |
| `codex-rs/rollout/src/ordinal.rs:67,80,98` | Resume reads the last physical valid ordinal and adds one. For `2,1`, it reuses ordinal 2. |
| `codex-rs/thread-store/src/local/thread_history_materialization.rs:224` | An ordinal below `next_ordinal` is discarded. Reading physical `2,1` discards the successfully persisted line 1. |
| Same file `:286,299,323` | A forward ordinal gap becomes `SkippedOrdinalRange`, and the checkpoint advances beyond it. |
| `codex-rs/thread-store/src/local/thread_history.rs:144,202,223` | Projection lines and skipped ranges must match one increasing ordinal checkpoint, stored alongside a byte checkpoint. |
| `codex-rs/protocol/src/protocol.rs:3101,3111,3113` | `HistoryPosition` describes one immutable prefix using both the first excluded ordinal and the byte offset after the last included JSONL record. These prefixes need not coincide under physical order `2,1`. |
| `codex-rs/thread-store/src/local/paginated_fork.rs:105,126` | Latest/ThroughTurn fork boundaries propagate this coupled ordinal/byte position. |
| `codex-rs/thread-store/src/local/model_context.rs:122,184` | Model-context lineage reads use the byte boundary. |
| `codex-rs/thread-store/src/local/rollout_lineage.rs:227,269` | Lineage logic also uses the ordinal boundary. |

Using max ordinal + 1 on resume fixes only ordinal reuse. Sorting a completed
file for one projection does not resolve immutable prefix semantics, incremental
checkpoint advancement, or smaller ordinals arriving after a checkpoint.

## Scope and the preexisting lock

`codex-rs/thread-store/src/local/live_writer.rs:335` holds a preexisting
per-thread lock over its normal write-and-project path. Calls exclusively through
that path are currently serialized and do not exhibit the interleaving above.
This audit does **not** claim that an ordinary CLI session has reproduced data loss.

The recorder itself is `Clone` (`recorder.rs:86`), shares reservation atomics
(`:91`), and exposes `record_canonical_items(&self, ...)` (`:1046`). Neither that
API nor P-3′ confines all callers to the existing upper-level lock. Treating the
lock as the missing universal contract would restrict the concurrent recording
contract rather than establish it.

The document needs to decide how ordinal order, reserved byte order, and
paginated resume/projection/fork positions relate. Choosing a caller restriction,
changing reservation allocation, or changing the prefix protocol here would be
an implementation-selected design change. The task explicitly forbids that.

## Work and validation boundary at stop

- P-3′ caller insertion, offset writes, `vrs_written`, and NUL-aware readers were
  implemented, but paginated concurrency remains blocked as described above.
- VI-13–VI-18 source changes were committed; whole-workspace validation is pending.
- Baseline `3da13917bdc` integration enumeration completed: 1,987 passed,
  359 failed, 7 ignored, 0 timed-out execution entries (2,353 total; deadline
  120 seconds per exact-name invocation). The binary lists 96 names twice;
  `--exact` selects both cases for such names, and the harness repeated those
  filters. Unique-name outcomes are 1,940 passed, 310 failed, 7 ignored.
  Repeated names had consistent exit outcomes but shared log paths; these are
  exact-filter results, not individually disambiguated duplicate test cases.
- The current rollout unit-test executable compiled against the stub. It was
  not executed. The current core integration suite and release CLI were not built.
- The real archive initially lacked `vrs_written`. A final read-only symbol check
  found it; relinking was not attempted after the design stop.
- No running app, Codex session, or vrs9 service was stopped or restarted.
