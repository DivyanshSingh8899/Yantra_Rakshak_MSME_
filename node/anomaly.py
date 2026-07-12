"""
On-device anomaly detection (mirrors what runs on the Arduino UNO Q STM32 MCU).

This reproduces the TinyML pipeline in Python so the simulator behaves exactly like
the firmware:
  1. read a window of vibration samples (dummy MPU6050 here)
  2. extract features: RMS, kurtosis, crest factor, dominant frequency
  3. score the window against a learned "healthy" baseline (autoencoder-style
     reconstruction error, approximated with a Mahalanobis-like statistical distance)
  4. classify the fault and severity

The real firmware uses an INT8 TFLite-Micro autoencoder; the feature maths and the
thresholding logic are identical, which is what makes the demo faithful.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

SAMPLE_RATE = 1000  # Hz
WINDOW = 128        # samples per inference window


@dataclass
class Baseline:
    """Healthy reference learned during the 30-second calibration on boot."""
    rms: float
    kurtosis: float
    crest: float
    peak_freq: float
    temp: float
    # spread (std) of each feature under healthy operation
    rms_sd: float
    kurt_sd: float
    crest_sd: float
    freq_sd: float
    temp_sd: float


def extract_features(window: np.ndarray, temp_c: float) -> dict[str, float]:
    """Time + frequency domain features from a vibration window."""
    x = window - np.mean(window)
    rms = float(np.sqrt(np.mean(x ** 2)))
    peak = float(np.max(np.abs(x)))
    crest = float(peak / rms) if rms > 1e-6 else 0.0

    # kurtosis (Fisher, excess). High kurtosis => impulsive => bearing faults.
    std = np.std(x)
    kurt = float(np.mean((x / std) ** 4) - 3.0) if std > 1e-6 else 0.0

    # dominant frequency via rFFT
    spec = np.abs(np.fft.rfft(window * np.hanning(len(window))))
    freqs = np.fft.rfftfreq(len(window), d=1.0 / SAMPLE_RATE)
    peak_freq = float(freqs[int(np.argmax(spec[1:]) + 1)]) if len(spec) > 1 else 0.0

    return {
        "rms": round(rms, 4),
        "kurtosis": round(kurt, 3),
        "crest_factor": round(crest, 3),
        "peak_freq_hz": round(peak_freq, 1),
        "temp_c": round(temp_c, 1),
    }


def reconstruction_error(feats: dict[str, float], base: Baseline) -> float:
    """
    Autoencoder-style anomaly score, normalised so 1.0 == healthy baseline.

    For each feature we measure the deviation in standard-deviations (sigma) from the
    healthy baseline, subtract 1 sigma of expected natural noise, and clamp. Averaging
    the excess deviation keeps healthy windows near 1.0 (no false alarms) while faults -
    which push several features well beyond their normal range - climb steadily.
    """
    devs = [
        abs(feats["rms"] - base.rms) / max(base.rms_sd, 1e-3),
        abs(feats["kurtosis"] - base.kurtosis) / max(base.kurt_sd, 1e-3),
        abs(feats["crest_factor"] - base.crest) / max(base.crest_sd, 1e-3),
        abs(feats["peak_freq_hz"] - base.peak_freq) / max(base.freq_sd, 1e-3),
        abs(feats["temp_c"] - base.temp) / max(base.temp_sd, 1e-3),
    ]
    # excess deviation beyond 1 sigma of natural noise, clamped so one feature
    # cannot saturate the score by itself
    excess = [min(max(d - 1.0, 0.0), 10.0) for d in devs]
    score = sum(excess) / len(excess)
    return round(1.0 + 0.55 * score, 3)


def classify(feats: dict[str, float], base: Baseline) -> tuple[str, float]:
    """Nearest-signature fault classification. Returns (fault_type, confidence)."""
    scores = {
        "BEARING_WEAR": max(0.0, (feats["kurtosis"] - base.kurtosis) / 5.0)
        + max(0.0, (feats["crest_factor"] - base.crest) / 3.0),
        "IMBALANCE": max(0.0, (feats["rms"] - base.rms) / max(base.rms, 0.1))
        - abs(feats["peak_freq_hz"] - base.peak_freq) / 200.0,
        "LUBRICATION": max(0.0, (feats["rms"] - base.rms) / max(base.rms, 0.1)) * 0.6
        + max(0.0, (feats["peak_freq_hz"] - base.peak_freq) / 300.0),
        "OVERHEAT": max(0.0, (feats["temp_c"] - base.temp) / 20.0),
    }
    fault = max(scores, key=scores.get)
    raw = scores[fault]
    confidence = round(min(0.99, 0.55 + raw * 0.4), 2)
    return fault, confidence


def score_window(window: np.ndarray, temp_c: float, base: Baseline) -> dict:
    """Full inference step: features -> error -> severity -> classification."""
    feats = extract_features(window, temp_c)
    mse = reconstruction_error(feats, base)

    if mse >= 2.5:
        severity = "CRITICAL"
    elif mse >= 1.5:
        severity = "WARNING"
    else:
        severity = "OK"

    if severity == "OK":
        return {
            "features": feats,
            "mse_score": mse,
            "severity": "OK",
            "fault_type": "NORMAL",
            "confidence": round(min(0.99, 1.2 - (mse - 1.0)), 2),
        }

    fault, confidence = classify(feats, base)
    # temperature-driven faults dominate when hot
    if feats["temp_c"] - base.temp > 15:
        fault, confidence = "OVERHEAT", max(confidence, 0.88)

    return {
        "features": feats,
        "mse_score": mse,
        "severity": severity,
        "fault_type": fault,
        "confidence": confidence,
    }
