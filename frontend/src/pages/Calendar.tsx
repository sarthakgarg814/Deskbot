import { useEffect, useState } from "react";
import { api, type CalAuth, type CalEvent } from "../lib/api";

function when(ev: CalEvent): string {
  const start = new Date(ev.start);
  if (ev.all_day) return "all day";
  return start.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function countdown(ev: CalEvent): string {
  const mins = Math.round((new Date(ev.start).getTime() - Date.now()) / 60000);
  if (mins < -1) return "";
  if (mins <= 0) return "now";
  if (mins < 60) return `in ${mins}m`;
  const h = Math.floor(mins / 60);
  return `in ${h}h ${mins % 60}m`;
}

export default function Calendar() {
  const [auth, setAuth] = useState<CalAuth | null>(null);
  const [today, setToday] = useState<CalEvent[]>([]);
  const [upcoming, setUpcoming] = useState<CalEvent[]>([]);
  const [syncing, setSyncing] = useState(false);
  const [tick, setTick] = useState(0);

  const load = async () => {
    const a = await api.calendarAuth().catch(() => ({ has_client_secret: false, connected: false }));
    setAuth(a);
    if (a.connected) {
      setToday(await api.calendarToday().catch(() => []));
      setUpcoming(await api.calendarUpcoming().catch(() => []));
    }
  };

  useEffect(() => {
    load();
    const t = setInterval(() => setTick((x) => x + 1), 30000); // refresh countdowns
    return () => clearInterval(t);
  }, []);
  void tick;

  const sync = async () => {
    setSyncing(true);
    try {
      await api.calendarSync();
      await load();
    } catch (e) {
      alert(`Sync failed: ${e}`);
    } finally {
      setSyncing(false);
    }
  };

  if (auth && !auth.connected) {
    return (
      <div className="max-w-xl">
        <h1 className="text-lg font-semibold mb-3">Calendar</h1>
        <div className="rounded-lg border border-neutral-800 bg-neutral-900/50 p-5 text-sm text-neutral-300 space-y-2">
          <p className="font-medium text-neutral-100">Not connected to Google Calendar.</p>
          <p className="text-neutral-400">
            {auth.has_client_secret
              ? "Client secret found. Run the one-time auth on your laptop:"
              : "Set it up (free, ~10 min):"}
          </p>
          <ol className="list-decimal ml-5 space-y-1 text-neutral-400">
            <li>Google Cloud → enable Calendar API → OAuth consent (add yourself as test user, set "In production")</li>
            <li>Create an OAuth <b>Desktop app</b> client → download JSON → save as <code>config/google/client_secret.json</code></li>
            <li>On your laptop: <code>python scripts/google-auth.py</code> (opens a browser)</li>
            <li>Enable calendar in Settings, then <code>./scripts/deploy-to-pi.sh</code> + restart core</li>
          </ol>
        </div>
      </div>
    );
  }

  const next = upcoming.find((e) => new Date(e.start).getTime() > Date.now());

  return (
    <div className="max-w-xl">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-lg font-semibold">Calendar</h1>
        <button onClick={sync} disabled={syncing}
                className="rounded-md bg-neutral-800 px-3 py-1.5 text-sm hover:bg-neutral-700 disabled:opacity-40">
          {syncing ? "syncing…" : "sync now"}
        </button>
      </div>

      {next && (
        <div className="rounded-xl border border-led-idle/40 bg-led-idle/10 p-5 mb-5">
          <div className="text-xs uppercase tracking-wide text-neutral-400">Next up · {countdown(next)}</div>
          <div className="text-xl font-semibold mt-1">{next.title}</div>
          <div className="text-sm text-neutral-400 mt-0.5">
            {when(next)}{next.location ? ` · ${next.location}` : ""}
          </div>
        </div>
      )}

      <h2 className="text-xs uppercase tracking-wide text-neutral-500 mb-2">Today</h2>
      <ul className="rounded-lg border border-neutral-800 divide-y divide-neutral-800 mb-5">
        {today.length === 0 && <li className="px-4 py-3 text-sm text-neutral-500">Nothing today 🎉</li>}
        {today.map((e) => (
          <li key={e.id} className="flex items-center gap-3 px-4 py-2.5 text-sm">
            <span className="w-16 tabular-nums text-neutral-400">{when(e)}</span>
            <span className="flex-1 truncate">{e.title}</span>
            <span className="text-xs text-neutral-500">{countdown(e)}</span>
          </li>
        ))}
      </ul>

      <h2 className="text-xs uppercase tracking-wide text-neutral-500 mb-2">Upcoming</h2>
      <ul className="rounded-lg border border-neutral-800 divide-y divide-neutral-800">
        {upcoming.length === 0 && <li className="px-4 py-3 text-sm text-neutral-500">No upcoming events</li>}
        {upcoming.map((e) => (
          <li key={e.id} className="flex items-center gap-3 px-4 py-2.5 text-sm">
            <span className="w-28 text-neutral-400">
              {new Date(e.start).toLocaleDateString([], { weekday: "short", hour: "2-digit", minute: "2-digit" })}
            </span>
            <span className="flex-1 truncate">{e.title}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
