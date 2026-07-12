# Yantra Rakshak — TinyML Predictive Maintenance for MSME Machines

[![CI](https://github.com/DivyanshSingh8899/Yantra_Rakshak_MSME_/actions/workflows/ci.yml/badge.svg)](https://github.com/DivyanshSingh8899/Yantra_Rakshak_MSME_/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> Sense at the Edge. Understand at the Centre. Act in Time.

A two-tier, **fully offline** predictive-maintenance system for factory machines
(motors, pumps, lathes, compressors). Arduino UNO Q nodes run a TinyML anomaly
detector on live vibration data and publish compact health events to a laptop
("the cloud"), which aggregates the whole fleet, runs a **local LLM** to turn raw
faults into plain-language maintenance guidance, and drives a real-time dashboard.

No internet. No subscriptions. No data leaves the LAN.

---

## What's in this repo

```
Qualcumm_bangalore/
├── backend/            FastAPI cloud service (runs on the laptop)
│   ├── main.py           REST + WebSocket + static UI, event ingestion
│   ├── database.py       SQLite persistence (local, offline)
│   ├── llm.py            LLM advisory (Ollama + rule-based fallback)
│   ├── models.py         Pydantic schemas
│   └── requirements.txt
├── node/               Arduino UNO Q simulator (dummy MPU-6050 + on-device ML)
│   ├── simulator.py      multi-machine fleet, publishes to the cloud
│   ├── anomaly.py        feature extraction + autoencoder-style scoring
│   └── requirements.txt
├── frontend/           Professional dashboard (vanilla JS, zero CDN, offline)
│   ├── index.html
│   ├── css/styles.css
│   └── js/{charts.js, app.js}
├── arduino/            Real UNO Q firmware for when hardware is wired
│   └── yantra_firmware/{yantra_firmware.ino, config.h}
├── run_cloud.bat       start the laptop service
├── run_nodes.bat       start the node simulator
└── README.md
```

---

## Quick start (2 terminals)

You only need **Python 3.10+**. Everything else installs automatically.

**Terminal 1 — start the cloud (laptop):**
```bat
run_cloud.bat
```
Then open **http://localhost:8000** in a browser.

**Terminal 2 — start the simulated node fleet:**
```bat
run_nodes.bat
```

Watch the dashboard: machines start healthy and gradually drift into
bearing wear, imbalance, lubrication and overheating faults. Each fault raises
an alert with an AI-written root cause, recommended action and urgency.

> If port 8000 is busy, run `run_cloud.bat 8010` and
> `run_nodes.bat http://127.0.0.1:8010`.

**Before a live demo**, run the smoke test to confirm everything is actually
up rather than finding out in front of judges:
```bat
python scripts/smoke_test.py
```

### Manual start (no batch files)
```bat
cd backend
pip install -r requirements.txt
python -m uvicorn main:app --host 0.0.0.0 --port 8000

REM in a second terminal
cd node
pip install -r requirements.txt
python simulator.py --url http://127.0.0.1:8000
```

> Use `127.0.0.1`, not `localhost`, for the node → cloud URL. On some Windows
> setups `localhost` resolves to `::1` first and adds a ~2s delay per request
> before falling back to IPv4.

---

## The dashboard

| View | What it shows |
|------|---------------|
| **Overview** | Live card per machine — health gauge, anomaly sparkline, fault, temp |
| **Machines** | Per-machine inspector: anomaly-score history chart + live vibration waveform |
| **Alerts & Advisory** | Stream of faults, each with LLM root cause / action / urgency |
| **Hardware Setup** | Node connection topology, MPU-6050 → UNO Q wiring table + diagram, deploy steps |
| **System & Architecture** | End-to-end data flow, inference engine and cloud specs, LLM status |

Connection status (cloud + LLM) is always visible in the sidebar.

---

## Enabling the real local LLM (optional)

By default the advisory uses a built-in **rule-based expert system** (real
vibration-analysis heuristics), so the demo works with zero setup. To use a true
local language model:

1. Install [Ollama](https://ollama.com) (runs fully offline).
2. Pull a small model: `ollama pull phi3:mini`
3. Restart `run_cloud.bat`. The sidebar will show `LLM: phi3:mini`.

Configure via env vars: `YANTRA_LLM_MODEL`, `YANTRA_OLLAMA_URL`, `YANTRA_LLM=off`.

On a Snapdragon Copilot+ PC this maps to an NPU-accelerated model; the same code
path works on any laptop's CPU/GPU.

---

## How anomaly detection works

Each node processes a 128-sample vibration window and extracts:

- **RMS amplitude** — overall energy
- **Kurtosis** — impulsiveness (spikes → bearing faults)
- **Crest factor** — peak/RMS ratio
- **Dominant frequency** — 1× running speed vs. harmonics
- **Temperature**

On boot, a 30-second **healthy baseline** (mean + std per feature) is captured.
Each new window is scored by its deviation from that baseline (an
autoencoder-style reconstruction error, normalised so 1.0 = healthy):

- `< 1.5` → **OK**
- `1.5 – 2.5` → **WARNING**
- `> 2.5` → **CRITICAL**

The fault is then classified from the feature signature (bearing wear, imbalance,
lubrication, overheat). This mirrors the INT8 TFLite-Micro autoencoder that runs
on the STM32U585 in the real firmware.

---

## Moving to real hardware

The simulator reproduces the firmware logic exactly, so the transition is direct:

1. Wire an **MPU-6050** to the **Arduino UNO Q** (see the Hardware Setup view for pinout).
2. Edit `arduino/yantra_firmware/config.h` — set `MACHINE_ID`, Wi-Fi, and the
   laptop's LAN IP in `CLOUD_HOST`.
3. Flash `yantra_firmware.ino`.
4. Power on. The node calibrates, then publishes to the same `/api/ingest`
   endpoint the simulator uses — the dashboard treats real and simulated nodes
   identically.

You can run **real nodes and simulated nodes at the same time**.

---

## Tech stack

- **Edge:** Arduino UNO Q (STM32U585 Cortex-M33), TFLite-Micro + CMSIS-NN, MPU-6050
- **Cloud (laptop):** Python, FastAPI, WebSocket, SQLite — all local
- **LLM:** Ollama (phi3:mini) with a deterministic rule-based fallback
- **Frontend:** vanilla HTML/CSS/JS with custom canvas charts — no CDN, fully offline

---

## Testing

```bat
cd node
pip install pytest
pytest tests/ -v
```

CI (`.github/workflows/ci.yml`) runs this plus a byte-compile check on every
push to `main`.

## More docs

- [ARCHITECTURE.md](ARCHITECTURE.md) — module boundaries and design decisions
- [CONFIGURATION.md](CONFIGURATION.md) — every environment variable and CLI flag
- [CHANGELOG.md](CHANGELOG.md) — notable fixes and why they were needed
- [TEST_CASES.md](TEST_CASES.md) — functional and non-functional test matrix
- [SECURITY.md](SECURITY.md) — offline-by-design posture and known gaps
- [LICENSE](LICENSE) — MIT

---

MIT licensed. Built for the Snapdragon Multiverse Hackathon, Bangalore.
