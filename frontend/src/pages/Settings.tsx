import { useEffect, useMemo, useState } from "react";
import { api, type Setting } from "../lib/api";

export default function Settings() {
  const [settings, setSettings] = useState<Setting[]>([]);
  const [dirty, setDirty] = useState<Record<string, unknown>>({});
  const [saving, setSaving] = useState(false);

  const load = async () => setSettings(await api.listSettings());
  useEffect(() => {
    load();
  }, []);

  const byNs = useMemo(() => {
    const m: Record<string, Setting[]> = {};
    for (const s of settings) (m[s.namespace] ??= []).push(s);
    return m;
  }, [settings]);

  const setVal = (key: string, value: unknown) =>
    setDirty((d) => ({ ...d, [key]: value }));

  const save = async () => {
    const updates = Object.entries(dirty).map(([key, value]) => ({ key, value }));
    if (updates.length === 0) return;
    setSaving(true);
    try {
      setSettings(await api.updateSettings(updates));
      setDirty({});
    } finally {
      setSaving(false);
    }
  };

  const cur = (s: Setting) => (s.key in dirty ? dirty[s.key] : s.value);

  return (
    <div className="max-w-2xl">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-lg font-semibold">Settings</h1>
        <button
          onClick={save}
          disabled={Object.keys(dirty).length === 0 || saving}
          className="rounded-md bg-led-idle px-4 py-2 text-sm font-medium text-white disabled:opacity-40"
        >
          {saving ? "Saving…" : `Save${Object.keys(dirty).length ? ` (${Object.keys(dirty).length})` : ""}`}
        </button>
      </div>

      {Object.entries(byNs).map(([ns, items]) => (
        <section key={ns} className="mb-6">
          <h2 className="text-xs uppercase tracking-wide text-neutral-500 mb-2">{ns}</h2>
          <div className="rounded-lg border border-neutral-800 divide-y divide-neutral-800">
            {items.map((s) => (
              <div key={s.key} className="flex items-center justify-between px-4 py-2.5 gap-4">
                <label className="text-sm text-neutral-300 font-mono">{s.key}</label>
                {s.type === "bool" ? (
                  <input
                    type="checkbox"
                    checked={Boolean(cur(s))}
                    onChange={(e) => setVal(s.key, e.target.checked)}
                    className="h-4 w-4 accent-led-idle"
                  />
                ) : (
                  <input
                    type={s.type === "int" || s.type === "float" ? "number" : "text"}
                    step={s.type === "float" ? "0.01" : "1"}
                    value={String(cur(s) ?? "")}
                    onChange={(e) =>
                      setVal(
                        s.key,
                        s.type === "int"
                          ? parseInt(e.target.value || "0", 10)
                          : s.type === "float"
                          ? parseFloat(e.target.value || "0")
                          : e.target.value
                      )
                    }
                    className="w-40 rounded-md bg-neutral-900 border border-neutral-800 px-2 py-1 text-sm text-right outline-none focus:border-neutral-600"
                  />
                )}
              </div>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
