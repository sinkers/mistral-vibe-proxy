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

No dependencies — stdlib only.

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
