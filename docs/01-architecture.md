# 01 — Architecture

## System diagram

```
                          Browser  →  http://deskbot.local
                                          │  (static React, WS)
                                          ▼
┌─────────────────────────────────────────────────────────────────┐
│  core  (FastAPI, single process)                                 │
│  REST + WebSocket · Scheduler(APScheduler) · Reminder engine     │
│  Calendar sync · Notes · SQLite (SOLE WRITER, WAL)               │
└───────────────┬───────────────────────────────┬─────────────────┘
                │  publish/subscribe + state cache (Redis)          
        ┌───────┴────────┬──────────────────────┬──────────────────┐
        ▼                ▼                      ▼                  ▼
┌──────────────┐ ┌──────────────┐      ┌──────────────┐   ┌──────────────┐
│   vision     │ │    voice     │      │  hardware    │   │ (redis-server)│
│ camera loop  │ │ wake word    │      │ OLED loop    │   │  bus + cache  │
│ face detect  │ │ STT          │      │ LED loop     │   └──────────────┘
│ presence     │ │ intent match │      │ SERVO ARBITER│
│ water detect │ │              │      │ + PID        │
│              │ │              │      │ touch poll   │
│ publishes    │ │ publishes    │      │ hw monitor   │
│ targets      │ │ intents      │      │ owns GPIO    │
└──────────────┘ └──────────────┘      └──────────────┘
```

Only `hardware` touches GPIO/I2C/PWM. Only `core` writes SQLite. Everything
between processes flows through Redis.

## Process responsibilities

### `core` (backend/core/)
- Serves REST API ([04](04-api-contract.md)) and the static React bundle.
- Owns the WebSocket: subscribes to Redis `state:*` / event topics and fans out
  to browsers.
- Owns SQLite: all writes. Subscribes to `event.*` topics and persists.
- Runs **APScheduler** jobs: calendar sync (15 min), water-reminder check, daily
  rollups, hardware-monitor heartbeat.
- **Reminder engine**: turns schedule/state changes into commands (LED yellow,
  OLED reminder, future voice) by publishing to `cmd.*` topics.
- No realtime hard-deadline work → asyncio is fine here.

### `vision` (backend/vision/)
- Single capture loop at target 15–20 FPS (OpenCV `VideoCapture` / picamera2).
- **Face detection** (MediaPipe Face Detection) → compute normalized error from
  frame center → publish `cmd.servo.target` at 20–30 Hz (throttled, dead-zoned).
- **Presence** state machine (`present`/`away`/`unknown`) → publish
  `event.presence` + cache `state:presence`.
- **Water detection** runs on a slow cadence (every N seconds, not per frame):
  YOLOv8-nano (ONNX Runtime) for bottle/cup + MediaPipe Pose for drinking motion
  → publish `event.water.sip`.
- Publishes `state:camera` (fps, latency, tracking mode, last face bbox).
- No servo writes — only targets.

### `hardware` (backend/hardware/)
- **Servo arbiter + PID** loop at 20–30 Hz (the only servo writer). Consumes
  `cmd.servo.*`, applies ownership priority, smoothing, limits; publishes
  `state:servo` (current angles, owner).
- **OLED renderer**: 6-screen carousel (luma.oled). Subscribes to `state:*` and
  `cmd.oled.*`; touch events change screens.
- **LED controller**: WS2812B state machine (rpi_ws281x). Subscribes to
  `cmd.led.state`.
- **Touch sensor**: poll/interrupt → publish `event.touch` (tap/double/long/vlong).
- **Hardware monitor**: CPU %, RAM, temp, storage → publish `state:system` at 1 Hz.
- Runs closest to hardware; may need root (LEDs) — see deployment.

### `voice` (backend/voice/)
- Always-on **wake word** (OpenWakeWord / Porcupine) → on trigger, publish
  `event.voice.wake` and start capture.
- **STT** (Whisper-tiny / Vosk) transcribes the utterance.
- **Intent engine**: rule-based matcher first (configurable command table from
  DB); falls back to optional LLM only for open-ended input. Publishes
  `event.voice.intent` with `{intent, slots, transcript, confidence}`.
- `core` maps intents → actions (create note, start meeting mode, center camera…).

## Concurrency model per process

| Process | Model | Why |
|---------|-------|-----|
| core | asyncio (uvicorn) + APScheduler threadpool | I/O bound; no hard deadlines |
| vision | one capture thread + inference in-loop; publisher async | CPU bound, keep it tight |
| hardware | dedicated servo thread (fixed-rate) + OLED thread + async subscriber | servo needs steady cadence |
| voice | audio callback thread + worker | audio is realtime-ish |

## Message bus contract (Redis)

Two mechanisms:
- **Pub/sub topics** for events/commands (fire-and-forget).
- **Key cache** `state:*` for "latest value" reads (`SET` with short TTL, `GET`
  by core).

Topic + key catalog lives in [04 — API contract](04-api-contract.md#redis-topics)
so the wire format has one source of truth. `common/bus.py` wraps both; swapping
Redis for an in-process implementation only touches that file (see D3).

## Configuration flow (D7)

```
config/defaults.yaml  ──seed──▶  SQLite `settings`  ◀──edit── Dashboard
                                        │
                    each service reads its namespace on start
                    + subscribes to `event.settings.changed` for hot-reload
```

Tunables (PID gains, FPS, wake word, reminder interval, water goal, servo
offsets) are DB rows so the dashboard is the single control surface. Defaults
ship in `config/defaults.yaml` for first boot / factory reset.

## Deployment (systemd)

Four units (+ redis) in `config/systemd/`:

```
deskbot-redis.service      (or system redis-server)
deskbot-core.service       After=redis, network-online
deskbot-hardware.service   After=redis         (may need User=root for LEDs)
deskbot-vision.service     After=redis
deskbot-voice.service      After=redis
deskbot.target             wants all of the above
```

- `pigpiod` must run for jitter-free servo PWM (enable its service).
- mDNS via `avahi-daemon` publishes `deskbot.local`.
- Boot target `<30s`: services start in parallel; `core` serves a "warming up"
  page until vision/hardware report ready over the bus.
- Watchdog: `core` tracks per-service heartbeats on `state:heartbeat:*`; a missed
  heartbeat → dashboard shows the service down and systemd restarts it
  (`Restart=on-failure`).

## Failure & degradation

| Failure | Behavior |
|---------|----------|
| `vision` crashes | servos hold last pos → arbiter falls back to idle after timeout; dashboard shows camera offline |
| `hardware` crashes | core + dashboard keep working; systemd restarts; LEDs/OLED dark meanwhile |
| Redis down | services retry with backoff; core serves cached DB data; no live updates |
| WiFi down | everything local keeps working; calendar sync + optional LLM skipped |
| Camera unplugged | vision reports error state, publishes no targets, arbiter idles |

## Why not the alternatives (quick)

- **Single asyncio app:** GIL — one busy vision loop stalls the web server and
  servo cadence. Rejected.
- **ZeroMQ:** great perf, but we'd hand-roll the state cache Redis gives us.
- **MQTT internal:** fine, but Redis' key cache is more convenient for the
  dashboard's "current status" reads. MQTT kept for external (Phase 2).
