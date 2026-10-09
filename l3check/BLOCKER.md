# L3 중단 근거

점검 대상은 `a99cec1bb41eda740b8b871f316e57a1b0f59af7`와 시작 시 존재한
`code_mode.rs`, `vrs/src/lib.rs`의 미커밋 변경이다. 이번 작업은 제품 코드를
수정하지 않았다. 설계대로 진행할 수 없는 곳에서 멈추라는 요청에 따라
아래 결정을 임의로 내리지 않고 중단했다.

## 중단 지점: 최신 입력 반영과 단계 대기 금지

- `codex-rs/core/src/session/vrs_input.rs:83`: 조립마다
  `sess.flush_rollout().await`로 writer 완료를 기다린다.
- `codex-rs/core/src/session/mod.rs:1430`: `flush_rollout`은 live thread의
  `flush`를 기다린다.
- `codex-rs/rollout/src/recorder.rs:1035`: 기록 호출은 `AddItems`를 비동기
  큐에 넣고 반환한다. 호출자가 반환받은 시점은 VRS 삽입 완료 시점이 아니다.
- `codex-rs/rollout/src/recorder.rs:1074`: `flush`는 큐에 barrier를 넣고
  `rx.await`로 writer 확인을 기다린다.
- `codex-rs/rollout/src/recorder.rs:2112`: 실제 파일 끝 위치를 읽은 뒤
  `write_all`, 파일 `flush`, `vrs_insert`를 실행한다. 따라서 새 조립은
  기존 단일 writer의 완료에 의존한다.

설계의 P-3(`VRS_코덱스일체화_v1.md:241`)와 P-6 D1(`:284`)은 삽입을
기록기의 줄 쓰기 자리에 놓는다. I6(`:27`), E3-3(`:327`)은 새 조립의
단계 대기를 금지한다. 현재 배치에서 barrier만 제거하면 `AddItems`의
최신 직접 발화가 아직 VRS 집합에 없는 상태로 조립할 수 있어 I5(`:26`)를
보장할 수 없다.

고정 C API인 `$WORK/vrsint/vrs.h:21`부터 `:25`에는 Rust writer의
미처리 항목이나 스레드별 삽입 완료 위치를 전달하는 계약이 없다.
`vrs_ready`의 복원 준비 상태가 Rust 큐의 반영 완료를 의미한다는 계약도 없다.
현재 정의만으로 두 조건을 함께 만족한다고 증명할 수 없으며, 삽입 시점과
파일 오프셋 소유/할당 계약을 임의로 바꾸는 것은 재설계가 된다.

이 근거는 소스 대조 결과다. 최신 입력 누락의 실행 재현 결과라고 주장하지
않는다. C++ 작업장은 읽기만 했으며 변경하지 않았다.

## 중단 전에 확인한 추가 미해결 사항

- `codex-rs/vrs/src/lib.rs:114`, `:153`: 프로세스 전역 `OnceLock`과
  `get_or_init`이 있다. 동시 초기화 호출자는 기다릴 수 있으므로 E3-3을
  통과했다고 할 수 없다. 기존 세션 `Mutex`와는 별개의 신규 코드다.
- `codex-rs/core/src/agent/control/spawn.rs:1012`: A20은 여전히
  `load_agent_model_context`로 부모의 저장된 rollout을 가져온다.
  P-6의 부모 VRS 조립 결과로 바뀌지 않았다.
- `codex-rs/core/src/session/mod.rs:4281`: A14 스냅숏의 조립 실패를
  빈 `ContextManager`로 바꾼다. 호출자는 오류를 전달받지 못하므로 D5의
  요청 차단을 보장하지 못한다.
- `codex-rs/rollout/src/recorder.rs:2116`: `vrs_insert` 오류를 경고만
  기록하고 성공으로 반환한다. 조립 전에 삽입 실패가 전달되지 않는다.
- `codex-rs/tui/src/chatwidget/tests/status_and_layout.rs:229`: 삭제된
  `Config.model_auto_compact_token_limit` 필드 할당이 남아 있다. TUI 테스트
  컴파일 성공을 주장할 수 없다. 이번 실행에서는 컴파일하지 않았다.
- `current_clone_history.tsv`: 80개 호출을 적었다. 69개는 테스트, 6개는
  직접 모델 입력이 아닌 용도, 1개는 전달 helper, 4개는 guardian 입력 구성에
  영향을 주므로 모델 요청에 닿지 않는다고 확인하지 못했다.
- `current_socket.txt`: core의 `UnixStream`/`CODEX_VRS_SOCK`는 0개지만,
  문자 그대로의 `socket`은 `core/src`에 369줄 있다. WebSocket 통신과
  네트워크 설정 및 테스트를 포함한다. "소켓 전체 0"이라고 보고하지 않는다.

## 시험 증거의 한계

- 앞 에이전트의 `suite_real.log`: 2,227개 시작, 1,611 통과, 608 실패,
  6 ignored, 2개 종료 미확인. 전체 종료는 `EXIT 143`; 완주 요약이 없다.
- `failed_tests.txt`: 608줄, 서로 다른 표시 이름은 540개다. 같은 이름의
  테스트가 로그에도 반복되므로 608을 고유 이름 집합의 크기로 쓰지 않는다.
- 앞 에이전트의 `rerun_failed.log`: 1 통과, 607 실패, 1,619 filtered out.
  이것은 기준선 결과가 아니다.
- 기준선은 `3da13917bdcd4d8bede271be71e40000f0ff0bd3`, 별도 worktree
  `$WORK/codexbase`, 별도 target `codexbase/target`이다.
  `--no-run` 빌드를 시작했지만 중단 지점을 확인한 뒤 3.09분에 본 작업의
  cargo PID와 자식 PID만 종료했다. 실제 테스트는 실행하지 않았다.
- 기준선 실패 집합이 없으므로 회귀 차집합과 (a)/(b)/(c) 분류는 미완료다.
  릴리스 빌드와 현재 트리의 잔여 테스트 컴파일도 이번 실행에서 수행하지 않았다.

기존 dirty 파일과 앞 에이전트의 로그를 보존했다. 보호 대상 앱/서비스를
종료하거나 재시작하지 않았고 보호 경로에 쓰지 않았다.
