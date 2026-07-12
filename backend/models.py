"""Pydantic schemas for the Yantra Rakshak cloud (laptop) service."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Features(BaseModel):
    """Vibration/acoustic features extracted on the node (Arduino UNO Q)."""
    rms: float = Field(..., description="RMS amplitude of the window")
    kurtosis: float = Field(..., description="Kurtosis - impulsiveness of the signal")
    crest_factor: float = Field(..., description="Peak / RMS ratio")
    peak_freq_hz: float = Field(..., description="Dominant frequency component")
    temp_c: float = Field(..., description="Bearing/casing temperature")


class HealthEvent(BaseModel):
    """Payload published by a node to the cloud on each inference window."""
    machine_id: str
    machine_type: str = "motor"
    location: str = "Shop Floor"
    ts: str = Field(default_factory=_now)

    fault_type: str = "NORMAL"          # NORMAL | BEARING_WEAR | IMBALANCE | LUBRICATION | OVERHEAT
    severity: str = "OK"                # OK | WARNING | CRITICAL
    confidence: float = 0.0             # 0..1 model confidence
    mse_score: float = 1.0              # reconstruction error vs. healthy baseline (1.0 = baseline)

    rpm: int = 0
    features: Features
    waveform: list[float] = Field(default_factory=list, description="Down-sampled window for the UI")


class Advisory(BaseModel):
    """LLM-generated maintenance guidance stored alongside an event."""
    text: str
    root_cause: str
    action: str
    urgency: str
    source: str  # "llm:<model>" or "rules"


class StoredEvent(HealthEvent):
    id: int
    advisory: Optional[Advisory] = None


class NodeStatus(BaseModel):
    machine_id: str
    machine_type: str
    location: str
    severity: str
    fault_type: str
    mse_score: float
    confidence: float
    rpm: int
    temp_c: float
    last_seen: str
    online: bool
    events_total: int
    alerts_total: int
