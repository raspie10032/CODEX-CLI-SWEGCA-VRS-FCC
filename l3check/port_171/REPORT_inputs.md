# F3b — U2 입구·U6 Ret·Prov·거절 오디오 감사

작성 시각: 2026-11-25 KST

대상: `p117`, `MERGE_HEAD=ad9d659a84`, production Rust 코드

제약: `cargo` 실행 안 함, 시험 파일 감사·수정 안 함, `vrs-lib7/`·`codex-rs/vrs/` 안 건드림

## 0. 결론

- U2 누락 0: 누적 live history가 provider 입력으로 직접 가는 production 길은 0개다.
- raw/live history 폴백 0: 조립 실패를 누적 이력으로 대신 보내는 길은 찾지 못했다.
- A4′ 0: `PrewarmInput::Restoring`, `has_file_image`, 복원 이력 prewarm 소비는 production에서 없어졌다.
- Ret/Prov 결함 2개를 L3에서 고쳤다.
  1. agent 재개와 V9-01 legacy subagent가 A20 VRS payload만 복사하고, A 밖의 Ret·보존 메타와 live 부모 Prov를 버렸다. 두 길을 기존 `prepare_parent_items_for_fork`로 합쳤다.
  2. 저장 롤아웃 Ret 재생이 `is_api_message`가 아닌 retained envelope를 Ret 술어보다 먼저 버려 live 기록과 달랐다. API 여부는 턴 경계 계산에만 쓰고 Ret는 같은 줄의 `is_always_retained()`로 기록하게 고쳤다.
- 수정 뒤 Ret의 live/재개/path 술어, rollback 뜻, 새 자식/포크 전달, 토큰 무선별, Prov의 live checkpoint/저장 ⊤가 §16.1·16.2와 일치한다.
- V116-01 거절 오디오와 0.171 `media_availability`는 모두 VRS 조립 뒤 요청 사본의 `for_prompt` 정규화에서만 적용된다. S와 A를 바꾸지 않는다.
- §10 지시문 빼기, §12 예측 포크, V9-01, `sender_context`, D3″, V114-01 자리가 남아 있다.

독립 읽기 전용 재검토와 아래 기계적 census를 서로 대조했다. `l3check/audit3_inventory.py`는 출력이 `l3check/port_169`로 고정되어 있고 0.169용 수동 `clone_history` 분류표를 내장하므로 실행하지 않았다. 그 스크립트의 검색 축을 현재 트리에서 처음부터 다시 셌다.

## 1. U2 모델 입력 입구 전수

판정 기준은 “모델 모양의 값을 만든다”가 아니라 “사용자 thread history를 실제 모델 요청에 싣는가”이다. 전달·예산·디버그·자체 대화는 따로 표시했다.

| 자리 | 현재 production 자리 | 판정과 근거 |
|---|---|---|
| A1 첫 요청 | `core/src/session/turn.rs:1460,1472` | `vrs_prompt_input(...).await?` 뒤 `build_prompt`; VRS 조립, 실패 전파 |
| A2 재시도 | `session/turn.rs:1448–1477` | sampling `loop` 안에서 매 시도 A1과 같은 VRS 조립을 다시 함 |
| A3 전송 | `core/src/client.rs:1322` | 이미 만든 `Prompt.input`을 `ResponsesApiRequest`로 직렬화; history 선택 자리가 아님 |
| A4 History prewarm | `session/startup_prewarm.rs:403–421`, 호출 `codex_thread.rs:366` | `History`만 `vrs_prompt_input`; `Base`는 빈 입력 |
| A4′ 복원 prewarm | production 호출 0 | enum은 `Base/History`뿐이고 `session/session.rs:2180`은 `Base`; `Restoring`·복원 `clone_history().for_prompt()` 없음 |
| A5 prompt debug | `core/src/prompt_debug.rs:91–130` | live clone을 표시용 `prompt.input`으로 돌려줌; provider sampling 호출 없음 |
| A6·A7 압축 요청 | `session/handlers.rs:273,883` | 압축 모델 요청 삭제; 남은 RPC는 unsupported 응답 |
| A8 Guardian pending budget | `guardian/input_budget.rs:96–104` | `vrs_history()` 뒤 `for_prompt_annotated`; VRS 결과의 예산 측정 |
| A9 Guardian final/request budget | `guardian/input_budget.rs:151–175`, `guardian/request_budget.rs:39–55` | VRS 결과로 request를 만들어 크기만 측정; raw history 읽기 없음 |
| A10 부모 검토 이력 | `guardian/review.rs:296–310` | `session.vrs_history()`; 실패하면 reviewer 시작 전 오류 |
| A11 검토 전달 | `guardian/review_session.rs:348–354` | A10/A13의 VRS `ContextManager`를 소비; 독립 raw-history 입구 아님 |
| A12 검토 부기 | `guardian/review_session_setup.rs:41,168–169` | VRS snapshot의 mode/history_version만 읽음; provider 입력 아님 |
| A13 Guardian prewarm 부모 | `guardian/review_session_setup.rs:340–356` | `parent.vrs_history()`를 reviewer 준비에 전달 |
| A14 Guardian-v2 scorer | 시작 `tools/lifecycle.rs:37–41`; 소비 `ext/guardian-v2/.../observation.rs:165,330–336`; 요청 `sampler.rs:213` | `conversation_history_snapshot()` 구현이 `session/mod.rs:5203–5210`의 `vrs_history()` |
| A15 realtime 시작 문맥 | `core/src/realtime_context.rs:59–68`, 호출 `realtime_conversation.rs:1735–1745` | 현재 thread 부분은 `sess.vrs_history()`로 생성 |
| A16 realtime 전달 | `realtime_conversation.rs:1726–1750` | A15 결과와 명시적 realtime prompt를 결합; history 재선택 없음 |
| A17·A19 기억 추출 | `memories/write/src/phase1.rs:272–314`, 전송 `runtime.rs:370–381` | 완료 rollout 파일을 읽는 독립 추출 작업; live thread I2 모델 입력 대상 아님 |
| A18 별도 thread | `memories/write/src/runtime.rs:410–447`, `ext/guardian-v3/src/conversation.rs:59–90` | `InitialHistory::New` 별도 thread; 실제 요청은 그 thread의 A1/A2 |
| A20 agent 포크·재개 | `agent/history.rs:247–312,316–424`; 호출 `agent/control/spawn.rs:318,1177`, 일반 fork `:871`, host fork `agent/host/spawn.rs:55` | live는 `vrs_history`, cold는 `vrs_history_for_path`; 저장 ResponseItem은 버리고 Ret∪F/Prov helper로 다시 만듦 |

추가 A20 계열:

- V9-01: `core/src/thread_manager.rs:1530–1578`. live/cold 모두 VRS를 얻은 뒤 같은 Ret∪F/Prov helper를 쓴다.
- `sender_context`: `agent/control/sender_context.rs:72–127`. live sender는 VRS-backed snapshot, cold sender는 `vrs_history_for_path`; guardian retained exchange만 receiver에 기록한다.
- `thread/sample`: `app-server/src/thread_sample.rs:130,218–243,353`. snapshot은 mode/revision/AdditionalTools 판별이고, 참조 포크 자식 요청은 A1/A2다.
- 예측 포크: `app-server/src/request_processors/thread_processor.rs:5489–5636`. loaded parent를 요구하고 `reference_fork_marker`/`prepare_reference_fork` 계보를 만든다. snapshot은 AdditionalTools 판별뿐이며 모델 입력은 자식 A1/A2다.
- Guardian-v3 housekeeper는 실제 `ResponsesApiRequest`를 만들지만 사용자 thread 누적 history가 아니라 housekeeper 자체 append-only vector를 쓴다(`housekeeper_sampler.rs:43,93,140–149,208`). 기본도 꺼져 있다.

### 1.1 기계적 census

- `build_prompt(`: production 호출 5, 정의 1.
  - VRS 모델 입력/측정: normal sampling(A1/A2), History prewarm(A4), Guardian budget(A9).
  - VRS 조립 예산 산출용 빈 입력: `session/vrs_input.rs:243`.
  - 비전송 debug: `prompt_debug.rs:124`.
- 실제 `Prompt {` 생성: `session/turn.rs:1364` 한 곳. 별도 `Prompt::default()` production은 완료 rollout 기억 추출 `memories/write/src/phase1.rs:294` 한 곳이다.
- `clone_history()` production 호출식: 11. provider 입력 0. debug 1, 오디오 수락/거절 부기 1, feedback 1, reviewer version 1, shutdown telemetry 1, 토큰/메모리·도구-origin·raw event 검증 등 비전송 6이다.
- 외부 `for_prompt*` production 소비: 4. VRS-backed 3(`guardian/input_budget.rs` 2, `vrs_input::normalize_for_prompt` 1), 비전송 debug 1. `ContextManager::for_prompt` 내부 forwarding 1은 별도다.
- `conversation_history_snapshot()` production 호출식: 16. Session/CodexThread 출발은 모두 `session/mod.rs:5203–5210`에서 `vrs_history()`로 닫히고, 나머지는 이미 VRS로 받은 immutable `ContextManager` snapshot이다.
- `include_history: true`: production 리터럴·의미 경로 6. app-server read view 1, legacy fork seed 1, external migration 3, thread-store `load_history` 구현 1이다. provider 직접 dispatch 0.
- prewarm production 생성: `Base` 2(`codex_thread.rs:357`, `session/session.rs:2180`), `History` 1(`codex_thread.rs:366`), `Restoring` 0.
- 직접 production `ResponsesApiRequest`: 3. `core/src/client.rs:1322`는 이미 만든 Prompt, Guardian-v2는 VRS snapshot evidence, Guardian-v3 housekeeper는 자기 history다.
- 최종 U2 수: live 누적 history→provider 직접 0, raw-history 폴백 0, A4′ 우회 0.

## 2. Ret — 정의와 구현

### 2.1 기록 자리

Ret 표지가 생길 수 있는 production ResponseItem 기록은 공통 `record_annotated_conversation_items` → `record_prepared_conversation_items` → `state.record_vrs_history`로 모인다(`session/inject.rs:179–197`, `session/mod.rs:3974–4108`). 같은 `ResponseItemEnvelope`에 다음 순서가 적용된다.

1. client developer/tool-output retain 표지를 붙인다(`session/inject.rs:158–171`, `turn_input.rs:1190–1207`).
2. `VrsLiveCache::record`가 `ContextManager::record_annotated_items`를 부른다(`state/vrs_live_cache.rs:66–82`).
3. `record_annotated_items`는 원 envelope에 provenance/sequence를 붙이고, 바로 다음 반복에서 같은 envelope의 `is_always_retained()`를 `AlwaysRetained`에 합친다(`context_manager/history.rs:576–590`).
4. 그 뒤 바로 그 envelope를 `RolloutItem::ResponseItem`으로 persistence한다(`session/mod.rs:4094–4108`).

별도 기록 길도 대조했다.

- inter-agent 전달 결과 `session/mod.rs:4635–4680`도 같은 `record_vrs_history` 뒤 같은 envelope를 persist한다.
- initial/fork history는 `rollout_reconstruction`의 Ret 재생으로 되살린다.
- loaded-thread goal update, unloaded goal direct recorder, realtime event, world-state, shutdown child result의 직접 기록은 retain 표지를 만들지 않는다. 따라서 Ret 줄을 우회해 기록하는 길은 없다.

### 2.2 재개·path·rollback

- 공용 `RetentionReplay`는 retained 줄을 원 envelope로 스트리밍 수집하고 id로 첫 항목만 남긴다(`context_manager/always_retained.rs:44–84`). 전체 rollout 복제나 매 항목 Ret 전체 재탐색이 없다.
- 이번 수정으로 `is_api_message`는 instruction-turn 경계 계산에만 적용되고, Ret는 live와 똑같이 그 줄의 `is_always_retained()`로 판정한다(`always_retained.rs:51–58`).
- 재개는 `rollout_reconstruction.rs:224–253`에서, cold path는 `session/vrs_input.rs:188–229`에서 같은 `RetentionReplay`를 쓴다.
- `ThreadRolledBack`는 현재 살아 있는 instruction-turn 수를 낮추고 그 뒤 턴에 속한 Ret를 뒤에서 제거한다. ResponseItem user boundary와 InterAgentCommunication boundary를 둘 다 센다. 재개와 path가 같은 함수라 뜻이 갈리지 않는다.
- 재개 결과는 `session/mod.rs:1945–1989`, path 결과는 `vrs_input.rs:177–181`에서 `restore_always_retained`로 넣는다. VRS assembly 교체는 이 독립 Ret 집합을 지우지 않는다.

### 2.3 새 자식·포크·재개

- fresh child: `agent/history.rs:51–87`이 부모 세션의 `always_retained()`를 그대로 원문 기록 순으로 복사한다. `clone_history`나 토큰 예산 선택이 없다.
- full/partial agent fork: `agent/history.rs:376–424`가 live `vrs_history` 또는 cold `vrs_history_for_path`에서 Ret와 F를 얻어 `prepare_parent_items_for_fork`로 합친다.
- A20 agent 재개: 이번 수정 뒤 `agent/history.rs:247–312`가 저장 host 메타만 남기고 model-visible ResponseItem을 Ret∪F로 교체한다.
- V9-01: 이번 수정 뒤 `thread_manager.rs:1530–1578`도 같은 helper를 쓴다.
- 합치기: `agent/history.rs:112–155`가 F에 없는 Ret를 Ret 원문 순서로 F 앞에 두고, 같은 id는 F payload를 유지하면서 네 보존 메타(`retain_across_windows`, `retained_source`, `history_truncation_token_limit`, `image_replay_sources`)를 되돌린다. §16.1/16.2의 정해진 배열이다.
- `select_retained_items`와 Ret token-budget 선택 production 호출은 0이다. 창을 넘으면 뒤의 D5 request-window 검사에서 오류가 나며 Ret 일부를 골라 버리지 않는다.

## 3. Prov

- live A20: `prepare_parent_items_for_fork`가 기존 검색 provenance를 먼저 지우고 `SearchOwner::checkpoint(parent_store, items)`로 현재 부모 상태를 모든 상속 항목에 찍는다(`agent/history.rs:104–155`). 일반 fork, agent 재개, V9-01 모두 이번 감사 뒤 이 helper를 사용한다.
- cold path: helper에 `None`을 주므로 저장 줄의 불완전한 과거 증거를 상속하지 않는다. 시작 이력에 checkpoint가 없으면 upstream `SearchOwner::restore`의 정의대로 ⊤=`SearchMcp`다(`model_search.rs:148–203`).
- 참조 포크도 §16.2의 “증거를 모르는 저장/참조 쪽은 ⊤” 규칙을 유지한다.
- 결론: live 부모 상태 checkpoint 있음, cold/path 기본 ⊤, raw stored history 폴백 없음.

## 4. 거절 오디오와 `media_availability`

- `vrs_prompt_input`은 먼저 A를 조립하고 live durable rejection set을 임시 `ContextManager`에 복사한 뒤 `normalize_for_prompt`를 부른다(`session/vrs_input.rs:245–277,323–332`).
- `ContextManager::for_prompt_annotated`의 한 요청 사본에서 순서대로:
  1. input modality 정규화,
  2. `replace_unresolvable_media_files`로 못 찾는 file image·tool audio를 placeholder로 치환,
  3. `project_file_audio_for_prompt`로 provider가 거절한 user file audio를 제거한다(`context_manager/history.rs:686–715`).
- `media_availability.rs:21–126`과 `history_rejected_audio.rs:221–266` 모두 `ResponseItem`/aligned metadata 모양을 보존해 요청 사본만 바꾼다. S 원문, A 집합, Ret 원문 envelope를 바꾸지 않는다.
- live 거절 집합은 terminal provider error에서 누적되고, 재개는 `rollout_reconstruction.rs:221–253`, cold path는 Ret와 같은 단일 rollout read(`vrs_input.rs:188–229`)에서 복원된다.
- 결론: V116-01과 새 media 정규화가 같은 VRS 후단 `for_prompt` 사영에 들어가며, 한쪽만 raw/live history에 적용되는 갈래는 없다.

## 5. 나머지 이음매

- 지시문 빼기 §10: `session/mod.rs:1679–1703`의 request-copy `without_compaction_guidance`/`without_update_plan_instructions`, `session/session.rs:813–835`의 provenance 추정이 유지된다. Custom은 손대지 않는다.
- D3″: `session/step_context.rs:59–68`은 feature `None`, `session/world_state.rs:63–71`은 history를 읽기 전에 `false`를 반환한다.
- 예측 포크 §12: `thread_processor.rs:5489–5636`의 loaded-parent 제한, reference marker, `prepare_reference_fork`가 유지된다.
- V9-01: `thread_manager.rs:1530–1578`을 A20 VRS+Ret/Prov 길로 고쳤다.
- `sender_context`: `agent/control/sender_context.rs:72–127`의 live VRS snapshot/cold path VRS 조립이 유지된다.
- V114-01: A1/A2는 VRS 설치 직후 `live_history_usage_cut()`으로 `(count,generation)`을 함께 잡고(`turn.rs:1460–1468`), sampling 사용량에 `input_list_generation`을 전달한다(`turn.rs:1534,2410,3107`; `history.rs:1114–1140`). 다른 세대면 오래된 count를 현재 목록 경계로 쓰지 않는다.

## 6. 수정·검증

production 수정:

1. `codex-rs/core/src/agent/mod.rs` — 공용 Ret∪F/Prov helper를 crate 안에 노출.
2. `codex-rs/core/src/agent/history.rs` — agent 재개에 VRS Ret∪F/Prov 공용 처리.
3. `codex-rs/core/src/thread_manager.rs` — V9-01 live/cold VRS 및 Ret∪F/Prov 공용 처리.
4. `codex-rs/core/src/context_manager/always_retained.rs` — Ret 술어를 API 필터와 분리.

협업 기록:

- production 수정 직전 `~/tmp/p117-work/prod_fixes.md`를 다시 읽었다.
- 두 수정의 `파일:줄 · 이유 · 층 · G 영향 · 작업자`를 `prod_fixes.md`에 남겼다.
- `git diff --check`는 위 4 production 파일에서 이상 0이다.
- `cargo`·시험·컴파일은 지시대로 실행하지 않았다. 시험 파일과 기대값도 바꾸지 않았다.

최종 판정: F3b 범위에서 남은 production 결함 0. U2 빠짐 0, U6 Ret/Prov 정의 불일치 0, 거절 오디오/media 사영 우회 0, 지정 이음매 유실 0.
