import { useEffect, useState } from "react";
import { api, type WifiNetwork, type WifiStatus } from "../lib/api";

function bars(signal: number): string {
  if (signal >= 75) return "▁▃▅▇";
  if (signal >= 50) return "▁▃▅ ";
  if (signal >= 25) return "▁▃  ";
  return "▁   ";
}

export default function Wifi() {
  const [status, setStatus] = useState<WifiStatus | null>(null);
  const [nets, setNets] = useState<WifiNetwork[]>([]);
  const [scanning, setScanning] = useState(false);
  const [selected, setSelected] = useState<WifiNetwork | null>(null);
  const [password, setPassword] = useState("");
  const [connecting, setConnecting] = useState(false);
  const [result, setResult] = useState<string | null>(null);

  const loadStatus = () => api.wifiStatus().then(setStatus).catch(() => setStatus({ available: false }));
  const scan = async () => {
    setScanning(true);
    try {
      setNets((await api.wifiScan()).networks);
    } finally {
      setScanning(false);
    }
  };

  useEffect(() => {
    loadStatus();
    scan();
  }, []);

  const connect = async () => {
    if (!selected) return;
    setConnecting(true);
    setResult(null);
    try {
      const r = await api.wifiConnect(selected.ssid, password);
      setResult(r.ok ? `Connected to ${selected.ssid}` : `Failed: ${r.message ?? "unknown error"}`);
      if (r.ok) {
        setSelected(null);
        setPassword("");
        setTimeout(() => { loadStatus(); scan(); }, 2000);
      }
    } catch (e) {
      setResult("Request failed — the Pi may have switched networks (see warning).");
    } finally {
      setConnecting(false);
    }
  };

  if (status && !status.available) {
    return (
      <div className="max-w-xl">
        <h1 className="text-lg font-semibold mb-2">WiFi</h1>
        <div className="rounded-lg border border-neutral-800 bg-neutral-900/50 p-6 text-sm text-neutral-400">
          WiFi management isn't available on this host (NetworkManager/`nmcli` not
          found). This works on the Raspberry Pi.
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-xl">
      <h1 className="text-lg font-semibold mb-4">WiFi</h1>

      {/* current connection */}
      <div className="rounded-xl border border-neutral-800 bg-neutral-900/50 p-5 mb-5">
        <div className="text-xs uppercase tracking-wide text-neutral-500 mb-1">Connected to</div>
        {status?.connected ? (
          <>
            <div className="text-xl font-semibold">{status.ssid}</div>
            <div className="mt-1 text-sm text-neutral-500 tabular-nums">
              signal {status.signal ?? "—"}% · {status.ip ?? "no IP"}
            </div>
          </>
        ) : (
          <div className="text-neutral-400">Not connected</div>
        )}
      </div>

      <div className="flex items-center justify-between mb-2">
        <h2 className="text-sm font-medium text-neutral-300">Available networks</h2>
        <button
          onClick={scan}
          disabled={scanning}
          className="text-xs text-neutral-500 hover:text-neutral-200 disabled:opacity-40"
        >
          {scanning ? "scanning…" : "rescan"}
        </button>
      </div>

      <ul className="rounded-lg border border-neutral-800 divide-y divide-neutral-800 mb-4">
        {nets.length === 0 && (
          <li className="px-4 py-3 text-sm text-neutral-500">{scanning ? "scanning…" : "no networks"}</li>
        )}
        {nets.map((n) => (
          <li key={n.ssid}>
            <button
              onClick={() => { setSelected(n); setPassword(""); setResult(null); }}
              className={`w-full flex items-center gap-3 px-4 py-2.5 text-left text-sm hover:bg-neutral-900 ${
                selected?.ssid === n.ssid ? "bg-neutral-800" : ""
              }`}
            >
              <span className="font-mono text-xs text-neutral-500 w-10">{bars(n.signal)}</span>
              <span className="flex-1 truncate">
                {n.ssid} {n.in_use && <span className="text-led-working text-xs">· connected</span>}
              </span>
              {n.security && n.security !== "open" && <span className="text-neutral-600 text-xs">🔒</span>}
            </button>

            {selected?.ssid === n.ssid && !n.in_use && (
              <div className="px-4 py-3 bg-neutral-900/60 space-y-2">
                {n.security && n.security !== "open" && (
                  <input
                    type="password"
                    autoFocus
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && connect()}
                    placeholder={`Password for ${n.ssid}`}
                    className="w-full rounded-md bg-neutral-950 border border-neutral-800 px-3 py-2 text-sm outline-none focus:border-neutral-600"
                  />
                )}
                <button
                  onClick={connect}
                  disabled={connecting}
                  className="rounded-md bg-led-idle px-4 py-2 text-sm font-medium text-white disabled:opacity-40"
                >
                  {connecting ? "Connecting…" : "Connect"}
                </button>
              </div>
            )}
          </li>
        ))}
      </ul>

      {result && <div className="text-sm text-neutral-300 mb-3">{result}</div>}

      <p className="text-xs text-neutral-600">
        ⚠️ Switching to a different network will disconnect the Pi from the current
        one — you may lose access to this dashboard until you reconnect on the new
        network (the Pi's IP / <code>deskbot.local</code> may change).
      </p>
    </div>
  );
}
