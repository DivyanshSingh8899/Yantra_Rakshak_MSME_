"""
Maintenance advisory generator.

Two backends, tried in order:
  1. Local LLM via Ollama HTTP API (http://localhost:11434) - fully offline once the
     model is pulled. On a Snapdragon Copilot+ PC this maps to an NPU-accelerated
     model; on any laptop it runs on CPU/GPU. Set YANTRA_LLM_MODEL to choose.
  2. Deterministic rule-based expert system - always available, no dependencies,
     so the demo never breaks even without a model installed.

The rule engine encodes real vibration-analysis heuristics (RMS, kurtosis,
crest factor, dominant frequency) so its output is genuinely diagnostic, not canned.
"""
from __future__ import annotations

import os
from typing import Any

import httpx

OLLAMA_URL = os.environ.get("YANTRA_OLLAMA_URL", "http://127.0.0.1:11434")
LLM_MODEL = os.environ.get("YANTRA_LLM_MODEL", "phi3:mini")
LLM_ENABLED = os.environ.get("YANTRA_LLM", "off")  # on | off
# Defaults off: a CPU-only phi3:mini pins 100% CPU for 30-60s+ per reply on a
# typical laptop, which visibly stutters the live multi-machine dashboard even
# with the one-in-flight cap in main.py. Set YANTRA_LLM=on to opt in (e.g. on
# NPU-accelerated Snapdragon hardware, or for a quiet single-fault demo).
# On CPU-only hardware phi3:mini can take 30-60s+ per reply, which would stall
# event ingestion for every fault. Fail fast and fall back to rules so the live
# dashboard stays responsive; raise this on NPU-accelerated (QNN) hardware.
LLM_TIMEOUT_S = float(os.environ.get("YANTRA_LLM_TIMEOUT", "6.0"))

_SYSTEM = (
    "You are Yantra Rakshak, a maintenance expert for Indian MSME factory machines "
    "(motors, pumps, compressors, lathes). You receive a machine fault detected by an "
    "on-device TinyML model. Reply with exactly three short labelled lines and nothing else:\n"
    "ROOT CAUSE: <one sentence, plain language>\n"
    "ACTION: <one concrete step an operator can take>\n"
    "URGENCY: <LOW | MEDIUM | HIGH> - <few words why>\n"
    "Be concrete and practical. No preamble, no markdown."
)

# ---------------------------------------------------------------- rule engine

_FAULT_LIBRARY: dict[str, dict[str, str]] = {
    "BEARING_WEAR": {
        "root": "High-frequency impacts and elevated kurtosis point to rolling-element "
                "bearing wear (spalling on the race or rollers).",
        "action": "Schedule bearing replacement (e.g. 6205-2RS). Inspect for pitting and "
                  "re-grease if replacement is not immediately possible.",
    },
    "IMBALANCE": {
        "root": "A dominant vibration peak at 1x running speed indicates rotor imbalance "
                "or material build-up on the rotating assembly.",
        "action": "Stop and clean the rotor/impeller. If it persists, dynamically "
                  "balance the assembly and check for a bent shaft.",
    },
    "LUBRICATION": {
        "root": "A raised broadband noise floor is typical of lubrication starvation or "
                "contamination causing metal-to-metal friction.",
        "action": "Apply the specified lubricant and verify the oil/grease level. Check "
                  "seals for contamination ingress.",
    },
    "OVERHEAT": {
        "root": "Casing temperature is above the safe limit, usually from overload, "
                "cooling-airflow blockage, or an electrical fault.",
        "action": "Reduce load and clear cooling vents/fan. Verify supply voltage balance "
                  "and winding insulation if temperature stays high.",
    },
    "NORMAL": {
        "root": "Vibration signature is within the healthy baseline.",
        "action": "No action required. Continue routine monitoring.",
    },
}


def _urgency(severity: str, mse: float) -> str:
    if severity == "CRITICAL":
        return f"HIGH - reconstruction error {mse:.1f}x baseline; risk of imminent failure."
    if severity == "WARNING":
        return f"MEDIUM - error {mse:.1f}x baseline; degrading, plan intervention this week."
    return "LOW - operating normally."


def rule_based(event: dict[str, Any]) -> dict[str, str]:
    fault = event.get("fault_type", "NORMAL")
    severity = event.get("severity", "OK")
    mse = float(event.get("mse_score", 1.0))
    lib = _FAULT_LIBRARY.get(fault, _FAULT_LIBRARY["NORMAL"])
    f = event.get("features", {}) or {}

    detail = (
        f" Measured RMS {f.get('rms', 0):.2f} g, kurtosis {f.get('kurtosis', 0):.1f}, "
        f"crest {f.get('crest_factor', 0):.1f}, peak {f.get('peak_freq_hz', 0):.0f} Hz, "
        f"{f.get('temp_c', 0):.0f} deg C."
    )
    urgency = _urgency(severity, mse)
    text = (
        f"{event.get('machine_id')} - {fault.replace('_', ' ').title()} "
        f"({int(event.get('confidence', 0) * 100)}% confidence).\n"
        f"ROOT CAUSE: {lib['root']}{detail}\n"
        f"ACTION: {lib['action']}\n"
        f"URGENCY: {urgency}"
    )
    return {
        "text": text,
        "root_cause": lib["root"],
        "action": lib["action"],
        "urgency": urgency,
        "source": "rules",
    }


# ---------------------------------------------------------------- LLM backend

def _build_prompt(event: dict[str, Any]) -> str:
    f = event.get("features", {}) or {}
    return (
        f"Machine: {event.get('machine_id')} ({event.get('machine_type')}), "
        f"location {event.get('location')}.\n"
        f"Detected fault: {event.get('fault_type')} | severity {event.get('severity')} | "
        f"confidence {event.get('confidence')}.\n"
        f"Reconstruction error: {event.get('mse_score')}x healthy baseline.\n"
        f"Features -> RMS {f.get('rms')} g, kurtosis {f.get('kurtosis')}, "
        f"crest factor {f.get('crest_factor')}, dominant freq {f.get('peak_freq_hz')} Hz, "
        f"temperature {f.get('temp_c')} C, speed {event.get('rpm')} rpm.\n"
        "Give the maintenance guidance now."
    )


def _parse_llm(text: str, event: dict[str, Any]) -> dict[str, str]:
    root = action = urgency = ""
    for line in text.splitlines():
        low = line.lower()
        if low.startswith("root cause:"):
            root = line.split(":", 1)[1].strip()
        elif low.startswith("action:"):
            action = line.split(":", 1)[1].strip()
        elif low.startswith("urgency:"):
            urgency = line.split(":", 1)[1].strip()
    fallback = rule_based(event)
    return {
        "text": text.strip(),
        "root_cause": root or fallback["root_cause"],
        "action": action or fallback["action"],
        "urgency": urgency or fallback["urgency"],
        "source": f"llm:{LLM_MODEL}",
    }


async def try_ollama(event: dict[str, Any]) -> dict[str, str] | None:
    try:
        async with httpx.AsyncClient(timeout=LLM_TIMEOUT_S) as client:
            resp = await client.post(
                f"{OLLAMA_URL}/api/chat",
                json={
                    "model": LLM_MODEL,
                    "stream": False,
                    "messages": [
                        {"role": "system", "content": _SYSTEM},
                        {"role": "user", "content": _build_prompt(event)},
                    ],
                    "options": {"temperature": 0.2},
                },
            )
            resp.raise_for_status()
            content = resp.json().get("message", {}).get("content", "")
            if content.strip():
                return _parse_llm(content, event)
    except Exception:
        return None
    return None


async def llm_available() -> bool:
    if LLM_ENABLED == "off":
        return False
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            r = await client.get(f"{OLLAMA_URL}/api/tags")
            return r.status_code == 200
    except Exception:
        return False
