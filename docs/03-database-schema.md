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
| key | TEXT PK | e.g. `camera.fps`, `servo.pid.pan.kp`, `mood.sample_interval_s` |
| value | TEXT | JSON-encoded |
| type | TEXT | `int`/`float`/`bool`/`str`/`json` (for UI rendering) |
| namespace | TEXT | `camera`/`voice`/`mood`/`servo`/`led`/`system` |
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

### `mood_logs`
One row per mood sample (every N seconds while a face is present). **Label only —
no image is ever stored** (privacy). Sensitive data; user can disable/clear from
the dashboard.
| col | type | notes |
|-----|------|-------|
| id | INTEGER PK | |
| user_id | FK | |
| detected_at | TEXT | |
| mood | TEXT | `happy`/`neutral`/`sad`/`stressed`/`surprised` (final set TBD) |
| confidence | REAL | model confidence |
| present | BOOLEAN | face present at sample time |

Daily/weekly/monthly rollups (dominant mood, distribution, timeline) computed on
read, or a `mood_daily` summary table if perf needs it later.

### `voice_commands`
| col | type | notes |
|-----|------|-------|
| id | INTEGER PK | |
| transcript | TEXT | |
| intent | TEXT | matched intent name (or `unhandled`) |
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
Audit trail of any on-device AI inference (privacy-transparency: user can audit).
No LLM in current scope; table stays so a future cloud LLM would be logged here too.
| col | type | notes |
|-----|------|-------|
| id | INTEGER PK | |
| kind | TEXT | `stt`/`vision`/`mood` |
| input | TEXT | redactable summary (e.g. transcript); never raw frames/audio |
| output | TEXT | label / result |
| model | TEXT | |
| local | BOOLEAN | true if on-device (always true for now) |
| latency_ms | INTEGER | |
| created_at | TEXT | |

## What lives where

| Data | Store |
|------|-------|
| Notes, mood logs, events, settings, bindings, activity, ai history | SQLite |
| Latest CPU/temp/RAM, presence, servo angles, camera fps, service heartbeats | Redis `state:*` (ephemeral) |
| Frames, audio | never persisted (privacy) |
| Models | `models/` on disk (downloaded, gitignored) |
