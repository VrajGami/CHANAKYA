"""
FILE: src/api.py
DESCRIPTION: FastAPI entry point. Hosts the WebSocket server for the Vite Frontend 
and runs the trading orchestrator background task.
"""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import List
import json
import asyncio

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.cache = {}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        # Hydrate new clients with cached state immediately to fix red-dots/empty values
        for msg_type, payload in self.cache.items():
            if payload:
                try:
                    if msg_type == "agent_log":
                        for t, log_payload in payload.items():
                            await websocket.send_text(json.dumps({"type": "agent_log", "data": log_payload}))
                    else:
                        await websocket.send_text(json.dumps({"type": msg_type, "data": payload}))
                except Exception:
                    pass

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message_type: str, payload: dict):
        # Cache critical state
        if message_type in ["portfolio_update", "system_health", "learning_metrics"]:
            self.cache[message_type] = payload
        elif message_type == "market_pulse":
            _pulse_cache = self.cache.get("market_pulse", {})
            if isinstance(_pulse_cache, dict):
                _pulse_cache.update(payload)
                self.cache["market_pulse"] = _pulse_cache
        elif message_type == "agent_log":
            _log_cache = self.cache.get("agent_log", {})
            if not isinstance(_log_cache, dict):
                _log_cache = {}
            _log_cache[payload.get("ticker", "UNKNOWN")] = payload
            self.cache["agent_log"] = _log_cache
            
        message = json.dumps({"type": message_type, "data": payload})
        for connection in list(self.active_connections):
            try:
                await connection.send_text(message)
            except Exception:
                self.disconnect(connection)

ws_manager = ConnectionManager()
_db = None  # Set by main.py after orchestrator is created

@app.websocket("/ws/dashboard")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("type") == "control_command":
                    # Handle pause/play/speed
                    # These will be picked up by the Orchestrator loop
                    ws_manager.cache["last_command"] = msg
            except:
                pass
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)

@app.get("/api/portfolio-history")
async def get_portfolio_history():
    """Returns all historical portfolio snapshots for chart seeding."""
    if _db is None:
        return JSONResponse({"snapshots": []})
    snapshots = _db.get_portfolio_history(limit=500)
    return JSONResponse({"snapshots": snapshots})

@app.get("/api/recent-trades")
async def get_recent_trades():
    """Returns the most recent trades from the database."""
    if _db is None:
        return JSONResponse({"trades": []})
    trades = _db.get_recent_trades(limit=100)
    return JSONResponse({"trades": trades})

@app.get("/api/session-info")
async def get_session_info():
    """Returns session start time for elapsed timer seeding."""
    if _db is None:
        return JSONResponse({"session_start": None})
    session_start = _db.get_session_start_time()
    return JSONResponse({"session_start": session_start})
