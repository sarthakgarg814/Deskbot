# DeskBot AI

A privacy-first, local-first AI desktop companion built on a Raspberry Pi 4. It
physically follows your face, tracks healthy habits, manages notes and calendar,
and responds to voice — processing almost everything **on-device**.

> Full product spec: this is the engineering design. The product vision lives in
> the PRD. Start with the design docs below before writing feature code.

## Design docs (read in order)

| # | Doc | What it covers |
|---|-----|----------------|
| 00 | [Overview & decisions](docs/00-overview.md) | Principles, the 4 crux architecture decisions, decision log |
| 01 | [Architecture](docs/01-architecture.md) | Process model, service boundaries, message bus, servo arbitration, concurrency, deployment |
| 02 | [Hardware layer](docs/02-hardware-layer.md) | HAL interfaces per peripheral, driver choices, servo arbiter contract |
| 03 | [Database schema](docs/03-database-schema.md) | Full SQLite schema, single-writer rule |
| 04 | [API contract](docs/04-api-contract.md) | REST endpoints + WebSocket + Redis topic contracts |
| 05 | [Milestone 1](docs/05-milestone-1.md) | Backend + Dashboard skeleton — detailed build plan |

## Repository map

```
deskbot/
├── backend/            # Python — the four services + shared libs
│   ├── core/           #   FastAPI app, WebSocket, scheduler, reminder engine
│   ├── vision/         #   camera, face detection, presence, mood detection
│   ├── hardware/       #   OLED, LED, servo (+ arbiter), touch, hw monitor
│   ├── voice/          #   wake word, STT, intent engine
│   ├── common/         #   bus (Redis), config, db models, schemas, logging
│   └── ...
├── frontend/           # React + Vite + Tailwind dashboard (served by core)
├── firmware/           # any microcontroller sketches (touch/led offload, future)
├── config/             # YAML/env config, systemd units
├── models/             # ONNX / Vosk / wakeword model files (gitignored, downloaded)
├── assets/
├── logs/
└── docker/             # optional containerized dev of core+frontend
```

## Target platform

- Raspberry Pi 4 (4GB / 8GB), Raspberry Pi OS (64-bit, Bookworm)
- Python 3.11+, Node 20+ (build frontend on Pi or cross-build)
- Peripherals: Pi Camera v2/HQ, 2× servo (pan/tilt), 0.96" I2C OLED, WS2812B
  strip, capacitive touch sensor, USB mic

## Status

**Milestone 1 complete** — backend + dashboard skeleton on mock hardware.

- `core` FastAPI service: REST + WebSocket, SQLite (seeded), 1 Hz system sampler,
  in-process bus, mock hardware behind the HAL seam. 5 smoke tests pass.
- React dashboard: live Home tiles, Notes (CRUD + search), Settings editor,
  Hardware test page (servo/LED/OLED). Backend serves the built bundle.

Run it:

```bash
make setup            # venv + backend deps (mock hardware)
make frontend-install
make frontend-build   # -> frontend/dist
make backend          # http://localhost:8000
# or dev mode with hot reload: `make backend` + `make frontend-dev` (:5173)
```

Next: **Milestone 2 — camera face-tracking** (vision process, MediaPipe, servo
arbiter + PID). See [docs/05-milestone-1.md](docs/05-milestone-1.md#exit-milestone-2).
