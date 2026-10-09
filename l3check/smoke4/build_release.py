#!/usr/bin/env python3
import datetime, hashlib, json, os, pathlib, subprocess, time
root = pathlib.Path(__file__).resolve().parents[2]
out = root / 'l3check'
env = os.environ.copy()
env.update(VRS_LIB_DIR=str(root/'vrslib_frozen'),
           CODEX_HOME=str(root/'l3check/build-home3'),
           CARGO_TARGET_DIR=str(root/'codex-rs/target'), RUST_MIN_STACK='33554432',
           PATH='~/.cargo/bin:/usr/local/bin:/usr/bin:/bin')
cmd = ['taskset','-c','0-11','cargo','build','--release','-j','10','-p','codex-cli']
data = dict(command=cmd,cwd=str(root/'codex-rs'),
            environment={k:env[k] for k in ['VRS_LIB_DIR','CODEX_HOME','CARGO_TARGET_DIR','RUST_MIN_STACK']},
            library_sha256=hashlib.sha256((root/'vrslib_frozen/libvrs.a').read_bytes()).hexdigest(),
            started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
(out/'release4b.json').write_text(json.dumps(data,indent=2)+'\n')
t=time.monotonic()
with (out/'release4b.log').open('w') as f:
    p=subprocess.run(cmd,cwd=data['cwd'],env=env,stdout=f,stderr=subprocess.STDOUT)
data.update(exit_code=p.returncode,elapsed_minutes=round((time.monotonic()-t)/60,3))
if p.returncode==0:
    data['binary_sha256']=hashlib.sha256((root/'codex-rs/target/release/codex').read_bytes()).hexdigest()
(out/'release4b.json').write_text(json.dumps(data,indent=2)+'\n')
print(json.dumps(data),flush=True)
raise SystemExit(p.returncode)
