import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { setToken } from "../lib/auth";

export default function Login({ onLogin }: { onLogin: () => void }) {
  const [password, setPassword] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [isDefault, setIsDefault] = useState(false);

  useEffect(() => {
    api.authStatus().then((s) => setIsDefault(s.is_default)).catch(() => {});
  }, []);

  const submit = async () => {
    setBusy(true);
    setErr(null);
    try {
      const { token } = await api.login(password);
      setToken(token);
      onLogin();
    } catch (e) {
      setErr("Wrong password");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen grid place-items-center px-4">
      <div className="w-full max-w-xs">
        <div className="flex items-center justify-center gap-2 mb-6">
          <span className="text-2xl">🤖</span>
          <span className="text-lg font-semibold tracking-tight">DeskBot</span>
        </div>
        <input
          type="password"
          autoFocus
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submit()}
          placeholder="Password"
          className="w-full rounded-md bg-neutral-900 border border-neutral-800 px-3 py-2.5 text-sm outline-none focus:border-neutral-600"
        />
        <button
          onClick={submit}
          disabled={busy || !password}
          className="mt-3 w-full rounded-md bg-led-idle px-4 py-2.5 text-sm font-medium text-white disabled:opacity-40"
        >
          {busy ? "Signing in…" : "Sign in"}
        </button>
        {err && <div className="mt-3 text-sm text-led-error text-center">{err}</div>}
        {isDefault && (
          <div className="mt-4 text-xs text-neutral-500 text-center">
            Default password is <code className="text-neutral-300">deskbot</code> — change it in
            Settings after signing in.
          </div>
        )}
      </div>
    </div>
  );
}
