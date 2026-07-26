import { useEffect, useState, type ReactNode } from "react";
import { api, type CalAuth, type CalConfig, type CalEvent, type CalInfo } from "../lib/api";

function Connect({ auth, onDone }: { auth: CalAuth; onDone: () => void }) {
  const [hasSecret, setHasSecret] = useState(auth.has_client_secret);
  const [authUrl, setAuthUrl] = useState<string | null>(null);
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const uploadSecret = async (file: File) => {
    setErr(null);
    try {
      await api.calendarSaveSecret(await file.text());
      setHasSecret(true);
    } catch (e) {
      setErr(`${e}`);
    }
  };

  const startAuth = async () => {
    setErr(null);
    try {
      setAuthUrl((await api.calendarAuthUrl()).url);
    } catch (e) {
      setErr(`${e}`);
    }
  };

  const finish = async () => {
    setBusy(true);
    setErr(null);
    try {
      await api.calendarExchange(code.trim());
      onDone();
    } catch (e) {
      setErr(`${e}`);
    } finally {
      setBusy(false);
    }
  };

  const step = "block text-xs font-semibold text-neutral-500 mb-1";
  return (
    <div className="max-w-xl">
      <h1 className="text-lg font-semibold mb-1">Connect Google Calendar</h1>
      <p className="text-sm text-neutral-500 mb-5">Read-only, free. All from here — no laptop scripts.</p>

      <div className="space-y-5">
        {/* 1 */}
        <div className="rounded-lg border border-neutral-800 p-4">
          <span className={step}>1 · Upload OAuth client secret</span>
          <p className="text-xs text-neutral-500 mb-2">
            Google Cloud → Credentials → create an <b>OAuth Desktop-app</b> client → Download JSON.
          </p>
          <input type="file" accept=".json,application/json"
                 onChange={(e) => e.target.files?.[0] && uploadSecret(e.target.files[0])}
                 className="text-sm text-neutral-400" />
          {hasSecret && <span className="ml-2 text-xs text-led-working">✓ saved</span>}
        </div>

        {/* 2 */}
        <div className={`rounded-lg border border-neutral-800 p-4 ${hasSecret ? "" : "opacity-40 pointer-events-none"}`}>
          <span className={step}>2 · Authorize</span>
          <button onClick={startAuth}
                  className="rounded-md bg-led-idle px-4 py-2 text-sm font-medium text-white">
            Get authorization link
          </button>
          {authUrl && (
            <div className="mt-3 text-xs text-neutral-400 space-y-2">
              <a href={authUrl} target="_blank" rel="noreferrer" className="text-led-idle underline break-all">
                Open Google authorization →
              </a>
              <p>
                Approve access. Your browser then tries to open a <b>localhost</b> page that
                won't load — that's expected. Copy the whole address-bar URL (or just the
                <code> code=… </code> part) and paste it below.
              </p>
            </div>
          )}
        </div>

        {/* 3 */}
        <div className={`rounded-lg border border-neutral-800 p-4 ${authUrl ? "" : "opacity-40 pointer-events-none"}`}>
          <span className={step}>3 · Paste the code</span>
          <div className="flex gap-2">
            <input value={code} onChange={(e) => setCode(e.target.value)}
                   placeholder="paste the redirected URL or code"
                   className="flex-1 rounded-md bg-neutral-900 border border-neutral-800 px-3 py-2 text-sm outline-none focus:border-neutral-600" />
            <button onClick={finish} disabled={busy || !code.trim()}
                    className="rounded-md bg-led-working px-4 py-2 text-sm font-medium text-neutral-950 disabled:opacity-40">
              {busy ? "Connecting…" : "Connect"}
            </button>
          </div>
        </div>

        {err && <div className="text-sm text-led-error">{err}</div>}
      </div>
    </div>
  );
}

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

function Tag({ ev }: { ev: CalEvent }) {
  const label = ev.primary ? "Personal" : (ev.source?.split("@")[0] || "shared");
  const cls = ev.primary ? "bg-led-idle/20 text-led-idle" : "bg-amber-500/20 text-amber-400";
  return <span className={`ml-2 rounded px-1.5 py-0.5 text-[10px] ${cls}`}>{label}</span>;
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
    return <Connect auth={auth} onDone={load} />;
  }

  const next = upcoming.find((e) => new Date(e.start).getTime() > Date.now());

  return (
    <div className="max-w-xl">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-lg font-semibold">Calendar</h1>
        <div className="flex gap-2">
          <button onClick={sync} disabled={syncing}
                  className="rounded-md bg-neutral-800 px-3 py-1.5 text-sm hover:bg-neutral-700 disabled:opacity-40">
            {syncing ? "syncing…" : "sync now"}
          </button>
          <button onClick={async () => { await api.calendarDisconnect(); load(); }}
                  className="rounded-md bg-neutral-800 px-3 py-1.5 text-sm text-neutral-400 hover:text-led-error">
            disconnect
          </button>
        </div>
      </div>

      {next && (
        <div className="rounded-xl border border-led-idle/40 bg-led-idle/10 p-5 mb-5">
          <div className="text-xs uppercase tracking-wide text-neutral-400">Next up · {countdown(next)}</div>
          <div className="text-xl font-semibold mt-1">{next.title}<Tag ev={next} /></div>
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
            <span className="flex-1 truncate">{e.title}<Tag ev={e} /></span>
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
            <span className="flex-1 truncate">{e.title}<Tag ev={e} /></span>
          </li>
        ))}
      </ul>

      <CalendarSettings />
    </div>
  );
}

function CalendarSettings() {
  const [cfg, setCfg] = useState<CalConfig | null>(null);
  const [cals, setCals] = useState<CalInfo[]>([]);

  const load = async () => {
    setCfg(await api.calendarConfig().catch(() => null));
    setCals(await api.calendarCalendars().catch(() => []));
  };
  useEffect(() => { load(); }, []);

  const set = async (key: string, value: unknown) => {
    await api.updateSettings([{ key, value }]);
    load();
  };

  const toggleCal = async (id: string) => {
    const current = cfg?.enabled_ids?.length ? cfg.enabled_ids : cals.filter((c) => c.enabled).map((c) => c.id);
    const next = current.includes(id) ? current.filter((x) => x !== id) : [...current, id];
    await set("calendar.enabled_ids", next);
  };

  if (!cfg) return null;
  const enabledId = (id: string) => (cfg.enabled_ids.length ? cfg.enabled_ids.includes(id) : cals.find((c) => c.id === id)?.enabled);

  return (
    <div className="mt-8">
      <h2 className="text-xs uppercase tracking-wide text-neutral-500 mb-2">Settings</h2>
      <div className="rounded-lg border border-neutral-800 divide-y divide-neutral-800 mb-5">
        <Row label="Sync every (min)">
          <input type="number" min={1} defaultValue={cfg.sync_min}
                 onBlur={(e) => set("calendar.sync_min", parseInt(e.target.value || "15", 10))}
                 className="w-20 rounded-md bg-neutral-900 border border-neutral-800 px-2 py-1 text-sm text-right" />
        </Row>
        <Row label="Remind before meeting (min)">
          <input type="number" min={0} defaultValue={cfg.reminder_min}
                 onBlur={(e) => set("calendar.reminder_min", parseInt(e.target.value || "5", 10))}
                 className="w-20 rounded-md bg-neutral-900 border border-neutral-800 px-2 py-1 text-sm text-right" />
        </Row>
        <Row label="Meeting mode (react when a meeting starts)">
          <input type="checkbox" checked={cfg.meeting_mode} onChange={(e) => set("calendar.meeting_mode", e.target.checked)}
                 className="h-4 w-4 accent-led-idle" />
        </Row>
        <Row label={'Hide detail-less "Busy" blocks'}>
          <input type="checkbox" checked={cfg.hide_busy} onChange={(e) => set("calendar.hide_busy", e.target.checked)}
                 className="h-4 w-4 accent-led-idle" />
        </Row>
      </div>

      {cals.length > 0 && (
        <>
          <h2 className="text-xs uppercase tracking-wide text-neutral-500 mb-2">Calendars to include</h2>
          <ul className="rounded-lg border border-neutral-800 divide-y divide-neutral-800">
            {cals.map((c) => (
              <li key={c.id} className="flex items-center justify-between px-4 py-2.5 text-sm">
                <span className="truncate">
                  {c.name}
                  {c.primary && <span className="ml-2 text-[10px] text-led-idle">primary</span>}
                </span>
                <input type="checkbox" checked={Boolean(enabledId(c.id))} onChange={() => toggleCal(c.id)}
                       className="h-4 w-4 accent-led-idle" />
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-center justify-between px-4 py-3">
      <span className="text-sm text-neutral-300">{label}</span>
      {children}
    </div>
  );
}
