import { useEffect, useState } from "react";
import { api, type ServoState } from "../lib/api";
import { useTopic } from "../lib/ws";

const LED_STATES = ["idle", "listening", "thinking", "working", "reminder", "meeting", "error", "off"];

export default function Hardware() {
  const [pan, setPan] = useState(0);
  const [tilt, setTilt] = useState(0);
  const [led, setLed] = useState("idle");
  const [oled, setOled] = useState<string[]>([]);

  const liveServo = useTopic<ServoState>("servo");
  const [servoSeed, setServoSeed] = useState<ServoState | null>(null);
  const servo = liveServo ?? servoSeed;

  const refreshOled = async () => setOled((await api.oledPreview()).lines);
  useEffect(() => {
    refreshOled();
    api.servoStatus().then(setServoSeed).catch(() => {});
  }, []);

  return (
    <div className="max-w-2xl space-y-6">
      <h1 className="text-lg font-semibold">Hardware</h1>
      <p className="text-sm text-neutral-500 -mt-4">
        Mock backend on this machine — calls are logged and reflected here. On the
        Pi these drive the real servos, LEDs, and OLED.
      </p>

      {/* Servo */}
      <section className="rounded-xl border border-neutral-800 p-5">
        <h2 className="font-medium mb-3">Servo test</h2>
        <div className="space-y-3">
          {[
            { label: "Pan", val: pan, set: setPan },
            { label: "Tilt", val: tilt, set: setTilt },
          ].map((a) => (
            <div key={a.label} className="flex items-center gap-3">
              <span className="w-10 text-sm text-neutral-400">{a.label}</span>
              <input
                type="range"
                min={-90}
                max={90}
                value={a.val}
                onChange={(e) => a.set(Number(e.target.value))}
                className="flex-1 accent-led-idle"
              />
              <span className="w-12 text-right text-sm tabular-nums">{a.val}°</span>
            </div>
          ))}
          <button
            onClick={() => api.servoTest(pan, tilt)}
            className="rounded-md bg-neutral-800 px-4 py-2 text-sm hover:bg-neutral-700"
          >
            Move
          </button>

          {/* live position from the hardware arbiter (updates while face tracking) */}
          <div className="mt-2 flex items-center gap-4 rounded-md bg-neutral-900/60 px-3 py-2 text-sm tabular-nums">
            <span className="text-neutral-500">live</span>
            <span>pan <span className="text-neutral-200">{servo ? servo.pan.toFixed(0) : "—"}°</span></span>
            <span>tilt <span className="text-neutral-200">{servo ? servo.tilt.toFixed(0) : "—"}°</span></span>
            <span className="ml-auto text-xs text-neutral-500">
              driver: {servo?.owner ?? "offline"}
            </span>
          </div>
        </div>
      </section>

      {/* LED */}
      <section className="rounded-xl border border-neutral-800 p-5">
        <h2 className="font-medium mb-3">LED state</h2>
        <div className="flex flex-wrap gap-2">
          {LED_STATES.map((s) => (
            <button
              key={s}
              onClick={() => {
                setLed(s);
                api.ledState(s);
              }}
              className={`rounded-md px-3 py-1.5 text-sm ${
                led === s ? "bg-led-idle text-white" : "bg-neutral-800 text-neutral-300 hover:bg-neutral-700"
              }`}
            >
              {s}
            </button>
          ))}
        </div>
      </section>

      {/* OLED */}
      <section className="rounded-xl border border-neutral-800 p-5">
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-medium">OLED preview</h2>
          <button onClick={refreshOled} className="text-xs text-neutral-500 hover:text-neutral-300">
            refresh
          </button>
        </div>
        <div className="rounded-md bg-black border border-neutral-700 p-4 font-mono text-sm text-cyan-300 aspect-[2/1] max-w-xs">
          {oled.length ? oled.map((l, i) => <div key={i}>{l}</div>) : <span className="text-neutral-600">(blank)</span>}
        </div>
      </section>

      <DisplayConfig />
    </div>
  );
}

const EMOTIONS = ["auto", "happy", "neutral", "sad", "angry", "surprised", "sleepy"];

function DisplayConfig() {
  const [saved, setSaved] = useState<Record<string, unknown>>({});
  const [dirty, setDirty] = useState<Record<string, unknown>>({});
  const [saving, setSaving] = useState(false);

  const load = () =>
    api.listSettings("oled").then((rows) =>
      setSaved(Object.fromEntries(rows.map((r) => [r.key, r.value]))),
    );
  useEffect(() => { load(); }, []);

  const upd = (key: string, value: unknown) => setDirty((d) => ({ ...d, [key]: value }));
  const val = (key: string, def: unknown) => (key in dirty ? dirty[key] : saved[key] ?? def);
  const nDirty = Object.keys(dirty).length;

  const save = async () => {
    setSaving(true);
    try {
      await api.updateSettings(Object.entries(dirty).map(([key, value]) => ({ key, value })));
      await load();
      setDirty({});
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="rounded-xl border border-neutral-800 p-5">
      <div className="flex items-center justify-between mb-3">
        <h2 className="font-medium">Display (OLED)</h2>
        <button
          onClick={save}
          disabled={nDirty === 0 || saving}
          className="rounded-md bg-led-idle px-4 py-1.5 text-sm font-medium text-white disabled:opacity-40"
        >
          {saving ? "Saving…" : `Save${nDirty ? ` (${nDirty})` : ""}`}
        </button>
      </div>
      <div className="space-y-3 text-sm">
        <div className="flex items-center justify-between">
          <span className="text-neutral-300">Mode</span>
          <select value={String(val("oled.mode", "eyes"))} onChange={(e) => upd("oled.mode", e.target.value)}
                  className="rounded-md bg-neutral-900 border border-neutral-800 px-2 py-1">
            <option value="eyes">eyes</option>
            <option value="status">stats screen</option>
          </select>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-neutral-300">Emotion</span>
          <select value={String(val("oled.emotion", "auto"))} onChange={(e) => upd("oled.emotion", e.target.value)}
                  className="rounded-md bg-neutral-900 border border-neutral-800 px-2 py-1">
            {EMOTIONS.map((e) => <option key={e} value={e}>{e}</option>)}
          </select>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-neutral-300">Flash stats when present</span>
          <input type="checkbox" checked={val("oled.stats_enabled", true) !== false}
                 onChange={(e) => upd("oled.stats_enabled", e.target.checked)}
                 className="h-4 w-4 accent-led-idle" />
        </div>
        <div className="flex items-center justify-between">
          <span className="text-neutral-300">…every (sec)</span>
          <input type="number" min={5} value={Number(val("oled.stats_every_s", 30))}
                 onChange={(e) => upd("oled.stats_every_s", parseInt(e.target.value || "30", 10))}
                 className="w-20 rounded-md bg-neutral-900 border border-neutral-800 px-2 py-1 text-right" />
        </div>
        <div className="flex items-center justify-between">
          <span className="text-neutral-300">…for (sec)</span>
          <input type="number" min={1} value={Number(val("oled.stats_dwell_s", 4))}
                 onChange={(e) => upd("oled.stats_dwell_s", parseInt(e.target.value || "4", 10))}
                 className="w-20 rounded-md bg-neutral-900 border border-neutral-800 px-2 py-1 text-right" />
        </div>
      </div>
    </section>
  );
}
