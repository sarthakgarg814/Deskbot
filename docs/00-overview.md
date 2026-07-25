# 00 — Overview & Decisions

## Design principles (from the PRD, made concrete)

| Principle | What it means in the code |
|-----------|---------------------------|
| Privacy first | No audio/video/frames leave the device. Cloud calls (calendar, optional LLM) are opt-in and logged. |
| Local AI first | Deterministic methods before ML. ML models run on-device via ONNX / Vosk / MediaPipe. |
| Cloud optional | The whole system runs with WiFi off, minus calendar sync and optional LLM. |
| Modular | Four independent OS processes, each restartable, communicating over a message bus. |
| Offline friendly | Frontend served locally, all data in local SQLite, models pre-downloaded. |
| Easy configuration | Every tunable lives in the DB `settings` table and is editable from the dashboard. |
| Extensible | New voice intents, new dashboard screens, new services plug in via the bus + registry. |

## The four crux decisions

These shape the whole codebase. Each is a **decision you can veto now** — cheap to
change on paper, expensive later.

### D1 — Multi-process architecture
The Pi 4 has 4 cores, but Python's GIL means one CPU-bound loop (face detection)
would starve everything else in a single process. We run **four OS processes**,
each managed by `systemd`:

- **`core`** — FastAPI, WebSocket, SQLite (sole writer), scheduler, reminder
  engine, calendar sync, notes, serves the React dashboard. The coordinator.
- **`vision`** — camera capture, face detection, presence, periodic water
  detection. CPU-heavy, isolated.
- **`hardware`** — OLED render loop, LED animations, **servo driver + arbiter**,
  touch polling, hardware monitor. Sole owner of GPIO/I2C/PWM.
- **`voice`** — wake word (always on), STT (on demand), intent matching.

**Trade-off:** more moving parts and an IPC bus, vs. clean isolation, independent
restarts, and no GIL contention. For realtime robotics on a Pi this is the right
call.

### D2 — Single owner for the servos (arbiter pattern)
Two subsystems want to move the servos: face-tracking (in `vision`) and idle
animations / manual test (in `hardware`). **Only `hardware` ever writes PWM.**
Vision publishes a *desired target* (face error or absolute angle); the
**servo arbiter** in `hardware` picks the current owner by priority and runs the
PID + smoothing loop. See [02 — hardware layer](02-hardware-layer.md#servo-arbiter).

Priority (high→low): `manual_test` → `meeting_center` → `face_tracking` → `idle_scan`.

### D3 — Redis as internal bus + live-state cache
High-frequency signals (face error, servo position, presence, CPU/temp) update
20–30×/sec. Those don't belong in SQLite. **Redis** provides:
- **Pub/sub** between the four processes (topics in [04 — API contract](04-api-contract.md#redis-topics)).
- A **latest-state cache** (`state:*` keys) the `core` process reads to answer
  `GET /system`, `/camera/status`, etc., and to push over the dashboard WebSocket.

MQTT (already on the PRD's Phase-2 roadmap) is reserved for **external**
integrations (Home Assistant). Redis stays internal.

**Trade-off:** one extra daemon (`redis-server`, ~few MB RAM on Pi) vs. hand-rolled
IPC. Redis is battle-tested on ARM and gives us the state cache for free.

> **Decided:** Milestone 1 runs `core` standalone with an **in-process async
> event bus**; Redis is introduced when `vision`/`voice` come online. The seam
> (`common/bus.py`) is identical either way, so this is a zero-API-change swap.

### D4 — SQLite with a single writer
`core` is the only process that writes SQLite (WAL mode). `vision`/`voice`/
`hardware` **publish events**; `core` subscribes and persists (water logs, voice
commands, activity). This eliminates multi-process write locking and keeps the
data model in one place.

## Decision log

| ID | Decision | Status | Alternatives considered |
|----|----------|--------|-------------------------|
| D1 | Four-process architecture | Proposed | Single asyncio app; process-per-feature |
| D2 | Servo arbiter in `hardware`, vision publishes targets | Proposed | Vision drives servos directly |
| D3 | Redis internal bus + state cache — **in-process bus for M1, Redis when vision lands** | **Accepted** | MQTT; ZeroMQ; SQLite polling |
| D4 | Single SQLite writer (`core`) | Proposed | Multi-writer WAL; Postgres |
| D5 | Frontend built static, served by `core` at `deskbot.local` — **built on laptop, copied to Pi** | **Accepted** | Build on Pi; separate node server |
| D6 | **pigpio (via gpiozero) for direct-GPIO servo PWM** | **Accepted** | RPi.GPIO software PWM; PCA9685 I2C driver (kept as optional backend behind same interface) |
| D7 | Config lives in DB `settings`, mirrored to `config/*.yaml` defaults | Proposed | Pure file config |

Update this table as decisions are accepted/changed. "Proposed" → "Accepted"
after your review. D1/D2/D4/D7 still want an explicit thumbs-up.

## Open questions for you

Resolved: ~~Bus for M1~~ (in-process, D3), ~~servo driver~~ (pigpio direct GPIO,
D6), ~~frontend build~~ (laptop → copy, D5).

Still open (none block starting Milestone 1 — they land in later milestones):

1. **NeoPixel power:** `rpi_ws281x` needs root or SPI/DMA. Are the LEDs on GPIO18
   (PWM) or driven over SPI? Affects whether `hardware` runs as root. *(M2/M3)*
2. **Wake word engine:** OpenWakeWord (fully open, no key) vs. Porcupine (needs a
   free access key, better accuracy). PRD lists both. *(Voice milestone)*
3. **Google Calendar OAuth on a headless-ish Pi:** device-flow / one-time browser
   auth on the dashboard? Confirm Google (vs. CalDAV/ICS) for v1. *(Productivity milestone)*
