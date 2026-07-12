"""Unit tests for the on-device anomaly scoring logic (node/anomaly.py).

Run from the node/ folder: pytest
"""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from anomaly import Baseline, WINDOW, extract_features, score_window


def make_baseline() -> Baseline:
    return Baseline(
        rms=0.11, kurtosis=0.0, crest=1.7, peak_freq=48.0, temp=35.0,
        rms_sd=0.03, kurt_sd=0.4, crest_sd=0.3, freq_sd=6.0, temp_sd=2.0,
    )


def healthy_window(base_freq: float = 48.0) -> np.ndarray:
    t = np.arange(WINDOW) / 1000.0
    rng = np.random.default_rng(42)
    sig = 0.15 * np.sin(2 * np.pi * base_freq * t)
    sig += rng.normal(0, 0.02, WINDOW)
    return sig


def test_extract_features_returns_expected_keys():
    feats = extract_features(healthy_window(), temp_c=35.0)
    assert set(feats) == {"rms", "kurtosis", "crest_factor", "peak_freq_hz", "temp_c"}
    assert feats["rms"] > 0


def test_healthy_window_scores_near_baseline():
    base = make_baseline()
    result = score_window(healthy_window(), temp_c=35.0, base=base)
    assert result["severity"] == "OK"
    assert result["fault_type"] == "NORMAL"
    assert result["mse_score"] < 1.5


def test_high_temperature_is_flagged_as_overheat():
    base = make_baseline()
    result = score_window(healthy_window(), temp_c=70.0, base=base)
    assert result["severity"] in ("WARNING", "CRITICAL")
    assert result["fault_type"] == "OVERHEAT"


def test_severity_thresholds_match_documented_bands():
    base = make_baseline()
    ok = score_window(healthy_window(), temp_c=35.0, base=base)
    hot = score_window(healthy_window(), temp_c=90.0, base=base)
    assert ok["mse_score"] < 1.5
    assert hot["mse_score"] >= 1.5


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
