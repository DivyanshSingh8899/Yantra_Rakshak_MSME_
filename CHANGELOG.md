# Changelog

## Unreleased

### Fixed
- Node → cloud requests used `http://localhost:8000` by default. On Windows,
  `localhost` can resolve to IPv6 `::1` first and stall before falling back
  to IPv4, adding a ~2s penalty per request. Switched every default (node
  simulator, Arduino bridge, Ollama URL, batch scripts) to `127.0.0.1`.
- `run_arduino.bat` defaulted to cloud port `8010` while `run_cloud.bat`
  defaults to `8000` — running both with no extra arguments silently failed
  to connect. Defaults now match.
- `arduino_bridge.py` looped forever retrying a dead serial handle if the
  OS dropped the port mid-stream (e.g. a USB re-enumeration glitch). It now
  closes and reopens the connection automatically.
- `/api/ingest` awaited the LLM advisory call before responding, so a slow
  or loaded Ollama instance stalled event ingestion for the whole fleet.
  The endpoint now returns the rule-based advisory immediately and
  upgrades it over the WebSocket if the LLM answers in time, capped to one
  in-flight LLM call so requests can't pile up.

### Changed
- `YANTRA_LLM` now defaults to `off`. A CPU-only `phi3:mini` via Ollama
  pins 100% CPU for 30-60s+ per reply on a typical laptop, which visibly
  stutters the live dashboard even with the above fixes. Set `YANTRA_LLM=on`
  to opt in (e.g. on NPU-accelerated hardware).

### Added
- Unit tests for the anomaly scoring pipeline (`node/tests/`).
- GitHub Actions CI (syntax check + test suite).
- MIT `LICENSE` file.
