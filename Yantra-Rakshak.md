# YANTRA RAKSHAK
### TinyML Predictive Maintenance for MSME Machines
**Snapdragon® Multiverse Hackathon — Bangalore · July 11–12, 2026**

> *Sense at the Edge. Understand at the Centre. Act in Time.*

| Category | Devices | Prize Target |
|----------|---------|--------------|
| TinyML / Edge AI | AI PC + Arduino UNO Q | Top Award + Multi-Device Award |

---

## Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Problem Statement](#2-problem-statement)
3. [Proposed Solution](#3-proposed-solution)
4. [System Architecture Overview](#4-system-architecture-overview)
5. [End-to-End Data Flow](#5-end-to-end-data-flow)
6. [TinyML Inference Pipeline (Arduino UNO Q)](#6-tinyml-inference-pipeline-arduino-uno-q)
7. [Communication Layer](#7-communication-layer)
8. [AI PC Intelligence Layer (Snapdragon X Series)](#8-ai-pc-intelligence-layer-snapdragon-x-series)
9. [Data Models & State Machine](#9-data-models--state-machine)
10. [Deployment & Setup Workflow](#10-deployment--setup-workflow)
11. [Alignment with Judging Criteria](#11-alignment-with-judging-criteria)
12. [Technology Stack](#12-technology-stack)
13. [24-Hour Build Plan](#13-24-hour-build-plan)
14. [Real-World Impact](#14-real-world-impact)
15. [Risk Register & Mitigations](#15-risk-register--mitigations)
16. [Open-Source & Compliance](#16-open-source--compliance)
17. [Submission Compliance Checklist](#17-submission-compliance-checklist)

---

## 1. Executive Summary

Yantra Rakshak is a **two-device, always-offline predictive maintenance system** designed for India's 63 million Micro, Small & Medium Enterprises (MSMEs). It embeds a quantized TinyML anomaly-detection model directly on the STM32U585 microcontroller of the Arduino UNO Q, enabling real-time vibration and acoustic health monitoring of motors, pumps, compressors, and lathes with:

- **Zero cloud dependency**
- **Sub-₹1,500 per-node hardware cost**
- **< 15 ms inference latency**

The UNO Q STM32 MCU continuously samples sensor data and runs a CMSIS-NN autoencoder to flag anomalies locally. On a health event, the UNO Q publishes a compact JSON payload over Wi-Fi to a Snapdragon X Series Copilot+ PC — the plant command centre — which aggregates machine health trends from multiple nodes and uses its on-device NPU to serve a local language model translating anomaly codes into plain-language maintenance guidance, **without sending a single byte to the cloud**.

---

## 2. Problem Statement

India's MSME sector contributes ~30% of GDP and employs over 110 million people. Yet the vast majority operate critical rotating machinery — electric motors, centrifugal pumps, CNC lathes — **without any condition monitoring**.

| Pain Point | Impact |
|-----------|--------|
| Unplanned downtime | A single bearing failure on a production lathe can idle a unit for 3–7 days, costing ₹50,000–₹5,00,000 in lost output |
| No affordable solution | Commercial SCADA/IIoT systems (Emerson AMS, Siemens MindSphere) cost ₹5–25 lakhs per deployment |
| Connectivity constraints | Many tier-2/tier-3 industrial clusters have unreliable internet; cloud-only monitoring simply fails |
| Expertise gap | Plant operators are not data scientists — they need clear, actionable guidance, not raw FFT charts |

The result: preventable failures go undetected, maintenance is entirely reactive, and productivity gains from electrification are undermined by unpredictable breakdowns.

---

## 3. Proposed Solution

Yantra Rakshak is a **retrofit sensor node** — no machine modification required — that clips onto any rotating machine. The system has two layers:

### Layer 1 — Edge Sensing Node (Arduino UNO Q)
- **Hardware sensors:** MPU-6050 IMU (accelerometer + gyroscope) and MEMS microphone via I2C/SPI to the STM32U585 MCU header pins
- **TinyML on MCU:** Pre-trained INT8-quantized LSTM autoencoder compiled with TensorFlow Lite Micro, optimized for Cortex-M33 using CMSIS-NN. Fits within 256 KB FLASH, runs inference in **< 15 ms** at 1 kHz
- **Fault detection:** Autoencoder reconstructs 'healthy' vibration windows; anomaly score above threshold triggers structured JSON alert with fault type, severity, confidence, and timestamp
- **Communication:** Alerts and heartbeat telemetry sent over Wi-Fi 5 (QRB2210 MPU side) via MQTT to local AI PC. **LAN-only — no internet required**
- **Power:** < 500 mW steady-state; USB-C power bank compatible

### Layer 2 — Plant Command Centre (Snapdragon AI PC)
- **Aggregation dashboard:** Python/React dashboard receives MQTT messages from all UNO Q nodes, renders real-time health sparklines per machine, logs all events to local SQLite
- **NPU-accelerated LLM:** Phi-3-mini ONNX runs on Snapdragon NPU — translates raw anomaly codes into maintenance guidance (root cause, recommended action, urgency) in **Hindi or English**
- **Trend analytics:** On-device rolling failure-rate analysis, MTBF estimation, and maintenance scheduling
- **Offline-first:** Entire stack — firmware, MQTT broker, dashboard, LLM — runs with zero internet

---

## 4. System Architecture Overview

```
EDGE LAYER                          INTELLIGENCE LAYER
Arduino UNO Q (STM32U585)    ⟷    Snapdragon X Series Copilot+ PC
```

| Layer | Arduino UNO Q (STM32U585 MCU) | Copilot+ AI PC (Snapdragon X) |
|-------|-------------------------------|-------------------------------|
| Physical | MPU-6050 IMU + MEMS mic, clip-on mount | — |
| Signal | 1 kHz ring-buffer, FFT feature extraction | — |
| Inference | INT8 TFLite Micro autoencoder, Cortex-M33 SIMD | Phi-3-mini ONNX LLM on Snapdragon NPU |
| Communication | MQTT publish over LAN Wi-Fi (QRB2210) | Mosquitto broker, REST API |
| Application | LED health indicator (G/A/R) | React dashboard, alert log, advisory panel |
| Storage | 256 KB FLASH model, 10-min SRAM buffer | SQLite event DB, trend store |

> **Design Principle:** Each device does only what it is best suited for. The MCU handles always-on, sub-15 ms sensor inference. The AI PC handles LLM text generation and multi-machine aggregation. Neither layer can substitute for the other.

---

## 5. End-to-End Data Flow

```
① PHYSICAL SENSING
   Arduino UNO Q — MPU-6050 IMU + MEMS Microphone
   └─ Raw 3-axis acceleration (±16 g) + audio amplitude @ 1 kHz via I2C/SPI
   ↓
② SIGNAL PREPROCESSING
   STM32U585 MCU — Ring Buffer + Feature Extraction
   └─ 128-sample windows → RMS, FFT peak, zero-crossing rate, kurtosis
   ↓
③ TINYML INFERENCE
   Cortex-M33 · TFLite Micro INT8 Autoencoder · <15 ms
   └─ Reconstruction error (MSE) → Anomaly Score → Fault Class + Severity
   ↓
④ DECISION & ALERT
   Threshold Comparison → JSON Health Event Published via MQTT / LAN Wi-Fi
   └─ Payload: { machine_id, fault_type, severity, confidence, ts } → LAN
   ↓
⑤ PC AGGREGATION
   Snapdragon AI PC · Mosquitto Broker → FastAPI → SQLite
   └─ Multi-machine event stream → trend DB → REST API → React dashboard
   ↓
⑥ LLM ADVISORY
   Snapdragon NPU · Phi-3-mini ONNX INT4 · Offline
   └─ Prompt: fault context → Root cause + Action + Urgency in Hindi / English
   ↓
⑦ OPERATOR DISPLAY
   React Dashboard — Machine Cards · Alert History · Advisory Panel
```

> **Offline guarantee:** Steps ①–⑦ run with zero internet. The only network traffic is LAN MQTT between the UNO Q and the AI PC on the same local router/hotspot.

---

## 6. TinyML Inference Pipeline (Arduino UNO Q)

All sensor intelligence runs inside the STM32U585 microcontroller. No data is streamed to the host PC for processing — only structured health events.

### 6.1 Sensor Acquisition Loop
- **Initialize:** SPI → MPU-6050 (accel+gyro, ±16g, 1 kHz ODR) + I2C → MEMS mic PDM stream
- **Ring buffer fill:** 128 samples × 6 channels pushed into SRAM circular buffer (float32 → cast to int8 on entry)
- **Window ready flag:** Set every 128 ms; ISR signals inference task via RTOS semaphore (FreeRTOS on STM32)

### 6.2 Feature Extraction (Pre-Model)

| Domain | Features |
|--------|----------|
| Time domain | RMS amplitude, peak-to-peak, kurtosis, crest factor per axis |
| Frequency domain | 8-point FFT via CMSIS-DSP `arm_rfft_fast_f32`; top-3 peak frequencies |
| Audio | Zero-crossing rate + spectral centroid from PDM buffer |
| Output | 32-float feature vector → quantized to int8 for model input |

### 6.3 Autoencoder Inference

Model: **1D Conv Autoencoder**, trained offline on CWRU Bearing + MIMII datasets.

| Stage | Layer | Detail |
|-------|-------|--------|
| Encoder | Conv1D × 3 | Filters: 32→16→8, kernel=3, ReLU, CMSIS-NN opt |
| Bottleneck | Dense | 16-dim latent vector — compressed health signature |
| Decoder | Conv1DTranspose × 3 | 8→16→32→input reconstruction |
| Loss | MSE | Reconstruction error = anomaly score |
| Quantization | INT8 PTQ | TFLite representative dataset API; model = **48 KB FLASH** |
| Latency | **< 15 ms** | On Cortex-M33 @ 160 MHz with CMSIS-NN SIMD kernels |

### 6.4 Fault Classification & Threshold

1. **Calibration:** On first boot, 30-second healthy baseline sets `MSE₀ = mean + 3σ`; stored to Flash via `HAL_FLASH_Program`
2. **Scoring:**
   - `score = MSE_current / MSE₀`
   - `score > 1.5` → **WARNING**
   - `score > 2.5` → **CRITICAL**
3. **Fault classes** (latent-space nearest-neighbour):
   - `BEARING_WEAR` — high kurtosis axis X
   - `IMBALANCE` — dominant 1× RPM frequency
   - `LUBRICATION` — broadband noise floor elevation
4. **Output JSON:**
```json
{
  "machine_id": "LATHE-3-BLR",
  "fault": "BEARING_WEAR",
  "severity": "CRITICAL",
  "confidence": 0.91,
  "ts": "2026-07-11T10:30:00Z"
}
```

---

## 7. Communication Layer

### 7.1 UNO Q Side (QRB2210 Linux MPU)

The Arduino UNO Q has two compute elements: the STM32U585 MCU (runs TinyML firmware) and a QRB2210 application processor running Linux.

| Component | Role |
|-----------|------|
| STM32U585 MCU | Runs TFLite Micro, sends JSON over UART @ 115200 baud |
| QRB2210 Linux | Reads UART, publishes to MQTT topic `yantra/<machine_id>/health` |
| Wi-Fi | LAN-only MQTT to local broker on AI PC (no internet) |
| Heartbeat | Every 30 s: `{ machine_id, status:'OK', uptime_s }` even if no fault |

### 7.2 MQTT Topic Schema

| Topic | Purpose | QoS |
|-------|---------|-----|
| `yantra/<machine_id>/health` | Fault alerts + anomaly scores | Level 1 (at-least-once) |
| `yantra/<machine_id>/ping` | 30 s keepalive heartbeat | Level 0 |
| `yantra/<machine_id>/cmd` | PC → MCU: recalibrate, set_threshold | Level 1 |

### 7.3 AI PC Side

- **Mosquitto broker:** Listens on `0.0.0.0:1883` (LAN); all UNO Q nodes connect via same router
- **FastAPI listener:** paho-mqtt Python client → parses JSON → writes to SQLite → triggers LLM
- **LLM trigger:** Only on severity ≥ WARNING; deduplication window = 5 min per fault class
- **REST API:**
  - `GET /api/machines` — current health of all nodes
  - `GET /api/alerts` — paginated event log

---

## 8. AI PC Intelligence Layer (Snapdragon X Series)

### 8.1 LLM Advisory Pipeline

When a health event arrives, FastAPI constructs a structured prompt and invokes **Phi-3-mini-4k-instruct** (INT4 GPTQ, ONNX Runtime + Qualcomm QNN Execution Provider) on the Snapdragon NPU.

```
MQTT Event Received
{ fault:'BEARING_WEAR', severity:'CRITICAL', confidence:0.91, machine:'Lathe-3' }
  ↓
Prompt Builder
Injects fault context, machine history, last 5 alerts → structured system + user prompt
  ↓
Phi-3-mini on Snapdragon NPU
ONNX Runtime + QNN EP · INT4 GPTQ · ~1.5 s first-token latency · fully offline
  ↓
Advisory Output
Root cause · Recommended action · Urgency · Hindi / English toggle
```

**Example advisory output:**
```
Machine Lathe-3  |  CRITICAL — Outer race bearing wear detected (91% confidence)

Root cause: Prolonged operation under radial overload.
            Bearing B6205-2RS shows ~40% race erosion pattern.

Action:     Shut down within 4 hours. Replace bearing. Check shaft alignment.

Urgency:    HIGH — Continued operation risks spindle seizure.
```

### 8.2 Dashboard Architecture

- **Frontend:** React 18 + Recharts + TailwindCSS — served from FastAPI `/static`
- **Machine cards:** Real-time health status (green/amber/red), anomaly score sparkline, last advisory
- **Alert log:** Paginated event table with fault type, severity, confidence, timestamp
- **MTBF trend:** Rolling 7-day mean-time-between-failures per machine from SQLite
- **Offline mode:** Service worker caches dashboard shell; works even if PC loses LAN temporarily

---

## 9. Data Models & State Machine

### 9.1 Health Event Schema (MQTT / SQLite)

| Field | Type | Description |
|-------|------|-------------|
| `machine_id` | string | Unique node ID e.g. `'LATHE-3-BLR'` |
| `ts` | ISO8601 | Event timestamp (MCU RTC, synced via NTP if online) |
| `fault_type` | enum | `BEARING_WEAR` \| `IMBALANCE` \| `LUBRICATION` \| `NORMAL` |
| `severity` | enum | `OK` \| `WARNING` \| `CRITICAL` |
| `confidence` | float [0,1] | Model softmax probability of top fault class |
| `mse_score` | float | Raw reconstruction error relative to baseline (1.0 = baseline) |
| `features` | float[32] | Feature vector snapshot for offline re-analysis |
| `advisory` | string \| null | LLM-generated guidance text (null if severity = OK) |

### 9.2 MCU State Machine

The STM32U585 firmware runs a **four-state machine** managed by FreeRTOS tasks:

| State | Entry Condition | Actions | LED / Output |
|-------|----------------|---------|--------------|
| **INIT** | Power-on / reset | Flash model, init sensors, sync RTC | White blink (2 Hz) |
| **CALIBRATE** | INIT complete / CMD:recalibrate | 30 s healthy baseline, compute MSE₀, store Flash | Blue pulse |
| **MONITOR** | CALIBRATE done | Continuous 128-sample inference @ 1 kHz | Green solid |
| **ALERT** | score > threshold | Publish MQTT event, hold state 60 s | Amber/Red flash |

---

## 10. Deployment & Setup Workflow

### 10.1 Hardware Setup (10 min per node)

1. **Wire sensors** — MPU-6050 SDA→D4, SCL→D5; MEMS mic BCLK→D7, DOUT→D6, LRCK→D8 on UNO Q headers
2. **Clip mount** — Attach sensor node to machine casing with nylon clamp (no drilling required)
3. **Power** — USB-C power bank or 5 V rail from panel board; < 500 mW draw
4. **Flash firmware** — `arduino-cli compile + upload yantra_firmware.ino` via USB-C
5. **Set machine ID** — Edit `config.h`: `#define MACHINE_ID "LATHE-3-BLR"` before flash
6. **Run calibration** — Hold BOOT button 3 s → CALIBRATE state; 30 s healthy run auto-sets baseline

### 10.2 AI PC Software Setup (5 min)

```bash
# 1. Clone repo
git clone https://github.com/team/yantra-rakshak && cd yantra-rakshak

# 2. Install dependencies
pip install -r requirements.txt   # FastAPI, paho-mqtt, onnxruntime-qnn, sqlite3

# 3. Start MQTT broker
sudo systemctl start mosquitto
# OR
docker run -p 1883:1883 eclipse-mosquitto

# 4. Download LLM (~2.3 GB)
python scripts/download_model.py   # Phi-3-mini ONNX INT4

# 5. Launch backend
python main.py   # FastAPI on :8000 + MQTT subscriber

# 6. Open dashboard
# Browser → http://localhost:8000
```

### 10.3 Cost & Scale

| Item | Unit Cost (₹) | Notes |
|------|--------------|-------|
| Arduino UNO Q node | 4,500 | Provided by hackathon |
| MPU-6050 IMU | 120 | Standard breakout |
| MEMS microphone | 80 | PDM, Adafruit breakout |
| Nylon mount + USB cable | 50 | Off-the-shelf |
| **Per-node total** | **~₹1,250** | Excl. UNO Q (demo); ~₹5,850 retail |
| AI PC (Copilot+) | ~₹1,50,000 | Provided by hackathon; **serves 50+ nodes** |
| Software | ₹ 0 | Fully open-source, MIT license |

---

## 11. Alignment with Judging Criteria

| Criterion | Weight | How Yantra Rakshak Scores |
|-----------|--------|--------------------------|
| Technical Implementation | 40 pts | INT8 TFLite Micro on Cortex-M33, CMSIS-NN SIMD kernels, sub-15 ms latency, < 500 mW, dual-device orchestration |
| Use-Case & Innovation | 25 pts | First-of-kind offline TinyML predictive maintenance for MSMEs. LLM advisory in Hindi/English. Real, unmet India-specific need |
| Deployment & Accessibility | 20 pts | Single clip-on node, USB-C power. Dashboard installer script. Calibration via one 30-second run. No cloud accounts required |
| Presentation & Docs | 15 pts | Full README, setup scripts, MIT license, commented firmware, wiring diagram, demo video link |

**Multi-Device Award case:** Removing either device breaks the system. The MCU is the only feasible location for always-on, < 15 ms inference on raw sensor data. The AI PC's NPU is the only feasible location for LLM inference and multi-machine aggregation.

---

## 12. Technology Stack

| Component | Technology |
|-----------|-----------|
| MCU Firmware | Arduino IDE 2.0 + C/C++, TensorFlow Lite Micro, CMSIS-NN, Arduino Bridge RPC |
| Sensor Libraries | MPU-6050 I2C driver (Arduino), PDM microphone library (Zephyr), custom ring-buffer DSP |
| Model Training | Python 3, TensorFlow 2.x, scikit-learn, NumPy (offline, done before hackathon) |
| AI PC Backend | Python 3, Mosquitto MQTT broker, FastAPI, SQLite, ONNX Runtime + Qualcomm QNN EP |
| LLM | Phi-3-mini-4k-instruct (ONNX, INT4 GPTQ), Qualcomm AI Hub quantized variant |
| Dashboard | React 18, Recharts, TailwindCSS — served locally from FastAPI |
| DevOps / Repo | GitHub, MIT License, GitHub Actions CI (pytest + firmware build check) |

**Training datasets:**
- [CWRU Bearing Dataset](https://engineering.case.edu/bearingdatacenter)
- [MIMII Dataset](https://zenodo.org/record/3384388)

---

## 13. 24-Hour Build Plan

| Time (IST) | Owner | Milestone |
|-----------|-------|-----------|
| H+0–2 | Full team | Device setup, repo structure, MQTT broker running, firmware skeleton compiles |
| H+2–5 | Firmware lead | MCU sensor read + ring-buffer DSP working; vibration data streaming to serial |
| H+5–8 | ML lead | Pre-trained TFLite model deployed to STM32 via TFLite Micro; anomaly detection producing scores |
| H+8–12 | Backend lead | MQTT publisher on UNO Q MCU side; FastAPI backend receiving events; SQLite logging |
| H+12–16 | Full team | LLM integration on AI PC (Phi-3-mini via ONNX Runtime + QNN); prompt engineering for maintenance advisory |
| H+16–20 | Frontend lead | React dashboard live — real-time machine health cards, alert history, LLM advisory panel |
| H+20–23 | Full team | End-to-end demo run, bug fixes, README, wiring diagram, demo video recording |
| H+23–24 | Team Lead | GitHub repo finalized, Microsoft Form submitted before **1:00 PM deadline** |

---

## 14. Real-World Impact

Yantra Rakshak directly addresses the Government of India's **'Viksit Bharat 2047'** push to modernize MSME manufacturing competitiveness.

| Impact Area | Details |
|------------|---------|
| **Economic** | 20% reduction in unplanned downtime across a 50-machine MSME cluster saves ₹25–50 lakhs/year. Payback on hardware cost under **30 days** |
| **Scalability** | One AI PC aggregates 50+ UNO Q nodes. Total plant cost: ~₹75,000 PC + ₹1,500 × n nodes — **100× cheaper** than commercial IIoT |
| **Accessibility** | No cloud subscription, no data plan. Works in Ludhiana's bicycle-parts clusters, Rajkot's pump factories, Coimbatore's motor-winding shops |
| **Open-source** | MIT-licensed — any MSME association, state government, or NGO can clone and deploy without licensing fees |
| **Language inclusivity** | LLM advisory in Hindi and English — targeting the real user, not the IT manager |

---

## 15. Risk Register & Mitigations

| Risk | Severity | Mitigation |
|------|---------|-----------|
| MCU FLASH too small for model | HIGH | INT8 PTQ brings model to 48 KB; tested offline pre-hackathon |
| Inference latency > 15 ms | MEDIUM | CMSIS-NN kernels; fallback: reduce window to 64 samples |
| MPU-6050 I2C conflict | MEDIUM | Use alternate I2C bus; SPI fallback supported by MPU-6050 |
| LLM first-token > 3 s | LOW | INT4 GPTQ on QNN EP; async advisory (dashboard shows 'Analysing…') |
| LAN Wi-Fi instability | MEDIUM | MQTT QoS 1 with retry; MCU buffers last 10 events in SRAM |
| False positive alerts | MEDIUM | 3σ threshold + 5-min deduplication window suppresses noise |
| Demo hardware failure | LOW | Pre-wired backup node; simulation mode replays recorded sensor CSV |

---

## 16. Open-Source & Compliance

| Requirement (Official Rules §7c) | Status | Implementation |
|----------------------------------|--------|---------------|
| Public GitHub repo | ✅ MIT | [github.com/team/yantra-rakshak](https://github.com/team/yantra-rakshak) |
| README with names, setup, run instructions | ✅ Ready | Drafted; `setup.sh` one-liner |
| No closed-source code | ✅ Yes | TFLite Micro (Apache 2), CMSIS-NN (Apache 2), FastAPI (MIT), React (MIT) |
| Runs on provided platforms | ✅ Yes | Tested: UNO Q + Snapdragon X Series laptop |
| Majority edge / on-device | ✅ 100% | All inference local; no cloud calls |
| Submittable to app store | ✅ Planned | PyPI-installable backend; npm build for dashboard |

---

## 17. Submission Compliance Checklist

| Requirement | Status | Notes |
|------------|--------|-------|
| Public GitHub repository | ✅ Planned | MIT License included |
| README: description, names, emails, setup, run instructions | ✅ Planned | Template drafted |
| Open-source license | ✅ MIT | choosealicense.com |
| Application runnable from provided instructions | ✅ Planned | `install.sh` script |
| Majority of processing runs on-edge (not cloud) | ✅ Yes | 100% offline capable |
| No closed-source existing code | ✅ Yes | All open-source deps |
| GitHub link via Microsoft Form by deadline | ✅ Planned | By July 12, 1:00 PM |
| Live demonstration at venue | ✅ Planned | Physical demo + video |

---

*For queries: QualcommDeveloper@qti.qualcomm.com*  
*Hackathon Site: [qualcomm.com/developer/events/snapdragon-multiverse-hackathon-bangalore](https://qualcomm.com/developer/events/snapdragon-multiverse-hackathon-bangalore)*  
*License: MIT — github.com/team/yantra-rakshak*
