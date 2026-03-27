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

## Setting up the pod at RunPod

1. **Signup**: Create an account on RunPod if you don't have one already.
2. **Go to pod templates**: Navigate to the pod templates section and select the `vLLM Latest` template.
3. **Configure pod**: Set up the pod configuration as needed.
4. **Pick the biggest instance you can afford**: Choose the largest instance you can afford, ensuring it has at least 40GB of VRAM to run the Devstral 2 Small model with a 128 context.
5. **Use this as the pod start command**: Use the following command to start the pod, replacing `<your-api-key>` with your actual API key:
   ```
   --model cyankiwi/Devstral-Small-2-24B-Instruct-2512-AWQ-4bit --enable-auto-tool-choice --tool-call-parser mistral --max-model-len 131072 --gpu-memory-utilization 0.90 --api-key <your-api-key>
   ```
6. **Start the pod and check logs**: Start the pod and monitor the System and Container logs for any errors. If everything looks good, proceed to testing.

## Testing

After setting up the pod, ensure that everything is working as expected by running a few test queries. Verify that the model responds correctly and that all tools are functioning properly.

## Setting up the local config and running the proxy

### Local Configuration

To use the proxy with Mistral Vibe, you need to configure the local Vibe settings. Here's how you can set it up:

1. **Edit the Vibe config file**: Open the `~/.vibe/config.toml` file in a text editor.
2. **Add the proxy provider**: Ensure that the `llamacpp` provider is configured to point to the proxy:
   ```toml
   [[providers]]
   name = "llamacpp"
   api_base = "http://127.0.0.1:8080/v1"
   api_key_env_var = ""
   api_style = "openai"
   backend = "generic"
   ```
3. **Add the model**: Add the model configuration to use the proxy:
   ```toml
   [[models]]
   name = "devstral"
   provider = "llamacpp"
   alias = "local"
   temperature = 0.2
   ```
4. **Save the file**: Save the changes to the config file.

### Running the Proxy

1. **Start the proxy**: Run the proxy using the following command:
   ```bash
   python3 proxy.py
   ```
2. **Check the logs**: To monitor the proxy's activity, you can tail the logs using the following command:
   ```bash
   tail -f proxy.log
   ```
3. **Test the setup**: Once the proxy is running, test the setup by sending a request to the proxy endpoint. Ensure that the model responds correctly and that all tools are functioning as expected.

### Tips for Tailing Logs

- Use `tail -f proxy.log` to continuously monitor the log file for real-time updates.
- Use `grep` to filter specific log entries. For example, to filter error logs:
  ```bash
  grep -i "error" proxy.log
  ```
- Use `less` to view the log file in a paginated manner:
  ```bash
  less proxy.log
  ```
- Use `journalctl` if the proxy is running as a systemd service:
  ```bash
  journalctl -u proxy.service -f
  ```

By following these steps, you can ensure that the proxy is correctly set up and running smoothly with Mistral Vibe.

## Running the Proxy as a Systemd Service

To run the proxy as a background service using systemd, follow these steps:

1. **Create a systemd service file**: Create a new file named `proxy.service` in the `/etc/systemd/system/` directory:
   ```bash
   sudo nano /etc/systemd/system/proxy.service
   ```

2. **Add the following content to the file**:
   ```ini
   [Unit]
   Description=Mistral Vibe Proxy Service
   After=network.target
   
   [Service]
   User=your_username
   WorkingDirectory=/path/to/proxy/directory
   ExecStart=/usr/bin/python3 /path/to/proxy/directory/proxy.py
   Restart=always
   RestartSec=10
   
   [Install]
   WantedBy=multi-user.target
   ```
   Replace `your_username` with your actual username and `/path/to/proxy/directory` with the path to the directory where the proxy is located.

3. **Reload systemd**: After saving the file, reload systemd to recognize the new service:
   ```bash
   sudo systemctl daemon-reload
   ```

4. **Start the service**: Start the proxy service:
   ```bash
   sudo systemctl start proxy.service
   ```

5. **Enable the service**: Enable the service to start automatically on boot:
   ```bash
   sudo systemctl enable proxy.service
   ```

6. **Check the service status**: Verify that the service is running correctly:
   ```bash
   sudo systemctl status proxy.service
   ```

7. **View logs**: To view the logs for the proxy service, use:
   ```bash
   journalctl -u proxy.service -f
   ```

By following these steps, you can ensure that the proxy runs in the background as a systemd service and automatically restarts if it crashes.

## Dependencies

The proxy requires the following dependencies:

- Flask
- requests

You can install them using pip:

```bash
pip install -r requirements.txt
```

Or manually:

```bash
pip install Flask==3.0.0 requests==2.31.0
```
