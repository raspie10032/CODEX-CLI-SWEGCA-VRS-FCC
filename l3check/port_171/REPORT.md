# FCC 1.1.7 / upstream 0.171 이식 L3 감사 보고

대상은 `rust-v0.171.0-alpha.13.2` 병합의 production 코드다. 이 절에서는 시험 파일을
감사 대상에서 제외했고, 지시대로 Cargo·빌드·시험은 실행하지 않았다. 기준은
`VRS_코덱스일체화_v1.md` §16의 G_117·U1–U8, §16.1 L1, §16.2 L2와 필요한
§14.5·§15.1·§15.2다.

## a. 충돌 65개와 새 압축 파일 2개

결론: DU 20개는 삭제를 유지했고, UU 45개는 upstream의 압축 무관 변경을 살린 뒤 FCC
이음매를 다시 얹었다. 병합이 새로 추가한 압축 전용 파일 2개도 삭제했다.

- DU 20: `core/src/{compact,compact_model_fallback,compact_remote_history,
  compact_remote_v2,compact_remote_v2_attempt,compact_remote_v2_installation,
  compact_retained_tool_outputs,compact_token_budget}.rs`,
  `core/src/session/async_compaction.rs`, `core/src/tasks/compact.rs`와 대응 시험 5개,
  스냅숏 5개를 삭제 상태로 유지했다. `compact_remote_v2`의 자식 Ret 선택기를 다시
  살리지 않고, `agent/history.rs`에서 무손실 Ret 필터·합집합으로 대체했다.
- 새 압축 파일 2: `core/src/session/compaction_replacement.rs`와
  `core/tests/suite/snapshots/compaction__interrupt_during_remote_compaction_preserves_summary_on_resume.snap`
  은 모두 현재 트리에 없다.
- UU 묶음 A, 5개: `context_manager/history_rejected_audio.rs`,
  `session/{handlers,mod,rollout_reconstruction,session}.rs`. 0.171의 거절 오디오,
  suspension-root, inter-agent delivery 동작을 살리고 압축 설치·재개 메타데이터는 끊었다.
  Ret 원문·롤백·재개 복원과 V114-01 세대를 합쳤다.
- UU 묶음 B, 8개: `session/{startup_prewarm,step_context,tests,turn_input}.rs`,
  `hook_runtime.rs`, `tasks/{mod,mod_tests}.rs`,
  `tools/executed_tool_calls/request_metadata_tests.rs`. 새 sampling interrupt·mailbox·훅
  흐름을 살리고 압축 task와 복원 이력 prewarm을 제거했다. D3 double-prime는 닫았다.
- UU 묶음 B2, 1개: `session/turn.rs`. 0.171의 새 표본·중단·정산 반복에 매 요청
  `vrs_prompt_input`, `check_prompt_window`, `(input_item_count, input_list_generation)`을
  다시 연결했다.
- UU 묶음 C, 19개: `agent/{history,control/sender_context}.rs`, `codex_thread.rs`,
  Guardian core 6개, guardian-v2 async-scorer 9개, `guardian_root_handoff.rs`다.
  누적 이력 대신 VRS 조립을 쓰고, 부모 압축 재사용·checkpoint 길을 제거했으며,
  Ret union F와 live/cold provenance를 보존했다.
- UU 묶음 D, 4개: `rollout/src/{lib,recorder,search}.rs`와 app-server
  `thread_fork.rs`. 0.171의 ordinals·실시간 내구 표지·search 변경을 받고 FCC의
  canonical VRS rollout·reference fork를 보존했다. compact RPC는 계속 명시적 거절이다.
- UU 묶음 E, 8개: `.prettierignore`, workspace `Cargo.toml`·`Cargo.lock`·`deny.toml`,
  `features/src/lib.rs`, scenarios 두 파일과 kickoff 스냅숏이다. workspace는 0.171에
  `codex-vrs`를 합쳤고, 혼합 시험은 압축 기대만 제거하면서 비압축 단언을 살렸다.

## b. U1 압축 실행 경로

두 지정 패턴의 production **압축 실행 참조는 0**이다. 문자열 적중은 아래 호환·스키마·
오프라인 분석 자리뿐이며 어느 것도 압축 요청을 만들거나 이력을 교체하지 않는다.

### 패턴 1 (`p117-work/R2_pattern.txt`)

- `features/src/lib.rs:525,2476-2477`: `AsyncCompactionRootOnly` 기능 ID와 설정 키를
  역직렬화하는 선언이다. 실행 모듈·소비 호출은 없다.
- `history/src/lib.rs:161`: `compaction_without_file_error_sources`는 과거 opaque
  checkpoint를 읽는 직렬화 호환 필드다.
- `rollout-trace/src/reducer/compaction.rs:155`,
  `rollout-trace/src/reducer/conversation.rs:123,188,261`,
  `rollout-trace/src/reducer/mod.rs:76,229`: 이름 일부가
  `pending_compaction_replacement_item_ids`에 걸린다. 저장된 추적 번들을 사후 환원하는
  오프라인 reducer의 비교용 map이며 core model request나 live history를 바꾸지 않는다.

### 패턴 2

- `config/src/schema.rs:111-115`, `core/src/config/mod.rs:684-686,3473-3480,4673`,
  `core/config.schema.json`: 폐기된 `[features.async_compaction]` 입력을 읽고 범위를
  검증하는 설정 호환 및 생성 schema다. 실행 함수 호출은 없다.
- `features/src/feature_configs.rs:216-219,271-272,645-655`,
  `features/src/lib.rs:455,523-525,996,1027-1031,2212-2213,2470-2477`:
  Guardian catalog 필드와 async-compaction 기능 키의 타입·등록 선언이다. core의
  `async_compaction` 모듈과 실행 소비자는 삭제 상태다.
- `protocol/src/openai_models/guardian_v2.rs:42-44`,
  `models-manager/models.json`의 `reuse_parent_compaction`·`max_parent_compaction_tokens`:
  서버/catalog 형식 호환 필드이고 bundled 값도 `null`이다.
- `core/src/hook_runtime/sampling.rs:68`: 들어온 `SamplingKind`가 compaction enum이면
  일반 model-request hook을 고르지 않는 exhaustiveness arm이다. 이 kind를 만드는 FCC
  production 호출자는 없다.
- `hooks/src/events/model_request.rs:115`: `BackgroundCompaction` 직렬화 enum
  discriminant다. 압축 실행자가 아니다.

`task_F_common_116.md` 4b의 설정 파싱·history 읽기 호환 제외와
`L1_compaction.md` 4(c)의 feature-key 및 `pending_compaction_replacement_item_ids`
거짓 양성 규칙을 적용했다. `run_*compact`, 새 창, 요약 설치, remote/background 압축,
Guardian 부모 압축 재사용으로 이어지는 production 호출은 없다.

## c. U3 폴백 금지와 V117-01

### 조립 실패가 오류로 가는 길

- `session/vrs_input.rs:58-67`의 `vrs_error_to_codex`는 `OverWindow`를
  `ContextWindowExceeded`, `NotReady`와 나머지를 요청 미전송 `Fatal`로 바꾼다.
- `session/vrs_input.rs:235-263`의 `vrs_prompt_input`은 `vrs_input(...).await` 오류를
  `map_err(vrs_error_to_codex)?`로 올리고, 빈 조립본도 `Fatal`로 막는다.
- 실제 표본 입구 `session/turn.rs:1460-1468`과 history prewarm
  `session/startup_prewarm.rs:407-415`는 모두 `vrs_prompt_input(...).await?`다.
- path 조립 `session/vrs_input.rs:164-174`는 wait task의 join 결과와 내부 VRS
  `Result`를 `??`로 모두 푼다. `vrs_history_for_path`에는 누적 이력 폴백이 없다.
- `session/vrs_input.rs:366-368`의 live `vrs_history`, `session/mod.rs:5203-5210`의
  `conversation_history_snapshot`, `session/guardian_checkpoint.rs:11-15`의
  `guardian_fork_history`도 조립 오류를 `Result`로 보존한다.
- Guardian core, guardian-v2, agent live/cold fork, app-server sample/fork, realtime,
  extension tool 호출자를 전수 역추적했다. 직접 `?`로 올리거나
  `GuardianReviewOutcome::Error`·`fail_closed`·`SessionFailed`로 바꾸며, 성공한 것처럼
  빈 snapshot을 쓰는 갈래는 없다.

오류를 즉시 상위로 반환하지 않는 두 cache 최적화는 모델 입력 폴백이 아니다.
`startup_prewarm.rs:183`의 speculative prewarm `Unavailable` 및
`vrs_input.rs:358-363`의 private cache 선설치 경고 뒤에도 다음 실제 턴은 다시
`vrs_prompt_input`을 부른다. 누적 live history를 대신 전송하지 않는다.

### 발견하고 고친 결함

`guardian/review_request.rs:350-365`의 cached approval 현재성 검사가
`get_guardian_package(...).await.ok().flatten()`으로 root VRS 조립 오류를 `None`으로
버리고 있었다. 이를 명시적 `match`로 바꾸어 실패를 경고하고 `false`를 반환하게 했다.
따라서 조립 실패 뒤 cached approval을 성공으로 재사용하지 않는다. 층은 L3, 영향은
G_117 막음(D5/U3 오류 은폐 제거)이다.

수정 뒤 production에서 VRS 조립·snapshot wrapper의 `let _ =`, `.ok()`, `if let Ok`,
`unwrap_or*`, 중첩 `Result` 한 겹 누락을 다시 검색했다. 추가 결함은 0이다.

### V117-01

- 비 MCP 길 `tools/registry.rs:938-943`은
  `notify_tool_start(...).or_cancel_tool(...).await??`로 취소 결과와 snapshot 결과를
  모두 푼다.
- MCP 길 `tools/handlers/mcp.rs:274-277`은 바깥 `or_cancel_tool`이 없으므로
  `notify_tool_start(...).await?` 한 겹이 맞다.
- snapshot 본체 `tools/lifecycle.rs:39-45`는
  `conversation_history_snapshot().await` 실패를 `FunctionCallError::Fatal`로 바꾼다.
  따라서 VRS 조립 실패 뒤 실제 도구 handler로 진행하지 않는다.

## d. D3 double-prime

- `session/step_context.rs:60-63`: `incremental_tools_feature()`는 항상 `None`.
- `session/step_context.rs:66-69`: 새 창의 `incremental_tools_enabled()`는 따라서 항상
  `false`.
- `session/world_state.rs:63-69`: 기존 창의
  `current_window_uses_incremental_tools()`는 history를 읽지 않고 항상 `false`.
- `session/world_state.rs:76-82`: 새 창과 기존 창 모두 위 두 false 스위치만 소비한다.
- `tools/spec_plan.rs:1123-1130`: `incremental_tools_enabled = false`이고
  `incremental_exec_enabled`는 이 값과 AND된다.
- `tools/spec_plan.rs:1141`: 중첩 exec 정의도 그 false 값에서만 생긴다.

production의 `Feature::IncrementalExecTools` 소비자는 이 `spec_plan.rs` 한 곳뿐이다.
Responses Lite·Bedrock·GCP·중첩 exec 우회는 모두 닫혀 있다.

## e. U6 무직렬, Ret 비용, V114-01

### 새 직렬 구조 0

FCC 이식 줄에는 새 전역 잠금, semaphore, notify, barrier, 단계 wait, flush 장벽,
항목 도착 순서를 강제하는 큐가 없다.

- Ret 라이브 기록은 `context_manager/always_retained.rs:14-35`에서 persistent
  `HashSet<String>`으로 ID를 한 번 조회하고 원문 envelope를 append한다. 항목마다 기존
  Ret 목록을 선형 탐색하거나 ID 집합을 다시 만들지 않는다.
- 재개는 `always_retained.rs:45-82`의 `RetentionReplay`가 rollout을 한 번 순회하면서
  현재 user-turn 단위만 임시 보관하고 rollback을 적용한다.
  `rollout_reconstruction.rs:226-253`, `vrs_input.rs:193-228` 모두 같은 streaming
  reducer를 쓴다.
- Ret union F는 `agent/history.rs:114-143`에서 `retained_by_id` map과
  `assembled_ids` set을 각각 한 번 만들고 합친다. Ret 항목마다 F 목록을 다시 훑지 않는다.
- 부모 live Ret snapshot `session/mod.rs:5184-5187`은 기존 session-state 잠금을 한 번
  잡고 `Arc<Vec<_>>`를 복제할 뿐 새 잠금 객체나 순서 계약을 만들지 않는다.
- `rollout/src/recorder.rs:1093-1105,1779-1828`의 `realtime_sync_pending`와
  `sync_data` 장벽은 upstream 0.171의 audio/realtime 내구 동작 그대로이며 FCC 이식
  diff가 새로 만든 구조가 아니다.

### V114-01 세대 규칙

`ContextManager`에서 live item 목록을 통째로 바꾸는 production 자리는 모두 세대와
경계를 함께 처리한다.

- `context_manager/history.rs:840-851` `remove_first_item`: 실제 제거 때
  `usage_list_generation += 1`, `reset_last_usage_boundary()`.
- `context_manager/history.rs:872-943` `replace_assembled_with_suffix`: 교체 뒤 세대 +1,
  경계 reset. `retained_context`, `rejected_audio_file_ids`, `file_audio_durations`, Ret
  원문은 건드리지 않는다.
- `context_manager/history.rs:951-973` `replace_annotated`: 교체 뒤 세대 +1, 경계 reset.
- `replace_assembled`은 `history.rs:865-868`에서 위 suffix 함수로 모인다. 삭제된
  `replace_compacted` production 자리는 없다.

요청과 응답의 pair는 다음처럼 이어진다.

- `history.rs:791-793` `usage_cut()`가 현재 `(items.len(), usage_list_generation)`을
  함께 돌려준다.
- `session/vrs_input.rs:350-353` `live_history_usage_cut()`과
  `session/turn.rs:1468,1534,2410`이 같은 요청의 길이·세대를 캡처해 sampling 함수에
  넘긴다.
- `session/turn.rs:3101-3108`이 완료 응답에서
  `TokenUsageContext::Sampling { input_item_count, input_list_generation: Some(...) }`을
  전달한다. Guardian denial resample의 첫 소비 응답은 `SpendingOnly`라 경계를 갱신하지
  않고, `turn.rs:3123-3134`의 같은 prompt 재표본 뒤 최종 응답만 원래 pair를 쓴다.
- `session/mod.rs:5463-5471`이 pair를 `update_token_info_from_usage`로 전달하고,
  `history.rs:1118-1144` `update_token_info_for_list`가 세대가 같을 때만 길이를 새 경계로
  쓴다. 세대가 다르면 교체 함수가 세운 경계를 유지한다.
- `history.rs:1194-1204`의 usage 이후 slice는 stale count를 clamp해 숨기지 않는다.

0.171이 `ContextManager`에 추가한 `sampling`과 `restored_through_sequence`는 item-list
index가 아니라 sequence 추적이다. 새 live-list count/index/cursor 필드는 없으며,
기존 `last_server_reported_usage_item_count`만 위 세대 검사를 거친다.

## 이번 실행의 변경과 검증 경계

- production 변경: `codex-rs/core/src/guardian/review_request.rs` 한 곳.
- `git diff --check`는 해당 변경에서 이상 0.
- Cargo·시험은 지시대로 실행하지 않았다. 이 보고의 결론은 production 소스·이식 diff·
  호출자 역추적 감사 결과다.
- Antigravity 독립 검토는 로컬 설정 로그 쓰기와 `127.0.0.1:0` 소켓 권한 때문에 분석
  세션 생성 전에 실패했다. 위임 에이전트의 별도 source audit은 U3/D3 double-prime
  결과와 일치했고, 최종 판단은 직접 재검증한 코드에 근거한다.
