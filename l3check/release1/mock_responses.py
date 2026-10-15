"""Local Responses API stand-in: saves each POST body and answers with a one-message stream."""
import http.server
import itertools
import json
import os
import sys

OUT = sys.argv[1]
PORT = int(sys.argv[2])
counter = itertools.count(1)

EVENTS = [
    {"type": "response.created", "response": {"id": "resp_1"}},
    {
        "type": "response.output_item.done",
        "item": {
            "type": "message",
            "role": "assistant",
            "id": "msg_1",
            "content": [{"type": "output_text", "text": "ok"}],
        },
    },
    {
        "type": "response.completed",
        "response": {
            "id": "resp_1",
            "usage": {
                "input_tokens": 1,
                "input_tokens_details": None,
                "output_tokens": 1,
                "output_tokens_details": None,
                "total_tokens": 2,
            },
        },
    },
]


class Handler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("content-length", "0")))
        n = next(counter)
        with open(os.path.join(OUT, f"req-{n:03d}.json"), "wb") as fh:
            fh.write(body)
        with open(os.path.join(OUT, f"req-{n:03d}.path"), "w", encoding="utf-8") as fh:
            fh.write(self.path)
        stream = "".join(
            f"event: {e['type']}\ndata: {json.dumps(e)}\n\n" for e in EVENTS
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("content-type", "text/event-stream")
        self.send_header("content-length", str(len(stream)))
        self.end_headers()
        self.wfile.write(stream)

    def do_GET(self):
        self.send_response(404)
        self.end_headers()

    def log_message(self, *args):
        pass


http.server.ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
