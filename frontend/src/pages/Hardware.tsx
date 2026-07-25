import { useEffect, useState } from "react";
import { api } from "../lib/api";

const LED_STATES = ["idle", "listening", "thinking", "working", "reminder", "meeting", "error", "off"];

export default function Hardware() {
  const [pan, setPan] = useState(0);
  const [tilt, setTilt] = useState(0);
  const [led, setLed] = useState("idle");
  const [oled, setOled] = useState<string[]>([]);

  const refreshOled = async () => setOled((await api.oledPreview()).lines);
  useEffect(() => {
    refreshOled();
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
    </div>
  );
}
