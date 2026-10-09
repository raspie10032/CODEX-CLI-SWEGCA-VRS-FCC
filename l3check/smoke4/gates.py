#!/usr/bin/env python3
"""Execute the requested five live gates against the final release only."""
import concurrent.futures, hashlib, json, pathlib, subprocess, time

root = pathlib.Path(__file__).resolve().parent
build = root.parent / 'release4b.json'
while 'exit_code' not in (b := json.loads(build.read_text())):
    time.sleep(5)
if b['exit_code']:
    raise SystemExit('Release build failed')
binary = root.parents[1] / 'codex-rs/target/release/codex'
with binary.open('rb') as f:
    digest = hashlib.file_digest(f, 'sha256').hexdigest()
assert digest == b['binary_sha256']

def run(case, resume=None):
    cmd = ['taskset', '-c', '0-11', 'python3', str(root/'run.py'), case,
           '--binary', str(binary), '--timeout', '600']
    if resume:
        cmd += ['--resume', resume]
    subprocess.run(cmd, check=True)
    r = json.loads((root/case/'result.json').read_text())
    m = json.loads((root/case/'command.json').read_text())
    assert m['binary_sha256'] == digest
    r['base_pass'] = (r['exit_code'] == 0 and not r['timed_out'] and
        r['vrs_receipts'] > 0 and not r['vrs_failed_receipts'] and
        not r['vrs_error_lines'] and not r['event_errors'] and
        not r['command_failures'] and bool(r['rollouts']) and
        all(x['nul_bytes'] == 0 and x['final_newline'] and
            not x['parse_errors'] and x['ordinals_strictly_increasing'] and
            x['compaction_events'] == 0 for x in r['rollouts']))
    r['pass'] = r['base_pass']
    if case == 'S1':
        r['pass'] &= r['final_messages'][-1].strip() == 'hello' and r['executed_commands'] >= 1
    elif case == 'S2':
        r['pass'] &= 'a.txt' in r['final_messages'][-1] and 'hello' in r['final_messages'][-1]
    elif case.startswith(('S3','S4')):
        r['pass'] &= r.get('all_20_files_correct',False) and r['line_total'] == 210 and r['executed_commands'] >= 10 and '210' in r['final_messages'][-1]
    elif case == 'S5':
        r['pass'] &= bool(r['request_start_seconds']) and min(r['request_start_seconds']) <= 5
    (root/case/'gate.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
    return r

results = {}
results['S1'] = run('S1')
results['S2'] = run('S2', results['S1']['thread_id'])
results['S3'] = run('S3')
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
    for case, result in zip(['S4A','S4B'],pool.map(run,['S4A','S4B'])):
        results[case] = result
intervals = [(json.loads((root/c/'command.json').read_text())['started_unix_ms'],results[c]['finished_unix_ms']) for c in ['S4A','S4B']]
overlap = max(0, min(i[1] for i in intervals)-max(i[0] for i in intervals))/1000
assert results['S4A']['thread_id'] != results['S4B']['thread_id']
results['S5'] = run('S5')
summary = dict(binary=str(binary), binary_sha256=digest,
               all_passed=all(r['pass'] for r in results.values()) and overlap>0,
               simultaneous_overlap_seconds=overlap, results=results)
(root/'gates.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(dict(all_passed=summary['all_passed'], simultaneous_overlap_seconds=overlap)),flush=True)
