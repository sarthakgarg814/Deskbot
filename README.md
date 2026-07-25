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
│   ├── vision/         #   camera, face detection, presence, water detection
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

Design phase. No feature code yet — see [Milestone 1](docs/05-milestone-1.md) for
the first vertical slice (backend + dashboard on stubbed hardware).
