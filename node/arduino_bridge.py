"""
Yantra Rakshak - Arduino USB Serial bridge.

Reads JSON health events from the Arduino UNO Q over USB Serial and
forwards them to the FastAPI cloud service on this laptop.

No sensors required - the Arduino generates synthetic vibration data
that mimics a real machine, runs the anomaly detector, and outputs
newline-delimited JSON at 115200 baud.

Usage:
    python arduino_bridge.py                     # auto-detect port, cloud on :8000
    python arduino_bridge.py --port COM3
    python arduino_bridge.py --port COM3 --url http://127.0.0.1:8010   # non-default cloud port

The bridge also runs the Python simulator for any REMAINING machines
that are not covered by physical Arduino nodes, so you always have
a full 5-node fleet on the dashboard.
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
import time

import requests

CLOUD_DEFAULT = "http://127.0.0.1:8000"

# ---------------------------------------------------------------- serial

def find_arduino_port() -> str | None:
    """Return the first likely Arduino/STM32 serial port."""
    try:
        import serial.tools.list_ports
        keywords = ("arduino", "stm32", "com3", "ch340", "cp210", "ftdi", "usb serial")
        for p in serial.tools.list_ports.comports():
            desc = (p.description or "").lower()
            if any(k in desc for k in keywords):
                return p.device
        # If nothing matched by description, return first available
        ports = list(serial.tools.list_ports.comports())
        if ports:
            return ports[0].device
    except ImportError:
        pass
    return None


def serial_reader(port: str, baud: int, cloud_url: str) -> None:
    """Read JSON lines from the Arduino and POST to the cloud.

    Reconnects automatically if the OS drops the port mid-stream (e.g. a
    USB re-enumeration glitch) instead of hammering a dead handle forever.
    """
    try:
        import serial
    except ImportError:
        print("pyserial not installed. Run: pip install pyserial")
        sys.exit(1)

    print(f"[bridge] Opening {port} at {baud} baud")
    try:
        ser = serial.Serial(port, baud, timeout=2)
    except serial.SerialException as e:
        print(f"[bridge] Could not open {port}: {e}")
        sys.exit(1)

    time.sleep(2)  # let the MCU boot and calibrate
    print(f"[bridge] Listening for Arduino events → {cloud_url}/api/ingest")

    while True:
        try:
            line = ser.readline().decode("utf-8", errors="ignore").strip()
            if not line or not line.startswith("{"):
                if line:
                    print(f"[arduino] {line}")
                continue

            data = json.loads(line)

            # skip calibration status messages
            if "status" in data and "machine_id" not in data:
                print(f"[arduino] {data}")
                continue

            sev = data.get("severity", "OK")
            mid = data.get("machine_id", "?")
            mse = data.get("mse_score", 1.0)
            fault = data.get("fault_type", "NORMAL")
            flag = {"OK": "  ", "WARNING": "!!", "CRITICAL": "XX"}.get(sev, "??")
            print(f"[{flag}] {mid:14s} {sev:8s} {fault:13s} mse={mse:.2f}")

            resp = requests.post(f"{cloud_url}/api/ingest", json=data, timeout=4)
            if resp.status_code != 200:
                print(f"  ! cloud returned {resp.status_code}")

        except json.JSONDecodeError as e:
            print(f"[bridge] bad JSON: {e}")
        except requests.RequestException as e:
            print(f"[bridge] cloud unreachable: {e}")
            time.sleep(2)
        except (serial.SerialException, OSError) as e:
            print(f"[bridge] serial connection lost: {e}")
            try:
                ser.close()
            except Exception:
                pass
            while True:
                print(f"[bridge] reconnecting to {port}...")
                time.sleep(2)
                try:
                    ser = serial.Serial(port, baud, timeout=2)
                    break
                except serial.SerialException:
                    continue
            time.sleep(2)  # let the MCU re-boot and re-calibrate
            print(f"[bridge] reconnected to {port}")


# ---------------------------------------------------------------- keep simulator running for other nodes

def run_remaining_simulator(arduino_id: str, cloud_url: str) -> None:
    """
    Start the Python simulator but skip the machine that the real Arduino
    is covering, so the dashboard always shows a full fleet.
    """
    import sys, os
    sys.path.insert(0, os.path.dirname(__file__))
    from simulator import build_fleet, publish, score_window

    fleet = [m for m in build_fleet() if m.machine_id != arduino_id]
    if not fleet:
        return

    print(f"[sim] Simulating {len(fleet)} remaining nodes: {[m.machine_id for m in fleet]}")
    tick = 0
    while True:
        tick += 1
        for m in fleet:
            m.tick()
            window, temp = m.synth_window()
            result = score_window(window, temp, m.baseline)
            publish(cloud_url, m, result)
        time.sleep(2)


# ---------------------------------------------------------------- main

def main() -> None:
    ap = argparse.ArgumentParser(description="Yantra Rakshak Arduino USB bridge")
    ap.add_argument("--port", default=None, help="Serial port e.g. COM3 (auto-detect if omitted)")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--url", default=CLOUD_DEFAULT)
    ap.add_argument("--no-sim", action="store_true", help="Don't run Python simulator for other nodes")
    args = ap.parse_args()

    port = args.port or find_arduino_port()
    if not port:
        print("[bridge] No Arduino port found. Check USB connection.")
        print("         Specify manually: --port COM3  (Windows) or --port /dev/ttyACM0 (Linux)")
        sys.exit(1)

    print("=" * 60)
    print(" YANTRA RAKSHAK - Arduino Bridge")
    print(f" Arduino port : {port}")
    print(f" Cloud URL    : {args.url}")
    print("=" * 60)

    # figure out which machine_id this Arduino will report
    # (read from the first good JSON line it sends)
    arduino_id = "MOTOR-01"  # default; overridden once we see the first event

    if not args.no_sim:
        sim_thread = threading.Thread(
            target=run_remaining_simulator,
            args=(arduino_id, args.url),
            daemon=True,
        )
        sim_thread.start()

    serial_reader(port, args.baud, args.url)


if __name__ == "__main__":
    main()
