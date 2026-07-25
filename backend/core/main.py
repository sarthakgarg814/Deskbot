"""DeskBot core — FastAPI app factory + lifespan.

Boot order: config -> DB (init + seed) -> hardware backend -> bus -> ws hub ->
scheduler. Serves the REST API, the `/ws` live stream, and (if present) the
built React dashboard as static files.

Run (from backend/):  uvicorn core.main:app --reload --port 8000
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from common.bus import make_bus
from common.config import load_config
from common.db import init_db
from common.db.seed import seed
from common.logging import setup_logging
from hardware.hal import get_hardware

from .api import api_router
from .scheduler import Scheduler
from .ws import WsHub


@asynccontextmanager
async def lifespan(app: FastAPI):
    cfg = load_config()
    log = setup_logging(cfg.log_level, "deskbot.core")
    log.info("starting DeskBot core — hardware backend: %s", cfg.hardware_backend)

    init_db(cfg.db_path)
    seed(cfg.seed_settings)

    app.state.config = cfg
    app.state.bus = make_bus("inprocess")
    app.state.hardware = get_hardware(cfg.hardware_backend)
    app.state.ws_hub = WsHub(app.state.bus)
    app.state.scheduler = Scheduler(app.state.bus, app.state.hardware)

    await app.state.ws_hub.start()
    app.state.scheduler.start()
    log.info("core ready on %s:%s", cfg.host, cfg.port)
    try:
        yield
    finally:
        app.state.scheduler.shutdown()
        await app.state.ws_hub.stop()
        log.info("core stopped")


def create_app() -> FastAPI:
    app = FastAPI(title="DeskBot AI", version="0.1.0", lifespan=lifespan)

    # Dev convenience: the Vite dev server (5173) calls the API cross-origin.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router)

    @app.get("/api/health")
    async def health():
        return {"status": "ok"}

    @app.websocket("/ws")
    async def ws_endpoint(ws: WebSocket):
        hub: WsHub = ws.app.state.ws_hub
        await hub.connect(ws)
        try:
            while True:
                await ws.receive_text()  # client keepalive / future commands
        except WebSocketDisconnect:
            hub.disconnect(ws)

    # Serve the built dashboard if it exists (vite build -> frontend/dist).
    cfg = load_config()
    if cfg.frontend_dist and cfg.frontend_dist.exists():
        app.mount("/", StaticFiles(directory=str(cfg.frontend_dist), html=True), name="frontend")

    return app


app = create_app()
