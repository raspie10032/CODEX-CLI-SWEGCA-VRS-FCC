#!/usr/bin/env python3
"""Run each libtest case in a fresh, affinity-limited process with an individual deadline."""
import argparse, concurrent.futures, datetime, hashlib, json, os, pathlib, re, signal, subprocess, time
p=argparse.ArgumentParser(); p.add_argument('binary'); p.add_argument('output'); p.add_argument('-j',type=int,default=10); p.add_argument('--timeout',type=int,default=120); p.add_argument('--names-file'); a=p.parse_args()
assert 1 <= a.j <= 10
out=pathlib.Path(a.output); out.mkdir(parents=True,exist_ok=True)
started=time.monotonic()
started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat()
with pathlib.Path(a.binary).open('rb') as binary_file:
    binary_sha256=hashlib.file_digest(binary_file, 'sha256').hexdigest()
env=os.environ.copy()
for k in ('CODEX_VRS_SOCK','CODEX_VRS_LOG','CODEX_VRS_DUMP'): env.pop(k,None)
env['PATH']=os.path.expanduser('~/.cargo/bin')+':/usr/local/bin:/usr/bin:/bin'
env['CODEX_HOME']=str(out.resolve()/'home'); pathlib.Path(env['CODEX_HOME']).mkdir(exist_ok=True)
env['RUST_MIN_STACK']='33554432'
env['OMP_NUM_THREADS']='1'; env['OPENBLAS_NUM_THREADS']='1'; env['RAYON_NUM_THREADS']='1'
prefix=['taskset','-c','0-11',str(pathlib.Path(a.binary).resolve())]
listed=subprocess.run(prefix+['--list'],env=env,capture_output=True,text=True,check=True).stdout
registered=[line[:-6] for line in listed.splitlines() if line.endswith(': test')]
# libtest can register duplicate display names. An exact filter already runs all
# such cases; repeating it only races on the log file and counts the cases twice.
names=list(dict.fromkeys(registered))
if a.names_file:
    selected=set(pathlib.Path(a.names_file).read_text().splitlines())
    missing=selected-set(names)
    if missing: raise SystemExit(f'Unknown exact test names: {sorted(missing)}')
    names=[name for name in names if name in selected]
(out/'test_list.txt').write_text('\n'.join(names)+'\n')
def descendants(pid):
    children={}
    for f in pathlib.Path('/proc').glob('[0-9]*/stat'):
        try:
            fields=f.read_text().rsplit(')',1)[1].split(); children.setdefault(int(fields[1]),[]).append(int(f.parent.name))
        except (OSError,ValueError,IndexError): pass
    result=[]
    def walk(parent):
        for child in children.get(parent,[]): walk(child); result.append(child)
    walk(pid); return result

def run(name):
    path=out/(hashlib.sha256(name.encode()).hexdigest()[:20]+'.log')
    cmd=prefix+['--exact',name,'--nocapture','--test-threads=1']; t=time.monotonic(); killed=[]
    with path.open('w') as log:
        proc=subprocess.Popen(cmd,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        try:
            rc=proc.wait(timeout=a.timeout); status='passed' if rc==0 else 'failed'
        except subprocess.TimeoutExpired:
            status='timeout'; killed=descendants(proc.pid)+[proc.pid]
            for pid in killed:
                try: os.kill(pid,signal.SIGKILL)
                except ProcessLookupError: pass
            rc=proc.wait()
    if status=='passed' and re.search(r'test result: ok\. 0 passed; 0 failed; [1-9][0-9]* ignored;',path.read_text(errors='replace')): status='ignored'
    return dict(name=name,status=status,exit_code=rc,seconds=round(time.monotonic()-t,3),log=str(path),killed_pids=killed)
results=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=a.j) as pool, (out/'results.jsonl').open('w') as journal:
    for result in pool.map(run,names):
        results.append(result); journal.write(json.dumps(result)+'\n'); journal.flush()
        if len(results)%50==0: print(f'{len(results)}/{len(names)} completed',flush=True)
summary=dict(binary=str(pathlib.Path(a.binary).resolve()),command=prefix+['--exact','<test>','--nocapture','--test-threads=1'],registered_cases=len(registered),unique_filters=len(set(registered)),selected_filters=len(names),jobs=a.j,rust_min_stack=env['RUST_MIN_STACK'],timeout_seconds=a.timeout,elapsed_minutes=round((time.monotonic()-started)/60,3),counts={s:sum(r['status']==s for r in results) for s in ['passed','failed','ignored','timeout']},complete=len(results)==len(names))
summary.update(started_utc=started_utc,binary_sha256=binary_sha256)
(out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
for status in ('failed','timeout'):
    (out/f'{status}.txt').write_text(''.join(r['name']+'\n' for r in results if r['status']==status))
print(json.dumps(summary),flush=True)
