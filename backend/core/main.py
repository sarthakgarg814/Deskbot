"""DeskBot core — FastAPI app factory + lifespan.

Boot order: config -> DB (init + seed) -> hardware backend -> bus -> ws hub ->
scheduler. Serves the REST API, the `/ws` live stream, and (if present) the
built React dashboard as static files.

Run (from backend/):  uvicorn core.main:app --reload --port 8000
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from common.bus import make_bus
from common.config import load_config
from common.db import init_db
from common.db.seed import seed
from common.logging import setup_logging
from hardware.hal.monitor import RealMonitor

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
    app.state.bus = make_bus(cfg.bus_backend, cfg.redis_url)
    log.info("bus backend: %s", cfg.bus_backend)
    # core does NOT own the servos/LEDs (the hardware process does, D2). It keeps
    # only a read-only system monitor and drives devices by publishing cmd.* .
    app.state.monitor = RealMonitor()
    app.state.ws_hub = WsHub(app.state.bus)
    app.state.scheduler = Scheduler(app.state.bus, app.state.monitor)

    await app.state.ws_hub.start()
    app.state.scheduler.start()
    mirror_task = asyncio.create_task(_mirror_vision_config(app))
    log.info("core ready on %s:%s", cfg.host, cfg.port)
    try:
        yield
    finally:
        mirror_task.cancel()
        app.state.scheduler.shutdown()
        await app.state.ws_hub.stop()
        log.info("core stopped")


async def _mirror_vision_config(app: FastAPI) -> None:
    """Mirror live-tunable settings into bus state keys the vision + hardware
    services poll (camera fps/detect/preview, servo PID/limits). Re-mirrors on
    every settings change so dashboard edits apply without a restart."""
    from common.db import session_scope
    from core.services.settings_service import get_value

    def read_vision(s) -> dict:
        return {
            "preview_enabled": bool(get_value(s, "camera.preview_enabled", False)),
            "tracking_enabled": bool(get_value(s, "camera.tracking_enabled", True)),
            "track_fps": int(get_value(s, "camera.track_fps", 10)),
            "idle_fps": int(get_value(s, "camera.idle_fps", 2)),
            "detect_width": int(get_value(s, "camera.detect_width", 256)),
        }

    def read_servo(s) -> dict:
        return {
            "track_gain": float(get_value(s, "servo.track_gain", 0.5)),
            "fov_pan": float(get_value(s, "servo.fov_pan", 54.0)),
            "fov_tilt": float(get_value(s, "servo.fov_tilt", 41.0)),
            "deadzone": float(get_value(s, "servo.deadzone", 0.04)),
            "max_speed": float(get_value(s, "servo.max_speed", 120)),
            "limit_deg": float(get_value(s, "servo.limit_deg", 80)),
            "pan_offset": float(get_value(s, "servo.pan.offset_deg", 0)),
            "tilt_offset": float(get_value(s, "servo.tilt.offset_deg", 0)),
            "pan_invert": bool(get_value(s, "servo.pan.invert", False)),
            "tilt_invert": bool(get_value(s, "servo.tilt.invert", False)),
            "recenter_after_s": float(get_value(s, "servo.recenter_after_s", 3.0)),
            "tracking_enabled": bool(get_value(s, "camera.tracking_enabled", True)),
        }

    def read_oled(s) -> dict:
        return {
            "mode": str(get_value(s, "oled.mode", "eyes")),        # eyes | status
            "emotion": str(get_value(s, "oled.emotion", "auto")),  # auto | happy | ...
        }

    async def mirror():
        with session_scope() as s:
            v, sv, ol = read_vision(s), read_servo(s), read_oled(s)
        await app.state.bus.set_state("state:vision.config", v)
        await app.state.bus.set_state("state:servo.config", sv)
        await app.state.bus.set_state("state:oled.config", ol)

    await mirror()
    async for _ in app.state.bus.subscribe("settings"):
        await mirror()


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
    # Assets are mounted; every other non-API path falls back to index.html so
    # client-side routes (/notes, /settings) survive a hard refresh.
    cfg = load_config()
    dist = cfg.frontend_dist
    if dist and dist.exists():
        app.mount("/assets", StaticFiles(directory=str(dist / "assets")), name="assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        async def spa_fallback(full_path: str):
            if full_path.startswith(("api/", "ws")):
                raise HTTPException(404)
            return FileResponse(dist / "index.html")

    return app


app = create_app()
