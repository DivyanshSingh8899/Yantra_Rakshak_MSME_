# Security policy

## Design posture

Yantra Rakshak is built to be **fully offline**. By default:

- The only network traffic is on the local LAN: nodes (Arduino UNO Q or the
  simulator) → cloud service (`127.0.0.1` or the laptop's LAN IP), and
  optionally the cloud service → a local Ollama instance (also `127.0.0.1`).
- No telemetry, analytics, or external API calls are made.
- All persisted data (`backend/yantra.db`) stays on the laptop running the
  cloud service.

If you're deploying this beyond a demo, be aware of what it does **not**
provide out of the box:

- No authentication on the REST API or WebSocket - anyone on the same LAN
  can read fleet data or POST fabricated events to `/api/ingest`.
- No TLS - traffic on the LAN is unencrypted.
- The Wi-Fi credentials in `arduino/yantra_firmware/config.h` are plaintext
  in the firmware source, as is normal for Arduino sketches - don't commit
  real credentials to a public repo (the checked-in file uses placeholders).

For a shop-floor deployment beyond a hackathon demo, put the cloud service
behind a reverse proxy with auth, or restrict it to a dedicated VLAN.

## Reporting an issue

This is a hackathon project without a dedicated security team. If you find
a vulnerability, please open a GitHub issue describing it - there's no
sensitive production deployment behind this repository to protect.
