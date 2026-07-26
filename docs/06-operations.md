# 06 — Operations Guide (as-built)

How the running DeskBot is put together, how to deploy it, every tunable, and a
troubleshooting playbook for the issues we actually hit. This is the "as-built"
companion to the design docs (00–05).

## What's running

Four processes on the Pi (Raspberry Pi OS **Trixie**, 64-bit, Python 3.13),
coordinated over **Redis**:

| Process | systemd unit | Owns | Talks via |
|---------|-------------|------|-----------|
| **core** | `deskbot-core` | FastAPI + WebSocket, SQLite (sole writer), scheduler, serves the dashboard | REST/WS to browser; publishes `cmd.*`, reads `state:*` |
| **vision** | `deskbot-vision` | Pi camera, YuNet face detection, presence, MJPEG preview | publishes `cmd.servo.target`, `state:camera`, `presence` |
| **hardware** | `deskbot-hardware` | the servos + OLED (sole GPIO/I2C owner) — arbiter + hardware PWM + status screen | subscribes `cmd.servo.*`, publishes `state:servo`, `state:oled` |
| redis | `redis-server` | the bus + state cache | — |

Design rules that matter operationally:
- **Only `hardware` touches the servos** (D2). `core` never opens GPIO — it
  publishes commands. This is why `hardware_backend: real` is safe with core running.
- **Only `core` writes SQLite** (D4). Other processes publish events.
- **Redis is the bus** (D3): `cmd.*` = commands, `state:*` = latest-value cache.

## The stack we ended up on (and why)

| Concern | Choice | Why not the "obvious" option |
|---------|--------|------------------------------|
| OS | Raspberry Pi OS Trixie 64-bit Lite | current release; Python 3.13 |
| Servo signal | **hardware PWM** on GPIO 12/13 via `rpi-hardware-pwm` | software PWM (gpiozero/lgpio) jitters; **pigpio was removed in Trixie** |
| Face detection | **OpenCV YuNet** | **MediaPipe doesn't support Python 3.13** |
| Camera capture | `picamera2` | fine on 3.13 (only MediaPipe wasn't) |
| Tracking control | **position-step** (move-and-settle) | velocity control hunts — camera rides on the servo (feedback lag) |
| Bus | Redis | needed once vision/hardware became separate processes |

See the decision log in [00-overview.md](00-overview.md#decision-log) (D3, D6, D9,
D10, D11).

## Deploy workflow

Frontend is **built on the laptop** and rsynced (D5) — the Pi never runs npm.

```bash
# One-time on the Pi (in order):
./scripts/setup-pi.sh              # core: venv + deps + deskbot-core service
./scripts/setup-vision-pi.sh       # redis + camera/opencv + deskbot-vision, flips bus->redis
./scripts/setup-hardware-pi.sh     # gpiozero/lgpio + deskbot-hardware (mock servo)
./scripts/setup-hardware-pi.sh --real   # once servos are wired: hardware PWM + real servo

# Every change after that:
./scripts/deploy-to-pi.sh deskbot@deskbot.local      # laptop: vite build + rsync
ssh deskbot@deskbot.local 'sudo systemctl restart deskbot-core deskbot-vision deskbot-hardware'
```

The Pi runs an **editable install** (`pip install -e backend`), so a redeploy +
service restart picks up code changes with no reinstall.

Dashboard: **http://deskbot.local:8000**

## Configuration model

Three layers, lowest to highest precedence:

1. **`config/defaults.yaml`** — `runtime:` (ports, pins, backends) read before the
   DB exists, and `settings:` seeds for first boot.
2. **`config/local.yaml`** — per-machine `runtime:` overrides (gitignored, **not**
   rsynced). The Pi sets `bus_backend: redis` and `hardware_backend: real` here so
   a redeploy never clobbers them.
3. **DB `settings` table** — the live-tunable values. **This is the source of
   truth at runtime**, edited from the dashboard Settings page.

> **Seeding is insert-only.** `defaults.yaml` seeds a setting *once*; changing a
> default later does **not** update an existing DB row (so your edits survive).
> To change a value on a running Pi, edit it in **Settings**, not the YAML. (This
> is what caused the "servo frozen" bug — a stale `kp: 0.08` from the very first
> seed.)

**Live tuning path:** edit in Settings → `core` writes the DB + publishes
`event.settings.changed` → `core` re-mirrors to `state:vision.config` /
`state:servo.config` → vision/hardware poll (~2 s) and apply. No restart.

## Settings reference

### camera (vision service)
| Key | Default | Effect |
|-----|---------|--------|
| `camera.tracking_enabled` | true | **off = servos freeze** (no follow, no home-drift). Manual/Center still work. |
| `camera.preview_enabled` | false | MJPEG video stream on port 8090 (privacy: off by default) |
| `camera.track_fps` | 10 | processing FPS while a face is present (CPU vs responsiveness) |
| `camera.idle_fps` | 2 | processing FPS when away (idle CPU saving) |
| `camera.detect_width` | 256 | detection downscale px (smaller = less CPU, less range) |

### servo (hardware service)
| Key | Default | Effect |
|-----|---------|--------|
| `servo.track_gain` | 0.5 | fraction of the geometric error corrected per frame (0.5 = halve error/frame). Higher = snappier, may overshoot |
| `servo.fov_pan` / `servo.fov_tilt` | 54 / 41 | camera field-of-view (deg). Sets how many degrees to move per unit error. Too high → overshoot |
| `servo.deadzone` | 0.04 | ignore error smaller than this (settle). Raise if a servo micro-jitters at rest |
| `servo.max_speed` | 120 | slew rate (deg/s) — how fast it physically moves to the target |
| `servo.limit_deg` | 80 | ± angle clamp |
| `servo.pan.invert` / `servo.tilt.invert` | false | flip if a servo moves the WRONG way (camera-on-gimbal usually needs true) |
| `servo.pan.offset_deg` / `servo.tilt.offset_deg` | 0 | mechanical center trim |
| `servo.recenter_after_s` | 3.0 | face lost this long → drift home (only when tracking enabled) |

### oled (hardware service)
| Key | Default | Effect |
|-----|---------|--------|
| `oled.mode` | eyes | `eyes` = animated robot eyes; `status` = text (time/CPU/temp/tracking/servo) |
| `oled.emotion` | auto | `auto` = happy when a face is present, sleepy when away (and mood-driven later); or force `happy`/`neutral`/`sad`/`angry`/`surprised`/`sleepy` |

### runtime (config/defaults.yaml or local.yaml)
`hardware_backend` (mock\|real), `bus_backend` (inprocess\|redis), `redis_url`,
`servo_pan_pin` (12), `servo_tilt_pin` (13), `preview_port` (8090),
`vision_track_fps`/`idle_fps`/`detect_width` (startup fallbacks), `frontend_dist`.

## Face-tracking, how it works

1. `vision` detects the face, computes normalized centering error `err_x/err_y`
   in `[-1,1]` (0 = centered), publishes `cmd.servo.target` (mode `error`) at
   `track_fps`.
2. `hardware`'s **arbiter** picks the owner by priority
   (`manual_test > center > face_tracking > idle`), then for a face-tracking
   sample computes an **absolute target**: `target = current + track_gain × err ×
   (FOV/2)`, slews to it (`max_speed`), and **holds** — no continuous motion.
3. Face within `deadzone` → no new target → servo settles.
4. Face gone `recenter_after_s` → drift home (if tracking enabled).
5. `camera.tracking_enabled = false` → vision stops sending targets and the
   arbiter freezes in place.

## Troubleshooting playbook

| Symptom | Cause | Fix |
|---------|-------|-----|
| `apt install pigpio` → no candidate | pigpio removed in Trixie | Use lgpio / hardware PWM (already the design) |
| MediaPipe won't install | no Python 3.13 support | We use OpenCV YuNet instead (D9) |
| Camera preview is **purple** | picamera2 "RGB888" is already BGR; double cvtColor | Fixed — no conversion in `PiCamera2Source` |
| Servo **buzzes/jitters** constantly | software PWM timing wobble | Hardware PWM on 12/13 + `pwm-2chan` overlay + reboot |
| Servo jitters only under load / Pi reboots | 5V brownout from servo current | External 5–6V supply, common ground, or a 470–1000 µF cap |
| Servo **won't move at all** on tracking, manual works | stale seed value (e.g. `kp 0.08`) OR service still on mock | Set the value in Settings; confirm `hw.real` in the hardware log; ensure the service was **restart**ed (not just `enable --now`) |
| Servo moves **opposite** to the face | camera-on-gimbal reverses direction | Flip `servo.pan.invert` / `servo.tilt.invert` |
| Tilt **micro-jogs** at rest | vertical error noisier than deadzone | Raise `servo.deadzone` (0.08–0.10) |
| Servo twitches erratically | loose signal/power jumper | Reseat the connector |
| Tracking **hunts / never settles** | velocity control / lag | Fixed — position-step control (D10); if still, lower `track_gain` |
| Preview enabled but no video | no `<img>` was on the page / stream on :8090 | Fixed — Camera page embeds the stream when preview on |
| Dashboard dot red, "connecting…" | core error on the bus | `journalctl -u deskbot-core -n 30` |

### Handy commands
```bash
journalctl -u deskbot-hardware -f          # watch the arbiter
redis-cli get state:servo                  # current pan/tilt/owner
redis-cli get state:servo.config           # gains the arbiter is using
redis-cli get state:camera                 # fps / present / face err_x,err_y
systemctl is-active deskbot-core deskbot-vision deskbot-hardware redis-server
```

## Status / roadmap

- ✅ **M1** backend + dashboard skeleton
- ✅ **M2a** camera + YuNet face detection (17 FPS, CPU-tuned)
- ✅ **M2b** servo arbiter + hardware-PWM pan/tilt face-follow, tracking toggle,
  return-to-home
- ✅ **OLED** (0.96" I2C SSD1306 @ 0x3C) — **animated robot eyes** (blink, gaze
  toward the face, emotions) or a text status screen, rendered in a dedicated
  ~12 fps thread. Emotion is happy/sleepy on presence today; mood detection will
  drive it later.
- ⬜ **Next:** mood detection (drives the eyes), LEDs (WS2812B), touch sensor +
  screen cycling, voice (wake word + STT), calendar
