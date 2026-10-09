# VI-31 fixture audit and VI-33 reminder contract

Source inspection only. No build or test was run by this audit agent. The root agent owns serial build and exact-test execution. This inventory identifies test intent; it does not establish that a particular request exceeds its window or classify a runtime failure as resolved.

## Implemented wording change (c)

Design `VRS_코덱스일체화_v1.md:527` (VI-33), I1 at line 22, and D5 at line 134 remove automatic compaction/reset and expose required-input overflow as a turn error. The bundled reminder in `codex-rs/prompts/src/model_messages.rs:52` now says:

> Your context window is nearly exhausted (only {n_remaining} tokens remaining). Requests whose required input exceeds the context window will return an error.

The exact string assertion in `suite::token_budget::token_budget_reminder_emits_after_crossing_compaction_threshold` (`codex-rs/core/tests/suite/token_budget.rs:873`) follows that contract. Its configured window remains 10,000, synthetic usage remains 8,000, reminder threshold remains 2,000, and expected remaining amount remains 1,000. The test still requires two requests, exactly one reminder, and the same context identity. No limit, threshold, request count, or omission assertion was relaxed. The historical test name is preserved for baseline comparison. This is a wording-only class (c) change, not evidence that the test passes with VI-31 admission.

## Remote-compaction advertisement

Before the root agent's parallel change, `codex-rs/core/src/session/mod.rs:1211–1219` explicitly included `Feature::RemoteCompactionV2` in every model-client beta header, independently of its configuration. `codex-rs/core/src/client.rs:2330–2334` sends that value as `x-codex-beta-features`. This is active advertisement, not configuration compatibility. It contradicts I1 and VI-33 removes the explicit inclusion.

By contrast, `codex-rs/features/src/lib.rs:1920–1924` declares that key `Stage::Removed` with default false; its old config input is ignored at line 633. `codex-rs/tui/src/daemon_startup.rs:106` permits the removed flag from old launch scripts. These are compatibility parsing sites. Retry enum/logging references (`core/src/responses_retry.rs`, `codex-client/src/retry.rs`) should be audited separately as dormant source, not mistaken for this transmitted header.

## Tiny physical windows and retained test intent

The following are metadata/catalog/format tests, not tests granting permission to send oversized requests. No fixture or assertion below was changed during this audit. Do not raise a physical limit, discard an assertion, or label a test (a) merely because admission now rejects its former setup. Before any (c) change, use the actual failure and request cost to show that D5 applies. Preserve the existing content/ordering/budget checks at their rendering boundary and test pre-network rejection separately if the original physical request cannot fit.

All `skills_extension.rs` locations below are under `codex-rs/core/tests/suite/`.

| Test/source | Window | Scope retained |
|---|---:|---|
| `skills_extension.rs:926` `production_turn_aliases_executor_skill_roots` | 3,000 | e0 alias, direct-read instructions, omission of optional usage prose |
| `skills_extension.rs:2032` `production_turn_aliases_catalogs_with_separate_cloud_budget` | 10,000 | e0/c0/r0 roots and all three providers' aliased skills |
| `skills_extension.rs:2158` `production_turn_scales_extension_catalog_from_resolved_model_window`, helper at 2162 | 10,000 then 400,000; usable percent 50 | captured model switch, 2% resolved-window catalog budgets (200/8,000), provider ordering, warning counts, model-attributed telemetry |
| `skills_extension.rs:2422` `production_turn_shortens_host_only_catalog_with_the_full_budget` | 12,000 | shortened descriptions and catalog cost <= 240 |
| `skills_extension.rs:2434` `production_turn_shortens_executor_only_catalog_with_the_full_budget` | 12,000 | shortened descriptions and catalog cost <= 240 |
| `skills_extension.rs:2446` `production_turn_shares_catalog_budget_across_host_and_executor_sections` | 12,000 | shared host/executor cost <= 240 |
| `skills_extension.rs:2466` `production_turn_uses_configured_skill_catalog_token_budget` | 12,000; also model-switch helper | configured catalog limit 800, full descriptions, equal catalog size across models |
| `skills_extension.rs:2526` `production_turn_preserves_host_alias_root_order_across_turns` | 12,000 | exact roots/skill aliases and stable two-turn ordering |
| `skills_extension.rs:3038` `production_turn_omits_host_skills_under_extreme_host_only_pressure` | 2,000 | exact three retained names and one omission warning |
| `skills_extension.rs:3060` `production_turn_preserves_empty_core_compatible_host_fragment` | 1,000 | empty host fragment, missing overlong entry, one exact warning |
| `skills_extension.rs:3090` `successive_turns_do_not_repeat_unchanged_host_budget_warning` | 2,000 | two turns, one warning across both event sources |
| `skills_extension.rs:3112` `production_turn_omits_executor_skills_under_extreme_executor_only_pressure` | 2,000 | exactly exec-alpha and five omitted skills |
| `skills_extension.rs:3126` `production_turn_omits_executor_skills_after_host_skills_under_extreme_pressure` | 2,000 | no host names, one executor name, exact omission markers |
| `skills_extension.rs:3152` `production_turn_omits_host_skills_before_executor_skills_under_extreme_mixed_pressure` | 6,000 | three host names, all executor names, exact warning |
| `skills_extension/cloud_skill_tests.rs:460` `production_turn_aliases_discovered_singleton_cloud_root` | 2,000 | c0 alias, locator guidance, full selected cloud body despite disabled host discovery |
| `token_budget.rs:836` `token_budget_reminder_emits_after_crossing_compaction_threshold` | 10,000 | exact remainder/reminder count and unchanged window identity; wording-only change above |
| `token_budget.rs:888` `get_context_remaining_returns_token_budget_remaining_fragment` | 10,000 | tool exposure and exact 6,500 remainder after synthetic 2,500 usage |
| `code_mode.rs:3894` `code_mode_get_context_remaining_returns_structured_result` | 10,000 | successful nested tool and exact JSON `tokens_left: 9000` |

Shared skills helpers `skills_extension.rs:520–578` set the real model window and then demand a sent request. Constants at lines 265–270 drive both physical admission and independent catalog sizing. The smallest setups therefore have two separate contracts that cannot be conflated. The 40,000-token full-catalog cases at lines 2512, 3010, and 3021 are also catalog tests; they are not presumed failures.

Actual admission-policy tests are `guardian_context_budget.rs:42` (28,000 required-instruction rejection), `:209` (one-token required-context rejection), and `:606` (160,000 fit vs 16,000 rejection, preserving user-approval/required-review distinction and the next complete review). Their physical limits are their subject and must remain unchanged. VI-31's session unit tests in `session/vrs_input.rs` additionally exercise captured-model budget, fixed instructions, tools, and schema. Those checks are separate from the metadata fixtures above.

## Verification boundary

The audit used tracked-source searches and inspected test bodies, the final-request estimator, the feature spec, and header generation. The reminder change was checked with `git diff --check` and the staged patch review. There was no build, exact-test run, network request, or snapshot acceptance by this agent. Await root-owned execution before reporting runtime success or assigning remaining failures to (b)/(c).
