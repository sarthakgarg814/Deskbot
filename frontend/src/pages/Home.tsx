import { useTopic } from "../lib/ws";
import type { SystemStatus } from "../lib/api";

function Tile({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-xl border border-neutral-800 bg-neutral-900/50 p-5">
      <div className="text-xs uppercase tracking-wide text-neutral-500">{label}</div>
      <div className="mt-2 text-3xl font-semibold tabular-nums">{value}</div>
      {sub && <div className="mt-1 text-xs text-neutral-500">{sub}</div>}
    </div>
  );
}

function fmtUptime(s: number): string {
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  if (h >= 24) return `${Math.floor(h / 24)}d ${h % 24}h`;
  return h > 0 ? `${h}h ${m}m` : `${m}m`;
}

export default function Home() {
  const sys = useTopic<SystemStatus>("system");

  return (
    <div>
      <h1 className="text-lg font-semibold mb-1">Dashboard</h1>
      <p className="text-sm text-neutral-500 mb-6">
        Live system status, streamed over WebSocket at 1&nbsp;Hz.
      </p>

      {!sys ? (
        <div className="text-neutral-500 text-sm">Waiting for the first sample…</div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
          <Tile label="CPU" value={`${sys.cpu_percent.toFixed(0)}%`} />
          <Tile
            label="RAM"
            value={`${sys.ram_percent.toFixed(0)}%`}
            sub={`${(sys.ram_used_mb / 1000).toFixed(1)} / ${(sys.ram_total_mb / 1000).toFixed(1)} GB`}
          />
          <Tile
            label="Temp"
            value={sys.temp_c != null ? `${sys.temp_c.toFixed(0)}°C` : "—"}
            sub={sys.temp_c == null ? "no sensor (dev machine)" : undefined}
          />
          <Tile label="Storage" value={`${sys.storage_percent.toFixed(0)}%`} />
          <Tile label="Uptime" value={fmtUptime(sys.uptime_s)} />
          <Tile
            label="Services"
            value={`${Object.values(sys.services).filter(Boolean).length}/${
              Object.keys(sys.services).length
            }`}
            sub={Object.keys(sys.services).join(", ") || undefined}
          />
        </div>
      )}
    </div>
  );
}
