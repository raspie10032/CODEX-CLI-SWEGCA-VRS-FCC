"""Exercise the native macOS port against synthetic, lossless rollout files.

Usage: python3 test-macos.py <libvrs.dylib> <new output directory>
"""
import ctypes as c
import datetime as dt
import json
from pathlib import Path
import sys
import threading
import time

lib = c.CDLL(sys.argv[1])
root = Path(sys.argv[2]).resolve()
root.mkdir(parents=True, exist_ok=False)
sessions = root / "sessions"
sessions.mkdir()
index = root / "idx"


class Options(c.Structure):
    _fields_ = [("sessions", c.c_char_p), ("index", c.c_char_p),
                ("workers", c.c_uint), ("cpus", c.POINTER(c.c_uint)),
                ("ncpus", c.c_uint), ("segwin", c.c_int), ("budget", c.c_uint64)]


lib.vrs_open.argtypes = [c.POINTER(Options), c.POINTER(c.c_void_p)]
lib.vrs_wait.argtypes = [c.c_void_p, c.c_char_p, c.c_uint64]
lib.vrs_insert.argtypes = [c.c_void_p, c.c_char_p, c.c_uint64, c.c_char_p, c.c_size_t]
lib.vrs_written.argtypes = [c.c_void_p, c.c_char_p, c.c_uint64]
lib.vrs_assemble_b.argtypes = [c.c_void_p, c.c_char_p, c.c_uint64,
                             c.POINTER(c.c_void_p), c.POINTER(c.c_size_t)]
lib.vrs_free.argtypes = [c.c_void_p]
lib.vrs_close.argtypes = [c.c_void_p]


def fixture(identity, turns=24, parent=None):
    records = []

    def add(kind, payload):
        ordinal = len(records)
        stamp = dt.datetime(2026, 10, 16, tzinfo=dt.timezone.utc) + dt.timedelta(milliseconds=ordinal)
        records.append({"timestamp": stamp.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
                        "ordinal": ordinal, "type": kind, "payload": payload})

    meta = {"id": identity}
    if parent:
        meta.update(forked_from_id=parent, forked_from_ordinal_exclusive=97)
    add("session_meta", meta)
    for turn in range(turns):
        add("event_msg", {"type": "task_started", "turn_id": str(turn)})
        add("response_item", {"type": "message", "role": "user", "content": [
            {"type": "input_text", "text": f"USER_{identity}_{turn}: preserve this original statement."}]})
        add("response_item", {"type": "message", "role": "assistant", "content": [
            {"type": "output_text", "text": f"ANSWER_{identity}_{turn}"}]})
        add("event_msg", {"type": "task_complete", "turn_id": str(turn),
                          "last_agent_message": f"ANSWER_{identity}_{turn}"})
    return [(json.dumps(r, separators=(",", ":")) + "\n").encode() for r in records]


def open_store():
    handle = c.c_void_p()
    opts = Options(str(sessions).encode(), str(index).encode(), 2, None, 0, 1, 258400)
    assert lib.vrs_open(c.byref(opts), c.byref(handle)) == 0
    assert lib.vrs_wait(handle, None, 5000) == 0
    return handle


def assemble(handle, path, budget=258400):
    out, size = c.c_void_p(), c.c_size_t()
    rc = lib.vrs_assemble_b(handle, str(path).encode(), budget, c.byref(out), c.byref(size))
    value = json.loads(c.string_at(out, size.value)) if out.value else None
    if out.value:
        lib.vrs_free(out)
    return rc, value


def wait_for(handle, path, text):
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        rc, value = assemble(handle, path)
        if rc == 0 and text in json.dumps(value):
            return value
        time.sleep(0.02)
    raise AssertionError(f"watcher did not deliver {text}: {rc} {value}")


identity = "10000000-0000-4000-8000-000000000001"
lines = fixture(identity)
(root / "fixture.jsonl").write_bytes(b"".join(lines))
h = open_store()
path = sessions / "new/nested" / f"rollout-{identity}.jsonl"
path.parent.mkdir(parents=True)
try:
    path.write_bytes(b"".join(lines[:41]))
    wait_for(h, path, f"USER_{identity}_9")
    print("PASS recursive creation through file watcher", flush=True)
    with path.open("ab") as out:
        out.write(b"".join(lines[41:65]))
    wait_for(h, path, f"USER_{identity}_15")
    print("PASS external append through file watcher", flush=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_bytes(b"".join(lines[:81]))
    temporary.replace(path)
    wait_for(h, path, f"USER_{identity}_19")
    print("PASS atomic file replacement through file watcher", flush=True)
    offset = path.stat().st_size
    with path.open("ab") as out:
        for line in lines[81:]:
            assert lib.vrs_insert(h, str(path).encode(), offset, line, len(line)) == 0
            out.write(line)
            out.flush()
            assert lib.vrs_written(h, str(path).encode(), offset) in (0, -3)
            offset += len(line)
    value = wait_for(h, path, f"USER_{identity}_23")
    users = [x for x in value["items"] if x.get("role") == "user"]
    assert len(users) == 24
    print("PASS direct insert and all 24 original user messages", flush=True)
    rc, error = assemble(h, path, 1)
    assert rc == 2 and error["error"] == "required input over budget"
    print("PASS over-budget fails closed", flush=True)

    parent = "20000000-0000-4000-8000-000000000002"
    child = "30000000-0000-4000-8000-000000000003"
    parent_path = sessions / f"rollout-{parent}.jsonl"
    parent_lines = fixture(parent)
    parent_path.write_bytes(b"".join(parent_lines[:41]))
    wait_for(h, parent_path, f"USER_{parent}_9")
    child_path = sessions / f"rollout-{child}.jsonl"
    child_path.write_bytes(b"".join(fixture(child, 1, parent)))
    # Assembly first discovers the unresolved parent even before FSEvents fires.
    assert assemble(h, child_path)[0] == 1
    start = time.monotonic()
    assert lib.vrs_wait(h, str(child_path).encode(), 80) == 1
    assert time.monotonic() - start >= 0.06
    print("PASS timed wait on unresolved fork", flush=True)
    def append_parent():
        time.sleep(0.1)
        with parent_path.open("ab") as out:
            out.write(b"".join(parent_lines[41:]))

    writer = threading.Thread(target=append_parent)
    writer.start()
    assert lib.vrs_wait(h, str(child_path).encode(), 5000) == 0
    writer.join()
    wait_for(h, child_path, f"USER_{parent}_0")
    print("PASS parent arrival wakes waiting fork", flush=True)
finally:
    lib.vrs_close(h)

h = open_store()
try:
    restored = wait_for(h, path, f"USER_{identity}_23")
    assert [x for x in restored["items"] if x.get("role") == "user"] == users
    print("PASS restart preserves all original user messages", flush=True)
finally:
    lib.vrs_close(h)
print("PASS clean shutdown", flush=True)
