#!/usr/bin/env python3
"""
Minimal Devstral proxy.
- Listens on localhost:8080
- Strips incoming payload to only 'messages' + stream flag
- Forces model to MODEL below
- Handles both streaming (SSE) and non-streaming responses
- Logs full outgoing payload and full response
- No third-party dependencies
"""

import json
import logging
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.request import Request, urlopen
from urllib.error import URLError

TARGET   = "https://tp48q97wk9296q-8000.proxy.runpod.net/v1/chat/completions"
MODEL    = "cyankiwi/Devstral-Small-2-24B-Instruct-2512-AWQ-4bit"
API_KEY  = "andrew678"
PORT     = 8080
LOG_FILE = "simple_proxy.log"

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s  %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE),
    ],
)
log = logging.getLogger()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass  # silence default access log

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)

        try:
            body = json.loads(raw)
        except json.JSONDecodeError as e:
            log.error("Bad JSON from client: %s", e)
            self._reply(400, {"error": "invalid json"})
            return

        stream = body.get("stream", False)

        payload = {
            "model": MODEL,
            "messages": [
                {"role": m["role"], "content": m["content"]}
                for m in body.get("messages", [])
            ],
            "stream": stream,
        }
        if stream:
            payload["stream_options"] = {"include_usage": True}

        log.info("── OUTGOING REQUEST (stream=%s) ───────────────────", stream)
        log.info(json.dumps(payload, indent=2))

        req = Request(
            TARGET,
            data=json.dumps(payload).encode(),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {API_KEY}",
                "User-Agent": "curl/7.88.1",
            },
            method="POST",
        )

        try:
            resp = urlopen(req, timeout=120)
        except URLError as e:
            log.error("Upstream error: %s", e)
            self._reply(502, {"error": str(e)})
            return

        status = resp.status
        content_type = resp.headers.get("Content-Type", "application/json")

        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.end_headers()

        if stream:
            self._stream(resp)
        else:
            resp_body = resp.read()
            resp.close()
            try:
                parsed = json.loads(resp_body)
                if "model" in parsed:
                    parsed["model"] = "devstral"
                resp_body = json.dumps(parsed).encode()
                log.info("── RESPONSE  HTTP %d ──────────────────────────────", status)
                log.info(json.dumps(parsed, indent=2))
            except json.JSONDecodeError:
                log.info("── RESPONSE  HTTP %d (non-JSON) ───────────────────", status)
                log.info(resp_body.decode(errors="replace"))
            self.wfile.write(resp_body)

    def _stream(self, resp):
        log.info("── STREAMING RESPONSE ────────────────────────────")
        try:
            while True:
                line = resp.readline()
                if not line:
                    break
                # Rewrite model name in data lines
                if line.startswith(b"data: ") and line.strip() != b"data: [DONE]":
                    try:
                        chunk = json.loads(line[6:])
                        if "model" in chunk:
                            chunk["model"] = "devstral"
                        line = b"data: " + json.dumps(chunk).encode() + b"\n"
                    except json.JSONDecodeError:
                        pass
                log.info(line.decode(errors="replace").rstrip())
                self.wfile.write(line)
            self.wfile.flush()
        except Exception as e:
            log.error("Stream error: %s", e)
        finally:
            resp.close()

    def _reply(self, status, obj):
        body = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    server = HTTPServer(("127.0.0.1", PORT), Handler)
    log.info("Devstral proxy → http://127.0.0.1:%d", PORT)
    log.info("Target : %s", TARGET)
    log.info("Model  : %s", MODEL)
    log.info("Log    : %s", LOG_FILE)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("Stopped.")
