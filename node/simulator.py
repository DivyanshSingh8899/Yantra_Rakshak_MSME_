"""
Yantra Rakshak - multi-node Arduino UNO Q simulator.

Simulates several factory machines, each a node that:
  - generates dummy MPU6050 vibration + temperature data (healthy or faulty)
  - runs the on-device anomaly detector (node/anomaly.py)
  - publishes health events to the cloud (laptop) over HTTP

Machines drift into faults over time so you can watch the dashboard react live.

Run:  python simulator.py            (uses http://127.0.0.1:8000)
      python simulator.py --url http://192.168.1.50:8000 --interval 1.5
"""
from __future__ import annotations

import argparse
import random
import time
from dataclasses import dataclass, field

import numpy as np
import requests

from anomaly import WINDOW, Baseline, score_window

CLOUD_DEFAULT = "http://127.0.0.1:8000"  # not "localhost": Windows can add a ~2s
# per-request penalty resolving localhost -> ::1 before falling back to IPv4


@dataclass
class Machine:
    machine_id: str
    machine_type: str
    location: str
    rpm: int
    base_freq: float          # 1x running frequency (Hz)
    baseline: Baseline
    # fault injection state
    health: float = 1.0        # 1.0 healthy -> degrades toward 0
    degrade_rate: float = 0.0  # per-tick degradation
    fault_bias: str = "BEARING_WEAR"
    temp_c: float = 35.0
    scenario: str = "healthy"

    def synth_window(self) -> tuple[np.ndarray, float]:
        """Produce a dummy MPU6050 vibration window reflecting current health."""
        t = np.arange(WINDOW) / 1000.0
        # base rotating signal at 1x
        sig = 0.15 * np.sin(2 * np.pi * self.base_freq * t)
        # always-present sensor noise
        sig += np.random.normal(0, 0.02, WINDOW)

        severity = 1.0 - self.health  # 0 healthy .. 1 fully degraded
        temp = self.temp_c

        if self.fault_bias == "BEARING_WEAR":
            # high-frequency impulsive impacts + harmonics
            impacts = np.zeros(WINDOW)
            n_impacts = int(2 + severity * 10)
            for _ in range(n_impacts):
                idx = random.randint(0, WINDOW - 1)
                impacts[idx] += random.uniform(0.3, 1.2) * severity
            sig += impacts
            sig += 0.2 * severity * np.sin(2 * np.pi * 8 * self.base_freq * t)
        elif self.fault_bias == "IMBALANCE":
            # strong growth at exactly 1x
            sig += (0.8 * severity) * np.sin(2 * np.pi * self.base_freq * t)
        elif self.fault_bias == "LUBRICATION":
            # elevated broadband noise floor
            sig += np.random.normal(0, 0.25 * severity, WINDOW)
        elif self.fault_bias == "OVERHEAT":
            sig += (0.3 * severity) * np.sin(2 * np.pi * self.base_freq * t)
            temp = self.temp_c + severity * 45.0

        return sig, temp

    def tick(self) -> None:
        """Advance the machine's condition according to its scenario."""
        if self.scenario == "healthy":
            self.health = min(1.0, self.health + 0.01)
        elif self.scenario == "degrading":
            self.health = max(0.05, self.health - self.degrade_rate)
        elif self.scenario == "intermittent":
            if random.random() < 0.2:
                self.health = max(0.2, self.health - 0.15)
            else:
                self.health = min(1.0, self.health + 0.05)
        # slow ambient temperature wobble
        self.temp_c += random.uniform(-0.4, 0.4)
        self.temp_c = max(30.0, min(self.temp_c, 48.0))


def seed_baseline(base_freq: float) -> Baseline:
    """Rough seed; replaced by empirical calibration in calibrate()."""
    return Baseline(
        rms=0.11, kurtosis=0.0, crest=1.7, peak_freq=base_freq, temp=35.0,
        rms_sd=0.03, kurt_sd=0.4, crest_sd=0.3, freq_sd=6.0, temp_sd=2.0,
    )


def calibrate(machine: Machine, n_windows: int = 25) -> None:
    """
    Capture a healthy baseline (mean + std of each feature), mirroring the 30-second
    on-boot calibration the firmware performs. Runs the machine fully healthy so the
    baseline reflects true normal operation - this is what makes OK windows score ~1.0.
    """
    saved_health, saved_scenario = machine.health, machine.scenario
    machine.health, machine.scenario = 1.0, "healthy"

    feats = {k: [] for k in ("rms", "kurtosis", "crest_factor", "peak_freq_hz", "temp_c")}
    for _ in range(n_windows):
        window, temp = machine.synth_window()
        from anomaly import extract_features
        f = extract_features(window, temp)
        for k in feats:
            feats[k].append(f[k])

    def m(k):
        return float(np.mean(feats[k]))

    def s(k, floor):
        return max(float(np.std(feats[k])), floor)

    machine.baseline = Baseline(
        rms=m("rms"), kurtosis=m("kurtosis"), crest=m("crest_factor"),
        peak_freq=m("peak_freq_hz"), temp=m("temp_c"),
        rms_sd=s("rms", 0.01), kurt_sd=s("kurtosis", 0.2),
        crest_sd=s("crest_factor", 0.15), freq_sd=s("peak_freq_hz", 4.0),
        temp_sd=s("temp_c", 1.5),
    )
    machine.health, machine.scenario = saved_health, saved_scenario


def build_fleet() -> list[Machine]:
    specs = [
        ("MOTOR-01", "motor", "Winding Section A", 2880, 48.0, "healthy", "BEARING_WEAR", 0.0),
        ("PUMP-02", "pump", "Coolant Line", 1440, 24.0, "degrading", "BEARING_WEAR", 0.012),
        ("LATHE-03", "lathe", "Machining Bay 1", 2100, 35.0, "degrading", "IMBALANCE", 0.018),
        ("COMPRESSOR-04", "compressor", "Air Utility Room", 1750, 29.0, "intermittent", "LUBRICATION", 0.0),
        ("MOTOR-05", "motor", "Winding Section B", 960, 16.0, "degrading", "OVERHEAT", 0.02),
    ]
    fleet = []
    for mid, mtype, loc, rpm, freq, scenario, fault, rate in specs:
        machine = Machine(
            machine_id=mid, machine_type=mtype, location=loc, rpm=rpm,
            base_freq=freq, baseline=seed_baseline(freq),
            scenario=scenario, fault_bias=fault, degrade_rate=rate,
            health=1.0, temp_c=35.0,
        )
        calibrate(machine)
        fleet.append(machine)
    return fleet


def publish(url: str, machine: Machine, result: dict) -> bool:
    window, _ = machine.synth_window()
    payload = {
        "machine_id": machine.machine_id,
        "machine_type": machine.machine_type,
        "location": machine.location,
        "rpm": machine.rpm,
        "fault_type": result["fault_type"],
        "severity": result["severity"],
        "confidence": result["confidence"],
        "mse_score": result["mse_score"],
        "features": result["features"],
        "waveform": [round(float(v), 4) for v in window[::4]],  # down-sampled for UI
    }
    try:
        r = requests.post(f"{url}/api/ingest", json=payload, timeout=5)
        return r.status_code == 200
    except requests.RequestException as e:
        print(f"  ! could not reach cloud at {url}: {e}")
        return False


def main() -> None:
    ap = argparse.ArgumentParser(description="Yantra Rakshak node simulator")
    ap.add_argument("--url", default=CLOUD_DEFAULT, help="cloud (laptop) base URL")
    ap.add_argument("--interval", type=float, default=2.0, help="seconds between windows")
    args = ap.parse_args()

    fleet = build_fleet()
    print("=" * 60)
    print(" YANTRA RAKSHAK - Node Simulator (Arduino UNO Q fleet)")
    print(f" Publishing to: {args.url}")
    print(f" Nodes: {', '.join(m.machine_id for m in fleet)}")
    print("=" * 60)

    tick = 0
    while True:
        tick += 1
        for m in fleet:
            m.tick()
            window, temp = m.synth_window()
            result = score_window(window, temp, m.baseline)
            ok = publish(args.url, m, result)
            flag = {"OK": "  ", "WARNING": "!!", "CRITICAL": "XX"}[result["severity"]]
            status = "->" if ok else "xx"
            print(
                f"[{tick:04d}] {status} {flag} {m.machine_id:14s} "
                f"{result['severity']:8s} {result['fault_type']:13s} "
                f"mse={result['mse_score']:.2f} conf={result['confidence']:.2f} "
                f"temp={temp:.1f}C"
            )
        print("-" * 60)
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
