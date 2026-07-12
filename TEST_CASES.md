# Test cases

Manual + automated test matrix for Yantra Rakshak. "Verified" means this was
actually executed against a running instance during development, not just
read from the code. "Not verified" is called out explicitly rather than
assumed - see notes per case.

Automated coverage for the parts that are safe to run in isolation lives in
[`node/tests/test_anomaly.py`](node/tests/test_anomaly.py) (run via
`pytest`, also wired into CI). Everything below that touches the live
`backend/yantra.db` is documented as a manual procedure instead, since
running it as an automated suite would insert fake rows into whatever
database is currently backing a real demo.

---

## Functional test cases

| ID | Description | Steps | Expected result | Status |
|----|---|---|---|---|
| FT-01 | Node event ingestion | POST a valid `HealthEvent` JSON body to `/api/ingest` | `200 OK`, response includes `id` and `advisory` | ✅ Verified — exercised continuously via the simulator and the Arduino bridge |
| FT-02 | Event persistence | Ingest an event, then `GET /api/machine/{id}/history` | The event appears in history, fields match what was posted | ✅ Verified — confirmed via direct SQLite read during this session |
| FT-03 | Severity classification | Feed windows with increasing deviation from baseline | `mse_score < 1.5` → `OK`, `1.5–2.5` → `WARNING`, `≥ 2.5` → `CRITICAL` | ✅ Verified — unit tested in `test_anomaly.py`; also observed live across thousands of simulated events |
| FT-04 | Fault classification | Force each `fault_mode` (bearing wear, imbalance, lubrication, overheat) via the simulator/firmware | `fault_type` in alerts matches the injected fault | ✅ Verified — observed all 4 fault types live on the dashboard |
| FT-05 | Rule-based advisory generation | Trigger a WARNING/CRITICAL event with `YANTRA_LLM=off` | Response `advisory.source == "rules"`, with non-empty root cause/action/urgency | ✅ Verified |
| FT-06 | LLM advisory upgrade | Trigger a fault with `YANTRA_LLM=on` and Ollama reachable | Advisory is later upgraded via WebSocket `{"type":"advisory", ...}`, `source` becomes `llm:<model>` | ✅ Verified the upgrade path fires; on this CPU-only laptop the reply itself is genuinely slow (~30-60s), so it's off by default — see `CHANGELOG.md` |
| FT-07 | WebSocket live push | Open `/ws`, ingest an event | Client receives `{"type":"event", ...}` and a following `{"type":"nodes", ...}` without polling | ✅ Verified via the dashboard's live updates |
| FT-08 | Alerts feed excludes healthy events | Ingest a mix of OK and WARNING/CRITICAL events, `GET /api/alerts` | Only non-OK events are returned | ✅ Verified |
| FT-09 | Node offline detection | Stop publishing for a machine, wait past `YANTRA_OFFLINE_AFTER_S` (15s default) | `GET /api/nodes` reports `online: false` for that machine | ✅ Verified — reproduced live during this session (nodes flipped to offline after the simulator was stopped) |
| FT-10 | Dashboard - Overview tab | Load `/`, default view | KPI strip and a card per known machine render with live severity/gauge | ✅ Verified |
| FT-11 | Dashboard - Machines tab | Click a machine in the Machines tab | Anomaly-history chart and vibration waveform render on `<canvas>` | ✅ Verified — confirmed via pixel inspection (>75% non-transparent pixels on the history chart), not just "canvas exists" |
| FT-12 | Dashboard - Alerts tab | Open Alerts & Advisory | Feed shows fault cards with root cause / action / urgency / advisory source | ✅ Verified |
| FT-13 | Dashboard - Hardware Setup tab | Open Hardware Setup | Node topology list, wiring table, and board diagram render | ✅ Verified |
| FT-14 | Dashboard - System tab | Open System & Architecture | Data-flow diagram and live LLM status render | ✅ Verified |
| FT-15 | Arduino bridge forwarding | Run `arduino_bridge.py` against a flashed UNO Q | JSON lines from serial are parsed and POSTed to `/api/ingest` | ✅ Verified — real hardware event observed in `yantra.db` after simulator was stopped to isolate it |
| FT-16 | Arduino bridge auto-reconnect | Kill the serial connection mid-stream (unplug/replug) | Bridge logs `serial connection lost`, then `reconnecting...`, then resumes without a manual restart | ✅ Verified — reproduced live; this was a real bug fixed during this session (see `CHANGELOG.md`) |
| FT-17 | Real + simulated nodes coexist | Run the bridge (`--no-sim`) alongside the standalone simulator with distinct `MACHINE_ID`s | Both appear as separate, correctly-attributed cards | ⚠️ Partially verified — confirmed the two *can* collide if `MACHINE_ID` isn't changed from the firmware default (documented as a setup step); not yet verified with a deliberately distinct ID |
| FT-18 | Batch launchers | Run `run_cloud.bat`, `run_nodes.bat`, `run_arduino.bat` | Each starts its process and connects to the expected port with no manual edits | ✅ Verified — including catching and fixing a real port-default mismatch between the two scripts |
| FT-19 | Firmware compiles/flashes on real UNO Q hardware | Flash `yantra_firmware.ino` via Arduino IDE | Board boots, calibrates, streams JSON over serial | ❌ **Not verified by Claude** — no Arduino UNO Q was available in the environment used for this session; verified only by the user's own hardware run (FT-15 confirms the *result* worked once flashed) |

---

## Non-functional test cases

| ID | Category | Description | Steps | Expected result | Status |
|----|---|---|---|---|---|
| NFT-01 | Performance - ingestion latency | Time `/api/ingest` round-trip with `YANTRA_LLM=off` | Response in low tens of ms, not seconds | ✅ Verified — measured directly (~30ms once the `localhost`→`127.0.0.1` fix was applied; was ~2s per call before) |
| NFT-02 | Performance - publish cadence | Run the simulator at `--interval 1.5`, check event timestamps | Events land ~1.5-2s apart, not with growing drift | ✅ Verified — root-caused and fixed a Windows IPv6 resolution delay that was inflating this to 15-60s+ |
| NFT-03 | Reliability - LLM never blocks ingestion | Trigger faults with `YANTRA_LLM=on` under load | `/api/ingest` still responds immediately; LLM upgrade happens async, capped to one in-flight call | ✅ Verified — this was a real bug (ingestion blocked on the LLM call) fixed during this session |
| NFT-04 | Reliability - graceful degradation without LLM | Run with Ollama not installed/unreachable | System falls back to rule-based advisories with no errors surfaced to the user | ✅ Verified |
| NFT-05 | Reliability - serial disconnect recovery | See FT-16 | Bridge recovers without a process restart | ✅ Verified |
| NFT-06 | Offline / no external dependency | Monitor network calls during normal operation with `YANTRA_LLM=off` | No calls leave the LAN; only `127.0.0.1` traffic | ✅ Verified by design/code review — `main.py`/`llm.py` only ever call `127.0.0.1` endpoints (cloud, Ollama); no third-party hosts are contacted |
| NFT-07 | Usability - no console errors | Load every dashboard tab, open dev tools | Zero JS console errors across Overview/Machines/Alerts/Hardware/System | ✅ Verified |
| NFT-08 | Data integrity - persistence across restarts | Restart the backend process, re-query history | Prior events are still present (SQLite file survives process restart) | ✅ Verified |
| NFT-09 | Scalability - concurrent machines | Run the default 5-machine simulated fleet simultaneously | All 5 publish independently without id collisions or dropped events | ✅ Verified |
| NFT-10 | Resource usage - CPU-bound LLM doesn't crash the app | Run `ollama ps` while `YANTRA_LLM=on` under load | Ollama pins CPU but the FastAPI process keeps serving other requests | ✅ Verified — also is *why* `YANTRA_LLM` now defaults to `off`, documented in `CHANGELOG.md` |
| NFT-11 | Portability - Windows batch setup | Fresh `pip install -r requirements.txt` + `run_cloud.bat` | No manual dependency wrangling beyond what the script does | ✅ Verified on this machine; not tested on macOS/Linux (the `.bat` launchers are Windows-only by design - README's manual-start commands are the cross-platform path) |
| NFT-12 | Security - no secrets in the repo | Review tracked files before pushing | No real credentials; `config.h`'s `WIFI_SSID`/`WIFI_PASS` are placeholder values | ✅ Verified before the initial push |
