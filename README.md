# mistral-vibe-proxy

A minimal proxy that lets [Mistral Vibe](https://github.com/mistralai/mistral-vibe) use a self-hosted vLLM endpoint (e.g. RunPod) as a local `llamacpp`-style provider.

## What it does

- Listens on `localhost:8080`
- Accepts OpenAI-compatible `POST /v1/chat/completions` requests
- Strips the payload to just `messages`, forces the configured model name
- Forwards to a remote vLLM endpoint with the real model name and API key
- Rewrites `model` in the response back to `devstral` so Vibe is happy
- Handles both streaming (SSE) and non-streaming responses
- Logs all requests and responses to `proxy.log`

## Configuration

Edit the constants at the top of `proxy.py`:

```python
TARGET  = "https://<your-runpod-endpoint>/v1/chat/completions"
MODEL   = "<your-model-name>"
API_KEY = "<your-api-key>"
PORT    = 8080
```

## Usage

```bash
python3 proxy.py
```

Requires Flask and requests (`pip install flask requests`). Hot reloads on file changes.

## Tool calling

Vibe sends tool definitions (file read, bash, etc.) so the model can act as a coding agent. Getting this working required several fixes:

**vLLM must be started with Mistral's tool call parser:**
```
--enable-auto-tool-choice --tool-call-parser mistral
```
Without these flags the model never emits structured tool calls regardless of what the proxy sends.

**The `injected` field must be stripped from messages.** Vibe adds `"injected": false` to system messages, which vLLM's Pydantic validation rejects with a 400 error.

**The Vibe system prompt must be dropped.** Vibe sends a long (~8000 token) system prompt describing its "Orient / Plan / Execute" workflow. With this prompt the model ignores the tool definitions and writes pseudo-code text instead of making structured tool calls. Dropping the system message restores normal tool-calling behaviour.

This is controlled by the `DROP_SYSTEM_MESSAGE` flag in `proxy.py`. Set to `False` if you want to experiment with a custom system prompt — keep it short and avoid instructing the model on how to structure its responses, as this interferes with tool use.

**Python's default User-Agent is blocked by RunPod's reverse proxy.** The proxy spoofs `User-Agent: curl/7.88.1` to avoid 403 errors.

## Vibe config (`~/.vibe/config.toml`)

```toml
[[providers]]
name = "llamacpp"
api_base = "http://127.0.0.1:8080/v1"
api_key_env_var = ""
api_style = "openai"
backend = "generic"

[[models]]
name = "devstral"
provider = "llamacpp"
alias = "local"
temperature = 0.2
```
