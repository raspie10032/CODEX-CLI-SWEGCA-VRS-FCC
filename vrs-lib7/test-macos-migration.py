"""FCC 1.1.2 regression and VX06 -> VX07 migration using synthetic rollouts.

Usage: python3 test-macos-migration.py <old dylib> <new dylib> <new output dir>
Both libraries are loaded locally; no real user sessions are read or changed.
"""
import ctypes as c
import hashlib
import json
from pathlib import Path
import sys


class Options(c.Structure):
    _fields_ = [("sessions", c.c_char_p), ("index", c.c_char_p),
                ("workers", c.c_uint), ("cpus", c.POINTER(c.c_uint)),
                ("ncpus", c.c_uint), ("segwin", c.c_int), ("budget", c.c_uint64)]


class Store:
    def __init__(self, library, sessions, index):
        self.lib = c.CDLL(str(library))
        self.lib.vrs_open.argtypes = [c.POINTER(Options), c.POINTER(c.c_void_p)]
        self.lib.vrs_wait.argtypes = [c.c_void_p, c.c_char_p, c.c_uint64]
        self.lib.vrs_assemble_b.argtypes = [
            c.c_void_p, c.c_char_p, c.c_uint64,
            c.POINTER(c.c_void_p), c.POINTER(c.c_size_t)]
        self.lib.vrs_free.argtypes = [c.c_void_p]
        self.lib.vrs_close.argtypes = [c.c_void_p]
        self.handle = c.c_void_p()
        opts = Options(str(sessions).encode(), str(index).encode(),
                       2, None, 0, 1, 258400)
        assert self.lib.vrs_open(c.byref(opts), c.byref(self.handle)) == 0
        assert self.lib.vrs_wait(self.handle, None, 5000) == 0

    def assemble(self, path, budget):
        out, length = c.c_void_p(), c.c_size_t()
        assert self.lib.vrs_wait(self.handle, str(path).encode(), 5000) == 0
        rc = self.lib.vrs_assemble_b(self.handle, str(path).encode(), budget,
                                   c.byref(out), c.byref(length))
        value = json.loads(c.string_at(out, length.value)) if out.value else None
        if out.value:
            self.lib.vrs_free(out)
        return rc, value

    def close(self):
        self.lib.vrs_close(self.handle)


old_lib, new_lib, output = map(Path, sys.argv[1:])
output.mkdir(parents=True, exist_ok=False)
sessions, index = output / "sessions", output / "idx"
sessions.mkdir()
identity = "40000000-0000-4000-8000-000000000004"
rollout = sessions / f"rollout-{identity}.jsonl"
records = []


def add(kind, payload):
    ordinal = len(records)
    records.append({"timestamp": f"2026-10-20T00:{ordinal // 60:02d}:{ordinal % 60:02d}.000Z",
                    "ordinal": ordinal, "type": kind, "payload": payload})


first = "[Important original](https://example.invalid) " + "ORIGINAL_USER " * 1500
add("session_meta", {"id": identity})
original_users = [first] + [f"CURRENT_USER_MARKER_{n}" for n in range(23)]
for turn, text in enumerate(original_users):
    add("event_msg", {"type": "task_started", "turn_id": str(turn)})
    add("response_item", {"type": "message", "role": "user",
                         "content": [{"type": "input_text", "text": text}]})
    add("response_item", {"type": "message", "role": "assistant",
                         "content": [{"type": "output_text", "text": "OK"}]})
    add("event_msg", {"type": "task_complete", "turn_id": str(turn),
                     "last_agent_message": "OK"})
rollout.write_text("".join(json.dumps(r, separators=(",", ":")) + "\n"
                          for r in records))
original_hash = hashlib.sha256(rollout.read_bytes()).hexdigest()

old = Store(old_lib, sessions, index)
try:
    rc, _ = old.assemble(rollout, 1024)
    assert rc == 0, "Old build must reproduce the link-message omission"
finally:
    old.close()
shards = list(index.rglob("*.vx"))
assert shards and all(p.read_bytes()[:4] == b"VX06" for p in shards)
print("PASS old build reproduces link omission and creates VX06 index", flush=True)

new = Store(new_lib, sessions, index)
try:
    rc, value = new.assemble(rollout, 1024)
    assert rc == 2 and value["error"] == "required input over budget"
    print("PASS original link message remains required and fails closed", flush=True)
    rc, value = new.assemble(rollout, 258400)
    assert rc == 0
    users = [item for item in value["items"] if item.get("role") == "user"]
    assert [item["content"][0]["text"] for item in users] == original_users
finally:
    new.close()
assert all(p.read_bytes()[:4] == b"VX07" for p in shards)
assert hashlib.sha256(rollout.read_bytes()).hexdigest() == original_hash
print("PASS VX07 migration preserves all 24 original user messages and rollout bytes",
      flush=True)
