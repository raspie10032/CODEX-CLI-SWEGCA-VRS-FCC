#!/usr/bin/env python3
"""Run the authorized live smoke case, preserving command, output and exit evidence."""
import argparse, datetime, hashlib, json, os, pathlib, re, signal, subprocess, time

p = argparse.ArgumentParser()
p.add_argument('case')
p.add_argument('--binary', default='$WORK/codexint/codex-rs/target/release/codex')
p.add_argument('--resume')
p.add_argument('--timeout', type=int, default=600)
a = p.parse_args()
root = pathlib.Path(__file__).resolve().parent
out = root / a.case
out.mkdir(parents=True, exist_ok=False)
cwd = pathlib.Path('$WORK/vrsint_smoke') / a.case
cwd.mkdir(parents=True, exist_ok=False)
if a.case.startswith('S1'):
    (cwd / 'a.txt').write_text('hello\n')
    prompt = 'a.txt 파일 내용을 읽고 그 내용을 한 단어로 답해.'
elif a.case.startswith('S2'):
    prompt = '방금 내가 뭘 물었고 너는 뭐라고 답했지?'
elif a.case.startswith(('S3', 'S4')):
    prompt = ('현재 폴더에 f01.txt부터 f20.txt까지 파일 20개를 만들어. 번호 i인 파일에는 '
              'hello 줄을 정확히 i개 넣어. 실제 도구를 최소 10회 이상 호출해야 해. '
              '파일 생성은 호출마다 정확히 두 파일씩, 10번의 서로 다른 도구 호출로 해. '
              '그 다음 별도 도구 호출에서 wc -l로 20개 파일 각각의 줄 수와 합계를 확인하고 '
              '최종 답에 합계를 말해. 이 폴더 밖 파일은 수정하지 마.')
else:
    prompt = '한 단어 hello만 답해.'
cmd = ['taskset', '-c', '0-11', str(pathlib.Path(a.binary).resolve()), 'exec']
if a.resume:
    cmd += ['resume', a.resume]
cmd += ['--skip-git-repo-check', '--json', '-m', 'gpt-6-astra', '-c',
        'model_reasoning_effort="low"', prompt]
env = os.environ.copy()
env.pop('CODEX_VRS_SOCK', None)
env.pop('CODEX_VRS_DUMP', None)
env.update(CODEX_HOME='~/.codex', CODEX_VRS_LOG=str(out / 'vrs.jsonl'),
           RUST_LOG='error,codex_api::responses_websocket_timing=trace',
           OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1')
with open(a.binary, 'rb') as f:
    binary_sha256 = hashlib.file_digest(f, 'sha256').hexdigest()
meta = dict(command=cmd, binary_sha256=binary_sha256, cwd=str(cwd), environment={k: env[k] for k in
            ['CODEX_HOME', 'CODEX_VRS_LOG', 'RUST_LOG']},
            started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            started_unix_ms=time.time_ns() // 1000000, timeout_seconds=a.timeout)
(out / 'command.json').write_text(json.dumps(meta, ensure_ascii=False, indent=2) + '\n')
t = time.monotonic()
with (out / 'stdout.jsonl').open('w') as stdout, (out / 'stderr.txt').open('w') as stderr:
    proc = subprocess.Popen(cmd, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                            stdout=stdout, stderr=stderr, start_new_session=True)
    meta['pid'] = proc.pid
    (out / 'command.json').write_text(json.dumps(meta, ensure_ascii=False, indent=2) + '\n')
    try:
        rc = proc.wait(timeout=a.timeout)
        timed_out = False
    except subprocess.TimeoutExpired:
        # Terminate only this subprocess; no pattern or unrelated session matching.
        proc.terminate()
        try:
            rc = proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            rc = proc.wait()
        timed_out = True
events = []
for line in (out / 'stdout.jsonl').read_text().splitlines():
    try:
        events.append(json.loads(line))
    except json.JSONDecodeError:
        pass
thread = next((e.get('thread_id') for e in events if e.get('type') == 'thread.started'), a.resume)
errors = (out / 'stderr.txt').read_text()
receipts = [json.loads(l) for l in (out / 'vrs.jsonl').read_text().splitlines()] if (out / 'vrs.jsonl').exists() else []
result = dict(exit_code=rc, timed_out=timed_out, elapsed_seconds=round(time.monotonic()-t, 3),
              finished_unix_ms=time.time_ns() // 1000000,
              thread_id=thread, vrs_receipts=len(receipts),
              vrs_failed_receipts=[r for r in receipts if r['outcome'] != 'assembled'],
              vrs_error_lines=[l for l in errors.splitlines() if re.search(r'VRS.*(failed|unavailable)|rollout writer failed|failed to record rollout', l, re.I)],
              event_errors=[e for e in events if e.get('type') in ('error', 'turn.failed')],
              final_messages=[e['item'].get('text') for e in events if e.get('type') == 'item.completed' and e.get('item', {}).get('type') == 'agent_message'])
if receipts:
    result['first_assembly_seconds'] = (receipts[0]['unix_ms']-meta['started_unix_ms'])/1000
    result['first_assembly_us'] = receipts[0]['us']
timing_lines = [l for l in errors.splitlines() if 'responses websocket timing' in l and 'warmup=false' in l and str(thread) in l]
timings = re.findall(r'request_start_ms="?(\d+)"?', '\n'.join(timing_lines))
result['request_start_seconds'] = sorted(set((int(v)-meta['started_unix_ms'])/1000 for v in timings if int(v)>=meta['started_unix_ms']))
commands = [e['item'] for e in events if e.get('type') == 'item.completed' and e.get('item',{}).get('type') == 'command_execution']
result['executed_commands'] = len(commands)
result['command_failures'] = [c for c in commands if c.get('exit_code') != 0 or c.get('status') != 'completed']
if thread:
    paths = list(pathlib.Path('~/.codex/sessions').rglob('*'+thread+'*.jsonl'))
    result['rollouts'] = []
    for path in paths:
        raw = path.read_bytes()
        lines, parse_errors = [], []
        for index, line in enumerate(raw.splitlines()):
            if not line.strip():
                continue
            try:
                lines.append(json.loads(line))
            except (json.JSONDecodeError, UnicodeDecodeError) as err:
                parse_errors.append(dict(line=index+1, error=str(err)))
        ordinals = [l.get('ordinal') for l in lines]
        result['rollouts'].append(dict(path=str(path), bytes=len(raw), nul_bytes=raw.count(b'\0'), final_newline=raw.endswith(b'\n'),
          lines=len(lines), parse_errors=parse_errors, ordinals_strictly_increasing=bool(ordinals) and all(isinstance(x, int) for x in ordinals) and all(x < y for x,y in zip(ordinals,ordinals[1:])),
          compaction_events=sum(l.get('type') == 'compacted' or l.get('payload',{}).get('type') in ('compacted','context_compaction','context_compacted','compaction_trigger','compaction') for l in lines),
          tool_calls=sum(l.get('type') == 'response_item' and l.get('payload',{}).get('type') in ('function_call','custom_tool_call','local_shell_call') for l in lines)))
files = sorted(cwd.glob('f[0-9][0-9].txt'))
if files:
    result['file_lines'] = {f.name: len(f.read_text().splitlines()) for f in files}
    result['line_total'] = sum(result['file_lines'].values())
    result['all_20_files_correct'] = len(files) == 20 and all(f.read_text() == 'hello\n'*int(f.name[1:3]) for f in files)
(out / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(result, ensure_ascii=False), flush=True)
