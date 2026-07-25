# 02 — Hardware Layer (HAL)

Every peripheral sits behind a small Python interface in `backend/hardware/hal/`.
Real drivers implement it; a `mock/` implementation (stdout + in-memory state)
implements the same interface so `core` and the dashboard can be developed and
CI-tested without the Pi. **We develop on the Pi (real drivers), but the seam
stays** — it's how we bench-test one peripheral at a time and how tests run.

```
backend/hardware/hal/
├── base.py         # abstract interfaces (below)
├── servo.py        # pigpio/gpiozero  (+ optional PCA9685 backend)
├── oled.py         # luma.oled
├── led.py          # rpi_ws281x
├── touch.py        # gpiozero button / capacitive
├── camera.py       # picamera2 / OpenCV VideoCapture  (used by vision, not hardware proc)
├── monitor.py      # psutil + vcgencmd
└── mock/           # drop-in fakes for every interface
```

Driver selection is config-driven (`config/defaults.yaml` → `hardware.backend:
real|mock`, per-device overrides), so a single flag runs the whole `hardware`
process against fakes on a laptop.

## Interfaces (contracts)

```python
# base.py — signatures only; async where a render/IO loop is involved

class ServoController(Protocol):
    def set_angles(self, pan_deg: float, tilt_deg: float) -> None: ...
    def get_angles(self) -> tuple[float, float]: ...
    def center(self) -> None: ...
    limits: PanTiltLimits          # min/max/offset/invert per axis

class OledDisplay(Protocol):
    def show(self, screen: RenderedScreen) -> None: ...   # 128x64 framebuffer
    def clear(self) -> None: ...

class LedStrip(Protocol):
    def set_state(self, state: LedState, **kw) -> None: ...  # runs animation loop
    def off(self) -> None: ...

class TouchSensor(Protocol):
    def on_event(self, cb: Callable[[TouchEvent], None]) -> None: ...  # tap/double/long/vlong

class HardwareMonitor(Protocol):
    def sample(self) -> SystemStats: ...   # cpu%, ram, temp_c, storage, uptime

class Camera(Protocol):                    # used by the vision process
    def frames(self) -> Iterator[Frame]: ...
    def set_resolution(self, w: int, h: int) -> None: ...
```

## Driver choices & notes

| Device | Library | Notes / risk |
|--------|---------|--------------|
| Servos (pan/tilt) | `pigpio` via `gpiozero` (pin factory) **or** `PCA9685` I2C | pigpio needs `pigpiod` daemon; gives hardware-timed PWM (no jitter). PCA9685 offloads timing entirely — recommended if you have the board. **Open Q2.** |
| OLED 0.96" I2C | `luma.oled` (SSD1306) | I2C addr usually `0x3C`. Render off-thread, push framebuffer. |
| NeoPixel WS2812B | `rpi_ws281x` (or `adafruit-circuitpython-neopixel`) | Needs root **or** SPI/DMA. Drives on GPIO18 (PWM0) typically. **Open Q3** — decides if `hardware` runs as root. |
| Touch sensor | `gpiozero` Button / capacitive breakout | Debounce + press-duration classification for tap/double/long/vlong. |
| Camera | `picamera2` (CSI) or OpenCV `VideoCapture` | Owned by `vision`, not `hardware`. |
| Monitor | `psutil` + `vcgencmd measure_temp` | Temp via vcgencmd; storage via psutil. |

## Servo arbiter

The heart of D2. Lives in `backend/hardware/servo_arbiter.py`. One fixed-rate
loop (20–30 Hz) is the **only** writer to `ServoController`.

```
inputs (Redis cmd.servo.*):
  cmd.servo.target   {owner, mode:"error"|"angle", pan, tilt, ttl_ms}
  cmd.servo.center   {owner}
  cmd.servo.claim / release {owner}          # manual test / meeting mode

ownership priority (high→low):
  manual_test  >  meeting_center  >  face_tracking  >  idle_scan

loop @ ~25 Hz:
  1. expire stale targets (ttl) — face targets self-expire so a dead vision
     process can't hold the servos hostage
  2. pick highest-priority live owner; if none → idle_scan (slow sweep) after
     grace period
  3. if mode=="error": PID(error)->delta angle ; if "angle": target = angle
  4. slew-rate limit + dead-zone (ignore tiny moves) + clamp to limits+offset
  5. servo.set_angles(...) ; publish state:servo {pan,tilt,owner,mode}
```

- **PID** is per-axis; gains + FPS + dead-zone + max slew come from `settings`
  (dashboard-tunable, hot-reloaded).
- **Dead-zone** satisfies "ignore tiny movements". **Slew limit** gives smooth
  tracking. **Return to center** = vision stops publishing → target expires →
  idle_scan → optional recenter.
- Meeting mode / manual servo test claim ownership so face tracking can't fight
  them.

## Mock behavior (for laptop/CI runs)

- `mock.servo` keeps angles in memory, logs moves, feeds `state:servo`.
- `mock.oled` renders the framebuffer to a PNG in `logs/oled/` (and the dashboard
  "OLED Preview" reads it) — matches PRD's dashboard OLED preview feature.
- `mock.led` prints state transitions / serves a color swatch to the dashboard
  LED test.
- `mock.camera` replays a sample video or a synthetic moving face so vision +
  arbiter can be exercised end-to-end without a Pi camera.

## Permissions / system prep checklist (Pi)

- `sudo systemctl enable pigpiod`
- Enable I2C + SPI in `raspi-config`
- Add user to `gpio`, `i2c`, `spi`, `video` groups
- NeoPixel: either run `hardware` as root or wire on SPI (decide Q3)
- `avahi-daemon` for `deskbot.local`
