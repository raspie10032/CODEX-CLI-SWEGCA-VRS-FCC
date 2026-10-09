status: smoke_passed_binary_ready
scope: "S1–S5 실제 실행과 바이너리 산출 완료. 전체 회귀 해소 및 I1–I8 전체 통과는 미완료."
binary:
  path: $WORK/codexint_deploy/codex-2207
  sha256: 27b9e2d369e933113a06b2a720f27a2c705a599fe6e94183c05570959f308563
  bytes: 1417121072
  matches_tested_binary: true
  codex_link_changed: false
  app_or_service_restarted: false
commits:
  - hash: 1dd1eff1288b2e09295ad52a236461f80bad83a4
    title: Avoid shared media cache waits during VRS request admission
  - hash: ad4597ae4a808295abb5340bfddafc1765454c3a
    title: Honor VRS persistence acknowledgements and publish rollout file identity
  - hash: 5546fb314fbe30f87eed8d31983419458f549568
    title: Keep VRS classification tables alive through process shutdown
build:
  cwd: $WORK/codexint/codex-rs
  command: "VRS_LIB_DIR=$HOME/tmp/codexint/vrslib_frozen taskset -c 0-11 cargo build --release -j 10 -p codex-cli"
  exit_code: 0
  minutes: 10.353
  evidence: l3check/release4b.json
  log: l3check/release4b.log
  library_sha256: 66bdc739d08e5ec071851c6834a8dc7cb8926f6be304dc8c714291f413c06417
  library_source_patch: l3check/library4_candidate/shutdown_static_lifetime.patch
  original_library_modified: false
smoke:
  all_passed: true
  code_home: ~/.codex
  workspace_root: $WORK/vrsint_smoke
  runner: l3check/smoke4/gates.py
  exact_commands_and_outputs: "l3check/smoke4/{S1,S2,S3,S4A,S4B,S5}/"
  evidence: l3check/smoke4/gates.json
  S1:
    exit_code: 0
    seconds: 6.281
    answer: hello
    vrs_errors: 0
    rollout_exists: true
    nul_bytes: 0
    valid_json_lines: 23
    ordinals_strictly_increasing: true
  S2:
    exit_code: 0
    seconds: 4.974
    same_session: true
    previous_question_and_answer_correct: true
    vrs_errors: 0
  S3:
    exit_code: 0
    seconds: 45.852
    tool_calls: 11
    files: 20
    independently_verified_line_total: 210
    vrs_errors: 0
  S4:
    exit_codes: [0, 0]
    seconds: [46.402, 49.065]
    simultaneous_overlap_seconds: 46.403
    tool_calls: [11, 11]
    independently_verified_line_totals: [210, 210]
    vrs_errors: 0
  S5:
    exit_code: 0
    first_actual_request_seconds: 2.241
    maximum_allowed_seconds: 5
    total_seconds: 4.874
    existing_index_used: true
    segfaults: 0
  all_executions:
    vrs_errors: 0
    segfaults: 0
    compaction_events: 0
    cumulative_history_fallbacks: 0
    fallback_evidence: "모델 입력 소스 경로 확인과 VRS 조립 성공 기록 109건. 별도 폴백 계측기를 추가하지는 않음."
    rollout_nul_bytes: 0
    rollout_ordinals_strictly_increasing: true
tests:
  count_unit: "중복 표시 이름을 합친 정확 이름 필터. 한 필터는 같은 이름의 등록 시험을 함께 실행한다."
  command: "taskset -c 0-11 <core-test-binary> --exact <name> --nocapture --test-threads=1"
  concurrent_jobs: 10
  per_filter_timeout_seconds: 120
  baseline:
    source: l3check/baseline3/results.jsonl
    rerun_this_pass: false
    passed: 1940
    failed: 310
    ignored: 7
  ours_before:
    source: l3check/ours3_after/results.jsonl
    passed: 276
    failed: 1759
    timeout: 36
    ignored: 49
    baseline_new_failures_or_timeouts: 1497
  ours_after:
    source: l3check/ours4/results.jsonl
    complete: true
    filters: 2120
    passed: 1601
    failed: 470
    timeout: 0
    ignored: 49
    minutes: 1.991
    baseline_new_failures: 172
  comparison: l3check/comparison4.json
  remaining_difference_list: l3check/new_failures4.txt
  classification:
    a: "이번 차수에서 삭제하거나 끈 시험 없음. 이전 비활성 시험은 그대로 실행 목록에 포함."
    b: "172개 기준선 신규 실패의 전수 분류·수정 미완료. 회귀 0으로 판정하지 않음."
    c: "이번 차수에서 기대값 또는 통과 문턱을 바꾼 시험 없음."
  test_compile:
    command: "VRS_LIB_DIR=$HOME/tmp/codexint/vrslib_frozen taskset -c 0-11 cargo test -j 10 -p codex-core --test all --no-run"
    exit_code: 0
    minutes: 1.636
    evidence: l3check/tests4_build.json
checks:
  run_auto_compact: 0
  compact_remote_v2: 0
  CompactTask: 0
  replace_compacted_history: 0
  core_UnixStream: 0
  core_CODEX_VRS_SOCK: 0
  source_evidence: l3check/smoke4/source_checks.json
  new_Rust_writer_wait_added: false
  new_Rust_global_lock_added: false
  full_E3_3_pass: false
  frozen_library_I6_limitation: "동일 파일의 다른 처리자 완료 대기가 고정본에 남음. D8/P-7 전환은 이 바이너리에 포함하지 않음."
clone_history_remaining:
  calls: 73
  test_calls: 65
  production_or_helper_calls: 8
  inventory: l3check/clone_history3.tsv
  qualification: "모델 입력의 누적 이력 폴백 없음. 메모리 대상 선정·도구 출처 판단의 간접 제어 영향 2곳은 별도 표기."
design_changes:
  document: VRS_코덱스일체화_v1.md §5.7
  R4_01: "L3, G 막음: 계약에 따라 vrs_written의 0과 -3을 성공으로 받고 다른 오류는 전달."
  R4_02: "L3, G 막음: 첫 삽입 전에 빈 rollout 파일을 create_new로 만들어 영속 세션 정체성 확정."
  R4_03: "L3, G 막음: 고정본 사본의 종료 시 파괴되는 분류 테이블을 상수 배열로, 빈 vector를 호출 지역값으로 변경."
open_issues:
  - "기준선 신규 실패 172개의 (a)/(b)/(c) 분류와 회귀 수정이 남음."
  - "resume fixture의 이전 직접 발화 누락 실패가 있음. 라이브러리의 JSON 필드 순서 의존 파싱 결함을 확인했으나 해당 실패와의 인과 재현 및 수정은 미완료."
  - "고정 라이브러리에 동일 파일 완료 대기가 남아 I6 및 E3-3 전체 통과 아님."
  - "원래 종료 139의 정확한 스택은 확보하지 못함. 정적 수명 결함은 소스 근거이며 수정 후 6개 실제 실행에서 세그폴트 0."
  - "S1–S5는 짧은 실제 실행 관문이다. 장기 실행 I4와 I1–I8 전체 검증을 대체하지 않음."
