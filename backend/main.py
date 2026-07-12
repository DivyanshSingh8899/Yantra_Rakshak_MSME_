"""
Yantra Rakshak - Cloud (laptop) service.

Receives health events from multiple Arduino UNO Q nodes (or the simulator),
persists them, generates a local LLM maintenance advisory, and streams everything
to the dashboard over a WebSocket. Fully offline - no internet required.

Run:  uvicorn main:app --host 0.0.0.0 --port 8000   (from the backend/ folder)
"""
from __future__ import annotations

import asyncio
import json
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import database as db
import llm
from models import HealthEvent

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
OFFLINE_AFTER_S = 15  # a node is "offline" if not heard from within this window


# --------------------------------------------------------------- live state

class Hub:
    """In-memory registry of nodes + WebSocket fan-out to dashboards."""

    def __init__(self) -> None:
        self.nodes: dict[str, dict[str, Any]] = {}
        self.clients: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.clients.add(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self.clients.discard(ws)

    async def broadcast(self, message: dict[str, Any]) -> None:
        dead = []
        payload = json.dumps(message, default=str)
        for ws in list(self.clients):
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    def update_node(self, event: dict[str, Any]) -> None:
        mid = event["machine_id"]
        total, alerts = db.counts_for(mid)
        self.nodes[mid] = {
            "machine_id": mid,
            "machine_type": event.get("machine_type", "motor"),
            "location": event.get("location", "Shop Floor"),
            "severity": event.get("severity", "OK"),
            "fault_type": event.get("fault_type", "NORMAL"),
            "mse_score": event.get("mse_score", 1.0),
            "confidence": event.get("confidence", 0.0),
            "rpm": event.get("rpm", 0),
            "temp_c": (event.get("features") or {}).get("temp_c", 0.0),
            "last_seen": time.time(),
            "events_total": total,
            "alerts_total": alerts,
        }

    def node_list(self) -> list[dict[str, Any]]:
        now = time.time()
        out = []
        for n in self.nodes.values():
            item = dict(n)
            item["online"] = (now - n["last_seen"]) < OFFLINE_AFTER_S
            item["last_seen"] = datetime.fromtimestamp(
                n["last_seen"], tz=timezone.utc
            ).isoformat()
            out.append(item)
        return sorted(out, key=lambda x: x["machine_id"])


hub = Hub()


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    yield


app = FastAPI(title="Yantra Rakshak Cloud", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------------------- ingestion

@app.post("/api/ingest")
async def ingest(event: HealthEvent):
    """A node publishes a health event here (HTTP stand-in for MQTT)."""
    data = event.model_dump()
    is_fault = data.get("severity", "OK") != "OK"

    # Use the instant rule-based advisory for the response so a slow/loaded LLM
    # never stalls event ingestion (nodes publish on a tight interval). If the
    # LLM answers in time, it upgrades this event over the WebSocket instead.
    advisory = llm.rule_based(data) if is_fault else None

    event_id = db.insert_event(data, advisory)
    hub.update_node(data)

    stored = {**data, "id": event_id, "advisory": advisory}
    await hub.broadcast({"type": "event", "event": stored})
    await hub.broadcast({"type": "nodes", "nodes": hub.node_list()})

    # Ollama serializes inference to one request at a time; with a fleet firing
    # every ~1.5s, queuing an upgrade per fault event would pile up unboundedly
    # and starve the box. Only ever have one upgrade in flight - skip the rest.
    if is_fault and llm.LLM_ENABLED != "off" and not _llm_busy.locked():
        asyncio.create_task(_upgrade_advisory(event_id, data))

    return {"ok": True, "id": event_id, "advisory": advisory}


_llm_busy = asyncio.Lock()


async def _upgrade_advisory(event_id: int, data: dict[str, Any]) -> None:
    """Best-effort: replace the rule-based advisory with a real LLM one once ready."""
    async with _llm_busy:
        result = await llm.try_ollama(data)
    if result is None:
        return
    db.update_advisory(event_id, result)
    await hub.broadcast({"type": "advisory", "id": event_id, "advisory": result})


# --------------------------------------------------------------- REST reads

@app.get("/api/nodes")
async def get_nodes():
    return {"nodes": hub.node_list(), "stats": db.fleet_stats()}


@app.get("/api/alerts")
async def get_alerts(limit: int = 50):
    return {"alerts": db.recent_alerts(limit)}


@app.get("/api/machine/{machine_id}/history")
async def get_history(machine_id: str, limit: int = 120):
    return {"machine_id": machine_id, "history": db.machine_history(machine_id, limit)}


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "llm_available": await llm.llm_available(),
        "llm_model": llm.LLM_MODEL,
        "nodes_seen": len(hub.nodes),
        "stats": db.fleet_stats(),
    }


# --------------------------------------------------------------- WebSocket

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await hub.connect(ws)
    try:
        await ws.send_text(json.dumps({"type": "nodes", "nodes": hub.node_list()}))
        await ws.send_text(json.dumps({"type": "alerts", "alerts": db.recent_alerts(30)}))
        while True:
            # keep the socket alive; also lets the client trigger a refresh
            await ws.receive_text()
            await ws.send_text(json.dumps({"type": "nodes", "nodes": hub.node_list()}))
    except WebSocketDisconnect:
        hub.disconnect(ws)
    except Exception:
        hub.disconnect(ws)


# --------------------------------------------------------------- static UI

if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

    @app.get("/")
    async def index():
        return FileResponse(FRONTEND_DIR / "index.html")
