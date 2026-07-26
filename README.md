# Peekabot AI

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
| 06 | [Operations](docs/06-operations.md) | **As-built**: services, deploy, full settings reference, troubleshooting playbook |

## Repository map

```
peekabot/
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

## Status — face-follow working on real hardware 🤖

- ✅ **M1** — `core` (FastAPI + WebSocket + SQLite) + React dashboard, on the bus.
- ✅ **M2a** — `vision`: Pi camera + OpenCV **YuNet** face detection at ~17 FPS,
  CPU-tuned (adaptive rate), privacy-gated MJPEG preview.
- ✅ **M2b** — `hardware`: servo **arbiter + position-step control** driving
  pan/tilt via **hardware PWM** (jitter-free), with direction/offset config,
  return-to-home when you step away, and a **tracking on/off** toggle.
- ⬜ **Next: OLED** status display (0.96" I2C), then LEDs, voice, calendar, mood.

Runs on Raspberry Pi OS **Trixie** (64-bit, Python 3.13). Full operator guide,
config reference, and troubleshooting: **[docs/06-operations.md](docs/06-operations.md)**.

### Run locally (mock hardware, no Pi)
```bash
make setup && make frontend-install && make frontend-build && make backend
# http://localhost:8000
```

### Install on a Raspberry Pi — one line
On a fresh Raspberry Pi OS (Trixie, 64-bit), SSH in and run:
```bash
curl -fsSL https://raw.githubusercontent.com/sarthakgarg814/Peekabot/main/install.sh | bash
```
Installs everything (deps, Redis, camera, GPIO, builds the dashboard, all three
services), then it's live at **http://peekabot.local:8000**. Default login password
is **`peekabot`** — change it under **Account**. (A reboot is needed once for the
hardware-PWM overlay.)

### Dev deploy (from your laptop)
```bash
./scripts/deploy-to-pi.sh peekabot@peekabot.local     # build + rsync
# first time: ./scripts/setup-pi.sh, setup-vision-pi.sh, setup-hardware-pi.sh [--real]
```

**Auth:** the dashboard + API are password-protected (default `peekabot`). See
[docs/06-operations.md](docs/06-operations.md#authentication). Wiring:
[docs/06-operations.md#wiring](docs/06-operations.md#wiring).
