# Configuration reference

All configuration is via environment variables, set before running
`run_cloud.bat` (or `python -m uvicorn main:app ...`). Nothing requires a
config file or restart beyond starting the cloud service.

| Variable | Default | Meaning |
|---|---|---|
| `YANTRA_LLM` | `off` | `on` to try the local Ollama LLM for fault advisories, `off` to always use the deterministic rule-based engine. Off by default because a CPU-only `phi3:mini` can pin 100% CPU for 30-60s+ per reply on a typical laptop, visibly stuttering the live dashboard. |
| `YANTRA_LLM_MODEL` | `phi3:mini` | Ollama model name to use when `YANTRA_LLM=on`. |
| `YANTRA_OLLAMA_URL` | `http://127.0.0.1:11434` | Base URL of the local Ollama server. Use `127.0.0.1`, not `localhost` - see the networking note in the README. |
| `YANTRA_LLM_TIMEOUT` | `6.0` | Seconds to wait for an Ollama reply before falling back to the rule-based advisory. Raise this on NPU-accelerated (QNN) hardware where the model is genuinely fast. |
| `YANTRA_OFFLINE_AFTER_S` | `15` | Seconds without an event before a node is marked offline on the dashboard. Default assumes the ~2s publish interval used by the simulator and firmware. |

## Node / simulator flags

Set via CLI arguments rather than environment variables - see
`python simulator.py --help` and `python arduino_bridge.py --help`.

| Flag | Default | Meaning |
|---|---|---|
| `--url` | `http://127.0.0.1:8000` | Cloud service base URL to publish events to. |
| `--interval` (simulator only) | `2.0` | Seconds between publish ticks per machine. |
| `--port` (bridge only) | auto-detected | Serial port the Arduino UNO Q is on. |
| `--no-sim` (bridge only) | off | Don't also run the Python simulator for machines the real board isn't covering. |
