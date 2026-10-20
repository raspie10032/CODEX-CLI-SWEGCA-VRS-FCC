"""Exercise CLI, resume, app-server and prediction forks with a local provider.

Usage: python3 test-macos-app.py <codex binary> <new output directory>
Requires the user's cached model catalog, but does not use their authentication.
"""
import http.server
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time

binary = Path(sys.argv[1]).resolve()
root = Path(sys.argv[2]).resolve()
root.mkdir(parents=True, exist_ok=False)
home, work = root / "home", root / "work"
home.mkdir(); work.mkdir()
source_home = Path(os.environ.get('CODEX_HOME', Path.home() / '.codex'))
catalog = json.loads((source_home / 'models_cache.json').read_text())
(root / 'catalog.json').write_text(json.dumps({'models': catalog['models']}))
model = 'gpt-6.1-sol'
assert any(m['slug'] == model for m in catalog['models'])
requests = []


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers['content-length'])))
        requests.append(body)
        (root / f'request-{len(requests):03}.json').write_text(json.dumps(body))
        events = [
            {'type': 'response.created', 'response': {'id': f'resp_{len(requests)}'}},
            {'type': 'response.output_item.done', 'item': {'type': 'message', 'role': 'assistant',
             'id': f'msg_{len(requests)}', 'content': [{'type': 'output_text', 'text': 'MAC_FCC_OK'}]}},
            {'type': 'response.completed', 'response': {'id': f'resp_{len(requests)}',
             'usage': {'input_tokens': 5, 'output_tokens': 3, 'total_tokens': 8}}},
        ]
        data = ''.join(f"event: {e['type']}\ndata: {json.dumps(e)}\n\n" for e in events).encode()
        self.send_response(200)
        self.send_header('content-type', 'text/event-stream')
        self.send_header('content-length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)


server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()
(home / 'config.toml').write_text(f'''model_provider = "mock"
model = "{model}"
model_catalog_json = "{root / 'catalog.json'}"
model_reasoning_effort = "low"
[model_providers.mock]
name = "mock"
base_url = "http://127.0.0.1:{server.server_port}/v1"
wire_api = "responses"
requires_openai_auth = false
supports_websockets = false
request_max_retries = 0
stream_max_retries = 0
''')
env = dict(os.environ, CODEX_HOME=str(home), CODEX_VRS_LOG=str(root/'vrs-receipts.jsonl'))
env.pop('CODEX_CLI_PATH', None)
env.pop('CODEX_THREAD_ID', None)


def cli(name, args):
    result = subprocess.run([str(binary), *args], cwd=work, env=env, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=90)
    (root / f'{name}.jsonl').write_text(result.stdout)
    (root / f'{name}.stderr').write_text(result.stderr)
    assert result.returncode == 0, (name, result.returncode, result.stderr[-2000:])
    events = [json.loads(x) for x in result.stdout.splitlines() if x.startswith('{')]
    assert not any(x.get('type') in ('error', 'turn.failed') for x in events), events
    assert not any(x.get('item', {}).get('type') == 'error' for x in events), events
    assert any(x.get('type') == 'item.completed' and x.get('item', {}).get('text') == 'MAC_FCC_OK' for x in events)
    print(f'PASS {name}', flush=True)
    return next((x['thread_id'] for x in events if x.get('type') == 'thread.started'), None)


tid = cli('cli-new', ['exec', '--skip-git-repo-check', '--json', 'Remember FIRST_ORIGINAL_MAC_MARKER.'])
assert tid
cli('cli-resume', ['exec', 'resume', tid, '--skip-git-repo-check', '--json', 'Return SECOND_ORIGINAL_MAC_MARKER.'])
assert 'FIRST_ORIGINAL_MAC_MARKER' in json.dumps(requests[-1])
assert 'SECOND_ORIGINAL_MAC_MARKER' in json.dumps(requests[-1])
print('PASS resumed request contains both original user messages', flush=True)

stderr = (root / 'app-server.stderr').open('w')
app = subprocess.Popen([str(binary), '-c', 'features.code_mode_host=true', 'app-server',
                        '--analytics-default-enabled'], cwd=work, env=env, text=True,
                       stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=stderr, bufsize=1)
events = queue.Queue()
transcript = []


def reader():
    for line in app.stdout:
        event = json.loads(line)
        transcript.append(event)
        events.put(event)


threading.Thread(target=reader, daemon=True).start()
rid = 0


def rpc(method, params):
    global rid
    rid += 1
    app.stdin.write(json.dumps({'id': rid, 'method': method, 'params': params}) + '\n')
    app.stdin.flush()
    end = time.monotonic() + 60
    while time.monotonic() < end:
        e = events.get(timeout=end-time.monotonic())
        if e.get('id') == rid:
            assert 'error' not in e, e
            return e['result']
    raise TimeoutError(method)


def turn(thread, text):
    rpc('turn/start', {'threadId': thread, 'input': [{'type': 'text', 'text': text}]})
    end = time.monotonic() + 60
    while time.monotonic() < end:
        event = events.get(timeout=end-time.monotonic())
        if event.get('method') == 'turn/completed' and event['params']['threadId'] == thread:
            assert event['params']['turn']['status'] == 'completed', event
            return
    raise TimeoutError('turn/completed')


try:
    init = rpc('initialize', {'clientInfo': {'name': 'fcc_macos_smoke', 'version': '1.0'},
                              'capabilities': {'experimentalApi': True}})
    app.stdin.write(json.dumps({'method': 'initialized', 'params': {}}) + '\n'); app.stdin.flush()
    print('PASS app-server initialize with desktop launch flags', flush=True)
    started = rpc('thread/start', {'cwd': str(work), 'model': model, 'approvalPolicy': 'never',
                                    'sandbox': 'read-only'})
    app_tid = started['thread']['id']
    turn(app_tid, '[Original link](https://example.invalid) APP_SERVER_ORIGINAL_MARKER')
    assert not any(e.get('method') == 'warning' and 'Code Mode is unavailable' in e.get('params', {}).get('message', '') for e in transcript), transcript
    assert 'APP_SERVER_ORIGINAL_MARKER' in json.dumps(requests[-1])
    print('PASS app-server thread/start and turn/start complete through VRS', flush=True)
    forked = rpc('thread/fork', {'threadId': app_tid, 'ephemeral': True,
                                'experimentalPredictionMode': True, 'excludeTurns': True})
    fork_tid = forked['thread']['id']
    assert fork_tid != app_tid
    turn(fork_tid, 'PREDICTION_FORK_ORIGINAL_MARKER')
    fork_input = json.dumps(requests[-1]['input'])
    assert 'APP_SERVER_ORIGINAL_MARKER' in fork_input
    assert 'PREDICTION_FORK_ORIGINAL_MARKER' in fork_input
    print('PASS ephemeral prediction fork assembles parent and new user input', flush=True)
    rpc('thread/unsubscribe', {'threadId': fork_tid})
    turn(app_tid, 'PARENT_AFTER_FORK_MARKER')
    parent_input = json.dumps(requests[-1]['input'])
    assert 'APP_SERVER_ORIGINAL_MARKER' in parent_input
    assert 'PARENT_AFTER_FORK_MARKER' in parent_input
    assert 'PREDICTION_FORK_ORIGINAL_MARKER' not in parent_input
    print('PASS fork unload and parent continuation without child contamination', flush=True)
finally:
    app.terminate()
    try:
        app.wait(timeout=10)
    except subprocess.TimeoutExpired:
        app.kill(); app.wait()
    stderr.close()
    (root / 'app-server.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in transcript))
    server.shutdown()

receipts = [json.loads(x) for x in (root/'vrs-receipts.jsonl').read_text().splitlines()]
assert len(receipts) >= 3 and all(x['outcome'] == 'assembled' for x in receipts), receipts
compactions = []
for rollout in home.joinpath('sessions').rglob('*.jsonl'):
    for line in rollout.read_text().splitlines():
        e = json.loads(line)
        if e.get('type') == 'compacted' or e.get('payload', {}).get('type') == 'context_compacted':
            compactions.append(e)
assert not compactions
summary = {'requests': len(requests), 'vrs_receipts': len(receipts), 'compactions': 0,
           'cli_thread': tid, 'app_server_thread': app_tid, 'prediction_thread': fork_tid,
           'status': 'PASS'}
(root/'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
print(json.dumps(summary), flush=True)
