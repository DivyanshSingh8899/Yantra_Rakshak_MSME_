"""
Pre-demo smoke test - run this against a running cloud service to confirm
the whole stack (backend, at least one publishing node, dashboard static
files) is actually healthy before you're in front of judges.

Usage:
    python scripts/smoke_test.py                       # checks http://127.0.0.1:8000
    python scripts/smoke_test.py --url http://127.0.0.1:8010
"""
from __future__ import annotations

import argparse
import sys

import requests

CHECKS_PASSED = 0
CHECKS_FAILED = 0


def check(name: str, fn) -> None:
    global CHECKS_PASSED, CHECKS_FAILED
    try:
        detail = fn()
        print(f"  OK   {name}" + (f" - {detail}" if detail else ""))
        CHECKS_PASSED += 1
    except Exception as e:
        print(f"  FAIL {name} - {e}")
        CHECKS_FAILED += 1


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8000")
    args = ap.parse_args()
    url = args.url.rstrip("/")

    print(f"Yantra Rakshak smoke test - {url}")
    print("-" * 60)

    def dashboard_reachable():
        r = requests.get(f"{url}/", timeout=5)
        assert r.status_code == 200, f"status {r.status_code}"
        assert "Yantra Rakshak" in r.text, "unexpected page content"

    def health_ok():
        r = requests.get(f"{url}/api/health", timeout=5)
        assert r.status_code == 200
        data = r.json()
        assert data.get("status") == "ok"
        return f"llm_available={data.get('llm_available')}"

    def nodes_publishing():
        r = requests.get(f"{url}/api/nodes", timeout=5)
        assert r.status_code == 200
        nodes = r.json().get("nodes", [])
        assert len(nodes) > 0, "no nodes have published yet - is a node running?"
        online = [n for n in nodes if n.get("online")]
        assert online, f"{len(nodes)} node(s) known but none are online right now"
        return f"{len(online)}/{len(nodes)} nodes online"

    def alerts_endpoint_ok():
        r = requests.get(f"{url}/api/alerts?limit=5", timeout=5)
        assert r.status_code == 200
        assert "alerts" in r.json()

    def static_assets_served():
        r = requests.get(f"{url}/static/js/app.js", timeout=5)
        assert r.status_code == 200
        assert len(r.text) > 100

    check("Dashboard HTML reachable", dashboard_reachable)
    check("/api/health responds", health_ok)
    check("At least one node is online", nodes_publishing)
    check("/api/alerts responds", alerts_endpoint_ok)
    check("Static JS/CSS served", static_assets_served)

    print("-" * 60)
    print(f"{CHECKS_PASSED} passed, {CHECKS_FAILED} failed")
    sys.exit(1 if CHECKS_FAILED else 0)


if __name__ == "__main__":
    main()
