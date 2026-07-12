# Architecture

This expands on the README's high-level flow with the actual module
boundaries and why they're drawn where they are.

## Components

```
node/simulator.py  ─┐
node/arduino_bridge.py ─┼─→ HTTP POST /api/ingest ─→ backend/main.py ─→ backend/database.py (SQLite)
arduino firmware (real UNO Q) ─┘                              │
                                                                ├─→ backend/llm.py (advisory)
                                                                └─→ WebSocket /ws ─→ frontend/js/app.js
```

- **`node/anomaly.py`** is the single source of truth for the feature
  extraction and scoring math. `node/simulator.py` imports it directly.
  `arduino/yantra_firmware/yantra_firmware.ino` re-implements the same
  formulas in C - the two are kept in sync by hand (there's no shared
  codegen), which is why `TEST_CASES.md` calls out that the firmware path
  isn't automatically tested against the Python one.

- **`backend/main.py`** is intentionally thin: it validates the incoming
  event (via `models.HealthEvent`), delegates storage to `database.py` and
  advisory generation to `llm.py`, and fans out over WebSocket. It does not
  contain scoring logic - that stays on the edge, matching the "majority
  of processing runs on-edge" judging criterion in `Yantra-Rakshak.md`.

- **`backend/llm.py`** has two independent paths: `rule_based()` (pure
  function, no I/O, always available) and `try_ollama()` (async, network
  call, best-effort). `main.py` calls `rule_based()` synchronously for the
  immediate API response, then optionally fires `try_ollama()` as a
  background task that upgrades the stored advisory later. This split
  exists because blocking ingestion on the LLM call was a real bug - see
  `CHANGELOG.md`.

- **`backend/database.py`** owns a single module-level SQLite connection
  (`_conn`) guarded by a `threading.Lock`. This is deliberately simple for
  a single-process demo; it's not designed for multiple backend processes
  sharing one `yantra.db` file.

- **`frontend/`** is vanilla JS with no build step - `index.html` loads
  `charts.js` then `app.js` directly. `app.js` owns a single `state` object
  and re-renders the active view on every WebSocket message; there's no
  virtual DOM or diffing, which is fine at this event rate (~1 event/1.5s
  per machine) but wouldn't scale to a much larger fleet without changes.

## Why HTTP instead of MQTT

`Yantra-Rakshak.md` (the pitch doc) describes an MQTT/Mosquitto broker
architecture. The implementation uses plain HTTP POST to `/api/ingest`
instead - see the docstring in `main.py`. This was a scope simplification:
HTTP needs no broker process, works identically for the simulator, the
Arduino bridge, and (if `WIFI_ENABLED`) the firmware talking directly to
the cloud, and is trivial to test with `curl`. The event schema
(`models.HealthEvent`) is the same shape either way, so swapping in MQTT
later would only touch `main.py`'s ingestion entrypoint and the firmware's
publish call, not the scoring or storage layers.

## Why two ways to get real hardware data in

`node/arduino_bridge.py` (USB serial → HTTP) and `WIFI_ENABLED` in the
firmware (direct Wi-Fi → HTTP) both end at the same `/api/ingest`
endpoint, so the backend can't tell them apart and doesn't need to. USB
serial is the default because it's more reliable on a crowded venue
network - see `SECURITY.md` and the Wi-Fi caveats in the README.
