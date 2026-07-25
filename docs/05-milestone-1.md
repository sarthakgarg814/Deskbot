# 05 — Milestone 1: Backend + Dashboard Skeleton

The first **vertical slice**: a running `core` process + React dashboard, talking
over REST + WebSocket, backed by SQLite, with hardware **stubbed** behind the HAL
seam. This is the backbone every later feature plugs into — no camera, voice, or
real servos yet, but the wiring, live updates, and settings persistence are real.

## Goal / definition of done

- `deskbot.local` (or Pi IP) serves the React dashboard.
- Dashboard **Home** shows live CPU/RAM/temp/storage updating over WebSocket
  (real values via `psutil`/`vcgencmd` — this part *is* real on the Pi).
- **Settings** page reads/writes the `settings` table; changes persist across
  restart and emit `event.settings.changed`.
- **Notes** page: create / list / search / edit / delete against SQLite (FTS).
- **Hardware** page: servo test, LED test, OLED preview buttons call the API and
  hit **stub** drivers that log + update `state:*` (so the UI shows feedback).
- A `mock` hardware backend satisfies the whole HAL so nothing needs real
  peripherals for this milestone.
- systemd unit for `core`; boots on the Pi; `<2s` UI load target measured.

## Scope IN

| Area | This milestone |
|------|----------------|
| core | FastAPI app, config loader, SQLite + Alembic, WebSocket hub, REST for system/notes/settings/hardware-stub, APScheduler (heartbeat + hw-monitor sample) |
| bus | `common/bus.py` — Redis-backed **or** in-process (D3 decision); state cache + pub/sub |
| hardware | HAL interfaces + **mock** drivers; real `HardwareMonitor` (psutil/vcgencmd) so system stats are genuine |
| frontend | Vite+React+Tailwind shell, routing, WS client, Home / Notes / Settings / Hardware pages |
| db | schema from [03](03-database-schema.md), seeded from `config/defaults.yaml` |
| ops | `deskbot-core.service`, dev run scripts, README run steps |

## Scope OUT (later milestones)

Face tracking, PID, camera, presence, mood detection, voice/wake word/STT,
calendar sync, LED animations on real strip, OLED real render, touch. Their API
endpoints may exist but return `501`/stub until their milestone.

## Proposed structure delivered in M1

```
backend/
├── core/
│   ├── main.py            # FastAPI app factory, static mount, lifespan
│   ├── api/               # routers: system, notes, settings, hardware, ws
│   ├── ws/hub.py          # websocket fan-out from bus
│   ├── scheduler.py       # APScheduler jobs
│   └── services/          # notes_service, settings_service
├── common/
│   ├── bus.py             # Redis|in-proc abstraction (D3 seam)
│   ├── config.py          # yaml defaults + settings-table overlay
│   ├── db/                # engine, session, models (SQLAlchemy), migrations
│   ├── schemas/           # pydantic request/response models
│   └── logging.py
├── hardware/
│   ├── hal/base.py        # interfaces
│   ├── hal/monitor.py     # REAL psutil/vcgencmd
│   └── hal/mock/          # mock servo/oled/led/touch
└── pyproject.toml
frontend/
├── src/{pages,components,lib/ws.ts,lib/api.ts}
├── index.html vite.config.ts tailwind.config.js
config/
├── defaults.yaml
└── systemd/deskbot-core.service
```

## Build order (small, verifiable steps)

1. **Scaffold repo**: `backend/pyproject.toml`, `frontend/` Vite app, `config/`,
   `.gitignore`, run scripts. Nothing functional yet — confirms toolchains on Pi.
2. **DB + config**: SQLAlchemy models + Alembic init + `config.py` overlay +
   seed from `defaults.yaml`. Test: migrate + seed on a fresh file.
3. **bus seam**: `common/bus.py` — **in-process async backend** for M1 (D3), with
   the Redis backend stubbed behind the same interface. Test: publish/subscribe +
   set/get state round-trip.
4. **core skeleton**: FastAPI app, lifespan starts bus + scheduler, `GET
   /api/system` returns real stats, `/ws` streams `system` at 1 Hz.
5. **Frontend shell**: layout, nav, WS client, **Home** page live tiles. Test in
   browser against core.
6. **Notes** end-to-end: API + service + FTS + React page (create/search/edit/
   delete).
7. **Settings** end-to-end: API + React form driven by `settings` rows + hot-
   reload event.
8. **Hardware page (stubbed)**: mock servo/led/oled drivers + endpoints; UI shows
   logged feedback + OLED preview PNG from the mock.
9. **Package**: `deskbot-core.service`, boot on Pi, measure UI-load + boot time
   against §11 targets; write run/deploy steps into README.

Each step is a reviewable commit. We stop and check after step 4 (backend alive)
and step 5 (dashboard alive) before pressing on.

## Risks / watch-items for M1

- **Frontend build (D5, decided):** `vite build` runs on your laptop; the `dist/`
  bundle is copied to the Pi and served by `core` via StaticFiles. A `make
  deploy-frontend` / rsync script handles the copy. The Pi never runs `npm build`.
- **`vcgencmd` path/permissions** for temp — verify the monitor reads temp under
  the service user.
- **D3 not yet decided** — step 3 depends on it. Default plan: in-process bus for
  M1, swap to Redis when `vision` arrives; zero API change.

## Exit → Milestone 2

With the backbone proven, M2 is **camera face-tracking**: `vision` process,
MediaPipe face detect, publish `cmd.servo.target`, and the **real** servo arbiter
+ PID in `hardware` — the first physical behavior. The bus, state cache, and
dashboard live-view built in M1 make that a plug-in, not a rebuild.
