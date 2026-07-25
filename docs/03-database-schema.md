# 03 — Database Schema (SQLite)

- Engine: SQLite, **WAL** mode, `core` is the **sole writer** (D4).
- ORM: SQLAlchemy 2.x + Alembic migrations.
- All timestamps stored UTC (`TEXT` ISO-8601 or `INTEGER` epoch — using ISO-8601
  TEXT for readability). Display TZ is a `settings` value.
- High-frequency signals (face error, servo pos, live CPU) are **not** stored —
  they live in the Redis state cache. The DB holds durable records + config.

## Tables

### `users`
Multi-user is Phase 3, but keep the table so foreign keys exist from day one.
| col | type | notes |
|-----|------|-------|
| id | INTEGER PK | |
| name | TEXT | |
| is_default | BOOLEAN | single default user for v1 |
| created_at | TEXT | |

### `settings`
The single control surface (D7). Key/value with type + namespace.
| col | type | notes |
|-----|------|-------|
| key | TEXT PK | e.g. `camera.fps`, `servo.pid.pan.kp`, `water.goal_ml` |
| value | TEXT | JSON-encoded |
| type | TEXT | `int`/`float`/`bool`/`str`/`json` (for UI rendering) |
| namespace | TEXT | `camera`/`voice`/`water`/`servo`/`led`/`system` |
| updated_at | TEXT | |

Change → `core` publishes `event.settings.changed` for hot-reload.

### `notes`
| col | type | notes |
|-----|------|-------|
| id | INTEGER PK | |
| user_id | FK users | |
| title | TEXT | auto or from voice |
| body | TEXT | |
| tags | TEXT | JSON array |
| source | TEXT | `voice`/`dashboard` |
| created_at / updated_at | TEXT | |

FTS: `notes_fts` virtual table (FTS5) mirrors title+body for search.

### `calendar_events`
Cache of synced Google events (source of truth is Google).
| col | type | notes |
|-----|------|-------|
| id | INTEGER PK | |
| external_id | TEXT UNIQUE | Google event id |
| calendar_id | TEXT | which calendar |
| title | TEXT | |
| start_utc / end_utc | TEXT | |
| location | TEXT | |
| status | TEXT | confirmed/tentative/cancelled |
| synced_at | TEXT | |

### `water_logs`
One row per detected sip/drink event.
| col | type | notes |
|-----|------|-------|
| id | INTEGER PK | |
| user_id | FK | |
| detected_at | TEXT | |
| duration_s | REAL | drinking motion length |
| container | TEXT | bottle/glass/cup |
| est_intake_ml | INTEGER | from container size setting × heuristic |
| confidence | REAL | model confidence |

Daily/weekly/monthly rollups computed on read (or a `water_daily` summary table
if perf needs it later).

### `voice_commands`
| col | type | notes |
|-----|------|-------|
| id | INTEGER PK | |
| transcript | TEXT | |
| intent | TEXT | matched intent name (or `llm_fallback`) |
| slots | TEXT | JSON |
| confidence | REAL | |
| handled | BOOLEAN | did an action run |
| created_at | TEXT | |

### `command_bindings`
User-defined "trigger → action" table (PRD feature F).
| col | type | notes |
|-----|------|-------|
| id | INTEGER PK | |
| phrase | TEXT | e.g. "start meeting mode" |
| intent | TEXT | canonical intent |
| action | TEXT | action id the core executes |
| params | TEXT | JSON |
| enabled | BOOLEAN | |

### `hardware_config`
Wiring/calibration that isn't a "soft" setting (pins, servo limits, offsets).
| col | type | notes |
|-----|------|-------|
| id | INTEGER PK | |
| device | TEXT | `servo_pan`/`servo_tilt`/`oled`/`led`/`touch` |
| params | TEXT | JSON (pin, i2c_addr, min/max angle, offset, invert, led_count) |

### `activity_logs`
Presence transitions, meeting-mode on/off, reminders fired — the analytics feed.
| col | type | notes |
|-----|------|-------|
| id | INTEGER PK | |
| type | TEXT | `presence`/`meeting`/`reminder`/`system` |
| detail | TEXT | JSON |
| created_at | TEXT | |

### `ai_history`
Record of any AI/LLM invocation (privacy-transparency: user can audit).
| col | type | notes |
|-----|------|-------|
| id | INTEGER PK | |
| kind | TEXT | `llm`/`stt`/`vision` |
| prompt | TEXT | redactable |
| response | TEXT | |
| model | TEXT | |
| local | BOOLEAN | true if on-device |
| tokens / latency_ms | INTEGER | |
| created_at | TEXT | |

## What lives where

| Data | Store |
|------|-------|
| Notes, water logs, events, settings, bindings, activity, ai history | SQLite |
| Latest CPU/temp/RAM, presence, servo angles, camera fps, service heartbeats | Redis `state:*` (ephemeral) |
| Frames, audio | never persisted (privacy) |
| Models | `models/` on disk (downloaded, gitignored) |
