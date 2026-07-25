# 04 — API Contract

Three wire surfaces, one source of truth each:
1. **REST** (browser ↔ `core`) — request/response, DB-backed.
2. **WebSocket** (browser ↔ `core`) — live push of `state:*` and events.
3. **Redis topics/keys** (process ↔ process) — the internal bus.

## REST (FastAPI, prefix `/api`)

Matches the PRD §9 list, fleshed out with bodies. All JSON. Errors:
`{ "error": {"code","message"} }` with proper HTTP status.

### System
| Method | Path | Body / returns |
|--------|------|----------------|
| GET | `/api/system` | `{cpu, ram, temp_c, storage, uptime_s, services:{name:up/down}}` (from Redis cache) |

### Camera
| Method | Path | Notes |
|--------|------|-------|
| GET | `/api/camera/status` | `{running, fps, latency_ms, tracking_mode, present, last_face}` |
| POST | `/api/camera/start` | publish `cmd.vision.start` |
| POST | `/api/camera/stop` | publish `cmd.vision.stop` |
| POST | `/api/camera/center` | publish `cmd.servo.center {owner:"api"}` |

### Notes
| Method | Path | Notes |
|--------|------|-------|
| GET | `/api/notes?q=&tag=` | FTS search + filter |
| POST | `/api/notes` | `{title?, body, tags?}` → created note |
| GET | `/api/notes/{id}` | |
| PUT | `/api/notes/{id}` | edit |
| DELETE | `/api/notes/{id}` | |
| GET | `/api/notes/export?fmt=md|txt|json` | export (PRD) |

### Calendar
| GET | `/api/calendar/today` | today's events |
| GET | `/api/calendar/upcoming` | next N |
| POST | `/api/calendar/sync` | force sync now |
| GET/POST | `/api/calendar/auth` | Google OAuth start / callback |

### Voice
| POST | `/api/voice/command` | `{transcript}` → run intent pipeline (also used for text testing) |
| GET | `/api/voice/bindings` / POST/PUT/DELETE | manage `command_bindings` |

### Mood
| GET | `/api/mood/current` | `{mood, confidence, at}` from `state:mood` |
| GET | `/api/mood/today` | `{dominant, distribution:{happy:..,neutral:..}, timeline[]}` |
| GET | `/api/mood/history?range=week|month` | series for the mood graph |
| DELETE | `/api/mood/history` | clear stored mood data (privacy control) |

### Settings & hardware
| GET | `/api/settings?ns=` | key/value list |
| POST | `/api/settings` | `{key,value}[]` → persists + emits `event.settings.changed` |
| POST | `/api/servo/test` | `{pan,tilt}` → `cmd.servo.claim(manual_test)` + target |
| POST | `/api/led/state` | `{state}` → `cmd.led.state` |
| POST | `/api/oled/preview` | returns current framebuffer PNG |
| GET | `/api/logs?service=&level=` | tail logs |

## WebSocket `/ws`

Server→client, JSON envelope `{topic, ts, data}`. Client subscribes with
`{action:"subscribe", topics:[...]}`.

| topic | data | rate |
|-------|------|------|
| `system` | cpu/ram/temp/storage | 1 Hz |
| `camera` | fps/latency/present/last_face | ~5 Hz (throttled) |
| `servo` | pan/tilt/owner | ~5 Hz |
| `presence` | state changes | on change |
| `led` | current state | on change |
| `mood` | current mood label + confidence | on change |
| `voice` | wake/intent/transcript | on event |
| `notes` | created/updated/deleted | on change |
| `service` | heartbeat up/down | on change |

Client→server: `{action:"command", cmd:"camera.center"}` for convenience (maps to
the same handlers as REST). Auth: local-network only for v1; token optional.

## Redis topics

Naming: `cmd.*` = imperative (do this), `event.*` = something happened,
`state:*` = latest-value cache key (not pub/sub).

### Commands (pub/sub)
| topic | payload | producer → consumer |
|-------|---------|---------------------|
| `cmd.servo.target` | `{owner,mode,pan,tilt,ttl_ms}` | vision/core → hardware |
| `cmd.servo.center` | `{owner}` | core/api → hardware |
| `cmd.servo.claim` / `.release` | `{owner}` | core → hardware |
| `cmd.led.state` | `{state, params}` | core → hardware |
| `cmd.oled.screen` | `{index}` or `{cmd:"next"/"prev"}` | core/touch → hardware |
| `cmd.vision.start` / `.stop` | `{}` | core → vision |
| `cmd.voice.listen` | `{}` | core → voice |

### Events (pub/sub)
| topic | payload | producer |
|-------|---------|----------|
| `event.presence` | `{state}` | vision |
| `event.mood` | `{mood,confidence}` | vision |
| `event.touch` | `{gesture}` | hardware |
| `event.voice.wake` | `{}` | voice |
| `event.voice.intent` | `{intent,slots,transcript,confidence}` | voice |
| `event.settings.changed` | `{keys:[...]}` | core |
| `event.service.ready` | `{service}` | each service on boot |

### State cache keys (`SET`, short TTL)
| key | value |
|-----|-------|
| `state:system` | cpu/ram/temp/storage/uptime |
| `state:camera` | fps/latency/tracking_mode/last_face |
| `state:presence` | present/away/unknown |
| `state:mood` | current mood label + confidence |
| `state:servo` | pan/tilt/owner |
| `state:led` | current state |
| `state:heartbeat:<service>` | epoch ts (watchdog reads) |

`core` is the bridge: it subscribes to `event.*`, persists to SQLite, and
rebroadcasts relevant items to the browser WebSocket. It reads `state:*` to
answer REST status calls without hammering the services.
