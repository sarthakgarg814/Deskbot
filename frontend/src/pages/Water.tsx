import { useEffect, useState } from "react";
import { api, type WaterStatus } from "../lib/api";

function fmt(secs: number): string {
  if (secs <= 0) return "due now";
  const m = Math.floor(secs / 60);
  const s = secs % 60;
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

function Toggle({ label, hint, value, onChange }: {
  label: string; hint?: string; value: boolean; onChange: (v: boolean) => void;
}) {
  return (
    <div className="flex items-center justify-between px-4 py-3">
      <div>
        <div className="text-sm text-neutral-200">{label}</div>
        {hint && <div className="text-xs text-neutral-500">{hint}</div>}
      </div>
      <input type="checkbox" checked={value} onChange={(e) => onChange(e.target.checked)}
             className="h-4 w-4 accent-led-idle" />
    </div>
  );
}

export default function Water() {
  const [w, setW] = useState<WaterStatus | null>(null);
  const [busy, setBusy] = useState(false);

  const load = () => api.waterStatus().then(setW).catch(() => {});
  useEffect(() => {
    load();
    const t = setInterval(load, 10000);   // refresh countdown
    return () => clearInterval(t);
  }, []);

  const set = async (key: string, value: unknown) => {
    setBusy(true);
    try {
      await api.updateSettings([{ key, value }]);
      await load();
    } finally {
      setBusy(false);
    }
  };

  if (!w) return <div className="text-sm text-neutral-500">Loading…</div>;

  const goalPct = Math.min(100, w.daily_goal ? (w.count_today / w.daily_goal) * 100 : 0);

  return (
    <div className="max-w-xl">
      <h1 className="text-lg font-semibold mb-1">Water reminder</h1>
      <p className="text-sm text-neutral-500 mb-5">
        A timed nudge to hydrate — fired only when you're actually in front of DeskBot.
      </p>

      {/* today */}
      <div className="rounded-xl border border-neutral-800 bg-neutral-900/50 p-5 mb-5">
        <div className="flex items-end justify-between mb-2">
          <div>
            <div className="text-xs uppercase tracking-wide text-neutral-500">Today</div>
            <div className="text-2xl font-semibold tabular-nums">
              {w.count_today} <span className="text-neutral-500 text-base">/ {w.daily_goal} glasses</span>
            </div>
          </div>
          <div className="text-right">
            <div className="text-xs uppercase tracking-wide text-neutral-500">Next reminder</div>
            <div className="text-lg font-semibold tabular-nums">
              {w.reminder_enabled ? fmt(w.seconds_until_next) : "off"}
            </div>
          </div>
        </div>
        <div className="h-2 rounded-full bg-neutral-800 overflow-hidden">
          <div className="h-full bg-led-idle" style={{ width: `${goalPct}%` }} />
        </div>
        <div className="mt-4 flex gap-2">
          <button
            onClick={async () => { setBusy(true); try { setW(await api.waterDrank()); } finally { setBusy(false); } }}
            disabled={busy}
            className="rounded-md bg-led-working px-4 py-2 text-sm font-medium text-neutral-950 disabled:opacity-40"
          >
            💧 I drank water
          </button>
          <button
            onClick={() => api.waterTest()}
            className="rounded-md bg-neutral-800 px-4 py-2 text-sm hover:bg-neutral-700"
          >
            Test alert
          </button>
        </div>
      </div>

      {/* config */}
      <h2 className="text-xs uppercase tracking-wide text-neutral-500 mb-2">Settings</h2>
      <div className="rounded-lg border border-neutral-800 divide-y divide-neutral-800">
        <Toggle label="Reminders enabled" value={w.reminder_enabled}
                onChange={(v) => set("water.reminder_enabled", v)} />
        <Toggle label="Only when present" hint="Skip the reminder if you're not in front of the camera"
                value={w.only_when_present} onChange={(v) => set("water.only_when_present", v)} />
        <Toggle label="Buzzer alert" hint="Beep the buzzer when a reminder fires"
                value={w.buzzer_enabled} onChange={(v) => set("water.buzzer_enabled", v)} />
        <div className="flex items-center justify-between px-4 py-3">
          <div className="text-sm text-neutral-200">Interval (minutes)</div>
          <input type="number" min={1} defaultValue={w.interval_min}
                 onBlur={(e) => set("water.interval_min", parseInt(e.target.value || "60", 10))}
                 className="w-24 rounded-md bg-neutral-900 border border-neutral-800 px-2 py-1 text-sm text-right outline-none focus:border-neutral-600" />
        </div>
        <div className="flex items-center justify-between px-4 py-3">
          <div className="text-sm text-neutral-200">Daily goal (glasses)</div>
          <input type="number" min={1} defaultValue={w.daily_goal}
                 onBlur={(e) => set("water.daily_goal", parseInt(e.target.value || "8", 10))}
                 className="w-24 rounded-md bg-neutral-900 border border-neutral-800 px-2 py-1 text-sm text-right outline-none focus:border-neutral-600" />
        </div>
      </div>

      <p className="mt-4 text-xs text-neutral-600">
        When a reminder fires: the OLED plays a “drink water” animation, the buzzer
        beeps (if enabled + wired), and a banner shows on the dashboard.
      </p>
    </div>
  );
}
