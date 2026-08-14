from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, List, Optional
import asyncio
import os
import sys
import uuid
from datetime import datetime
import logging
from sqlalchemy.orm import Session

from database import init_db, get_db, SessionLocal
from models import ExplorationSession, Finding, ExplorationPath
from exploration_engine import ExplorationEngine

# uvicorn only configures its own loggers, so module loggers (exploration_engine,
# browser_automation) would otherwise be silent under `python main.py`.
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s:     [%(name)s] %(message)s",
)

# Initialize database
init_db()

app = FastAPI(title="Vanguard-X API")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Models
class ExplorationConfig(BaseModel):
    start_url: str
    depth: int = 5
    max_time: int = 300
    browser_type: str = "chromium"
    explore_visual: bool = True
    explore_console: bool = True
    explore_network: bool = True

# WebSocket Manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
        self.exploration_tasks: Dict[str, asyncio.Task] = {}

    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        if session_id not in self.active_connections:
            self.active_connections[session_id] = []
        self.active_connections[session_id].append(websocket)

    def disconnect(self, websocket: WebSocket, session_id: str):
        connections = self.active_connections.get(session_id)
        if not connections:
            return
        if websocket in connections:
            connections.remove(websocket)
        if not connections:
            del self.active_connections[session_id]

    async def send_message(self, session_id: str, message: dict):
        # Iterate over a copy: a dead socket must not abort delivery to the
        # remaining clients, and we prune it as we go.
        for connection in list(self.active_connections.get(session_id, [])):
            try:
                await connection.send_json(message)
            except Exception:
                logging.debug("Dropping dead websocket for session %s", session_id)
                self.disconnect(connection, session_id)

manager = ConnectionManager()

@app.on_event("startup")
async def _log_event_loop():
    # Playwright spawns the browser driver as a subprocess, which Windows'
    # SelectorEventLoop cannot do (raises NotImplementedError). Log which loop
    # we actually got so that failure is diagnosable.
    loop = asyncio.get_running_loop()
    logging.info("Event loop: %s", type(loop).__name__)
    if sys.platform == "win32" and "Proactor" not in type(loop).__name__:
        logging.error(
            "Windows requires a ProactorEventLoop for Playwright; got %s. "
            "Browser launches will fail with NotImplementedError.",
            type(loop).__name__,
        )

@app.get("/")
async def root():
    return {"status": "ok", "service": "Vanguard-X API"}

@app.get("/health")
async def health():
    """Liveness probe; the frontend's api.healthCheck() calls this."""
    return {
        "status": "ok",
        "active_sessions": len(manager.exploration_tasks),
        "websocket_clients": sum(len(v) for v in manager.active_connections.values()),
    }

@app.post("/api/explore/start")
async def start_exploration(config: ExplorationConfig):
    session_id = str(uuid.uuid4())
    
    # Create database record
    db = SessionLocal()
    session = ExplorationSession(
        id=session_id,
        start_url=config.start_url,
        depth=config.depth,
        max_time=config.max_time,
        browser_type=config.browser_type,
        config=config.dict()
    )
    db.add(session)
    db.commit()
    db.close()
    
    # Start exploration
    engine = ExplorationEngine(session_id, config.dict())
    task = asyncio.create_task(engine.explore(manager))
    manager.exploration_tasks[session_id] = task

    def _log_task_result(t: asyncio.Task):
        # A bare create_task swallows exceptions; surface them instead.
        if t.cancelled():
            logging.warning("Exploration %s was cancelled", session_id)
        elif t.exception() is not None:
            logging.error("Exploration %s crashed", session_id, exc_info=t.exception())

    task.add_done_callback(_log_task_result)

    return {"session_id": session_id, "status": "started"}

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await manager.connect(websocket, session_id)
    try:
        while True:
            data = await websocket.receive_text()
            # Handle messages if needed
    except WebSocketDisconnect:
        pass
    except Exception:
        # A client that vanishes without a close frame surfaces as
        # ConnectionResetError (WinError 10054) rather than WebSocketDisconnect.
        logging.debug("Websocket for session %s ended abnormally", session_id, exc_info=True)
    finally:
        manager.disconnect(websocket, session_id)

if __name__ == "__main__":
    import uvicorn
    # Reload is OFF by default on purpose. uvicorn picks the event loop in
    # uvicorn/loops/asyncio.py:
    #
    #     if sys.platform == "win32" and not use_subprocess:
    #         return asyncio.ProactorEventLoop
    #     return asyncio.SelectorEventLoop
    #
    # use_subprocess is True whenever reload/workers are on, so on Windows
    # --reload forces a SelectorEventLoop. That loop cannot spawn subprocesses,
    # and Playwright launches the browser as one — every exploration then dies
    # with NotImplementedError before the browser opens. Reload and Playwright
    # are mutually exclusive on Windows.
    #
    # Opt in with RELOAD=true (safe on Linux/macOS, breaks browsing on Windows).
    use_reload = os.getenv("RELOAD", "").strip().lower() in ("1", "true", "yes")
    if use_reload and sys.platform == "win32":
        logging.warning(
            "RELOAD is ignored on Windows: it forces a SelectorEventLoop, which "
            "prevents Playwright from launching a browser."
        )
        use_reload = False

    # reload/workers also require an import string rather than the app object;
    # passing the object made uvicorn exit with STARTUP_FAILURE.
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=use_reload,
        # The SQLite file lives in this directory, so a session write would
        # otherwise trip the watcher and kill the run mid-exploration.
        reload_excludes=["*.db", "*.db-journal", "*.db-wal", "*.db-shm",
                         "__pycache__/*", "*.pyc"],
    )