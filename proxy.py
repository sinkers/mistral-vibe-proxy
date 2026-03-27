#!/usr/bin/env python3
"""
Mistral Vibe proxy — Flask with hot reload.
Run: python3 proxy.py

Forwards to a vLLM/RunPod endpoint, cleaning only known-bad fields.
Edit ALLOWED_FIELDS to gradually expand what gets passed through.
"""

import json
import logging
import requests
from flask import Flask, request, Response, stream_with_context

app = Flask(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
TARGET  = "https://tp48q97wk9296q-8000.proxy.runpod.net/v1/chat/completions"
MODEL   = "cyankiwi/Devstral-Small-2-24B-Instruct-2512-AWQ-4bit"
API_KEY = "andrew678"
PORT    = 8080

# Fields to forward from the incoming request.
# Add more here as you test them.
ALLOWED_FIELDS = {
    "messages",
    "tools",
    "tool_choice",
    "stream",
    "stream_options",
    "temperature",
    "max_tokens",
}

# Message-level fields that cause upstream validation errors
STRIP_MESSAGE_FIELDS = {"injected"}

# Set to True to drop the system message (helps when a long system prompt
# causes the model to write text instead of making tool calls)
DROP_SYSTEM_MESSAGE = True
# ──────────────────────────────────────────────────────────────────────────────

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s  %(message)s")
log = logging.getLogger()
log.addHandler(logging.FileHandler("proxy.log"))


def clean_message(m):
    return {k: v for k, v in m.items() if k not in STRIP_MESSAGE_FIELDS}


@app.route("/v1/chat/completions", methods=["POST"])
def chat_completions():
    body = request.get_json(force=True)

    payload = {"model": MODEL}
    for field in ALLOWED_FIELDS:
        if field in body:
            payload[field] = body[field]

    if "messages" in payload:
        msgs = payload["messages"]
        if DROP_SYSTEM_MESSAGE:
            msgs = [m for m in msgs if m.get("role") != "system"]
        payload["messages"] = [clean_message(m) for m in msgs]

    if payload.get("stream"):
        payload.setdefault("stream_options", {})
        payload["stream_options"]["include_usage"] = True

    log.info("── OUTGOING REQUEST (stream=%s) ───────────────────", payload.get("stream"))
    log.info(json.dumps(payload, indent=2))

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}",
        "User-Agent": "curl/7.88.1",
    }

    if payload.get("stream"):
        def generate():
            with requests.post(TARGET, json=payload, headers=headers,
                               stream=True, timeout=120) as r:
                log.info("── STREAMING  HTTP %d ─────────────────────────────", r.status_code)
                r.raw.decode_content = True
                while True:
                    line = r.raw.readline()
                    if not line:
                        break
                    if line.startswith(b"data: ") and line.strip() != b"data: [DONE]":
                        try:
                            chunk = json.loads(line[6:])
                            if "model" in chunk:
                                chunk["model"] = "devstral"
                            line = b"data: " + json.dumps(chunk).encode() + b"\n"
                        except json.JSONDecodeError:
                            pass
                    log.info(line.decode(errors="replace").rstrip())
                    yield line

        return Response(stream_with_context(generate()),
                        content_type="text/event-stream")

    r = requests.post(TARGET, json=payload, headers=headers, timeout=120)
    try:
        resp_json = r.json()
        if "model" in resp_json:
            resp_json["model"] = "devstral"
        log.info("── RESPONSE  HTTP %d ──────────────────────────────", r.status_code)
        log.info(json.dumps(resp_json, indent=2))
        return Response(json.dumps(resp_json), status=r.status_code,
                        content_type="application/json")
    except Exception:
        return Response(r.content, status=r.status_code,
                        content_type=r.headers.get("Content-Type", "application/json"))


@app.route("/v1/models", methods=["GET"])
def models():
    return {"object": "list", "data": [
        {"id": "devstral", "object": "model", "created": 0, "owned_by": "local"},
    ]}


if __name__ == "__main__":
    log.info("Devstral proxy → http://127.0.0.1:%d", PORT)
    log.info("Target : %s", TARGET)
    log.info("Model  : %s", MODEL)
    app.run(host="127.0.0.1", port=PORT, debug=True, use_reloader=True)
