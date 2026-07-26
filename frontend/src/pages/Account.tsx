import { useState } from "react";
import { api } from "../lib/api";
import { clearToken } from "../lib/auth";

export default function Account() {
  const [oldp, setOld] = useState("");
  const [newp, setNew] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const change = async () => {
    setMsg(null);
    setErr(null);
    setBusy(true);
    try {
      await api.changePassword(oldp, newp);
      setMsg("Password changed ✓");
      setOld("");
      setNew("");
    } catch (e) {
      setErr(`${e}`.replace("Error: ", ""));
    } finally {
      setBusy(false);
    }
  };

  const logout = () => {
    clearToken();
    location.reload();
  };

  const input =
    "w-full rounded-md bg-neutral-900 border border-neutral-800 px-3 py-2 text-sm outline-none focus:border-neutral-600";

  return (
    <div className="max-w-sm">
      <h1 className="text-lg font-semibold mb-4">Account</h1>

      <div className="rounded-xl border border-neutral-800 p-5 space-y-3">
        <h2 className="font-medium text-sm">Change password</h2>
        <input type="password" value={oldp} onChange={(e) => setOld(e.target.value)}
               placeholder="Current password" className={input} />
        <input type="password" value={newp} onChange={(e) => setNew(e.target.value)}
               placeholder="New password (min 4 chars)" className={input} />
        <button onClick={change} disabled={busy || !oldp || !newp}
                className="rounded-md bg-led-idle px-4 py-2 text-sm font-medium text-white disabled:opacity-40">
          {busy ? "Saving…" : "Update password"}
        </button>
        {msg && <div className="text-sm text-led-working">{msg}</div>}
        {err && <div className="text-sm text-led-error">{err}</div>}
      </div>

      <button onClick={logout}
              className="mt-5 rounded-md bg-neutral-800 px-4 py-2 text-sm text-neutral-300 hover:text-led-error">
        Sign out
      </button>
    </div>
  );
}
