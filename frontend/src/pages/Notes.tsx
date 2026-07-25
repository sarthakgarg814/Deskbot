import { useEffect, useState } from "react";
import { api, type Note } from "../lib/api";

export default function Notes() {
  const [notes, setNotes] = useState<Note[]>([]);
  const [query, setQuery] = useState("");
  const [draft, setDraft] = useState("");
  const [loading, setLoading] = useState(true);

  const load = async (q = "") => {
    setLoading(true);
    try {
      setNotes(await api.listNotes(q));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  useEffect(() => {
    const t = setTimeout(() => load(query), 200);
    return () => clearTimeout(t);
  }, [query]);

  const add = async () => {
    const body = draft.trim();
    if (!body) return;
    await api.createNote(body);
    setDraft("");
    load(query);
  };

  const remove = async (id: number) => {
    await api.deleteNote(id);
    load(query);
  };

  return (
    <div className="max-w-2xl">
      <h1 className="text-lg font-semibold mb-4">Notes</h1>

      <div className="flex gap-2 mb-4">
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && add()}
          placeholder="New note… (first line becomes the title)"
          className="flex-1 rounded-md bg-neutral-900 border border-neutral-800 px-3 py-2 text-sm outline-none focus:border-neutral-600"
        />
        <button
          onClick={add}
          className="rounded-md bg-led-working/90 px-4 py-2 text-sm font-medium text-neutral-950 hover:bg-led-working"
        >
          Add
        </button>
      </div>

      <input
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Search…"
        className="w-full mb-4 rounded-md bg-neutral-900 border border-neutral-800 px-3 py-2 text-sm outline-none focus:border-neutral-600"
      />

      {loading ? (
        <div className="text-sm text-neutral-500">Loading…</div>
      ) : notes.length === 0 ? (
        <div className="text-sm text-neutral-500">No notes yet.</div>
      ) : (
        <ul className="space-y-2">
          {notes.map((n) => (
            <li
              key={n.id}
              className="rounded-lg border border-neutral-800 bg-neutral-900/50 p-3 flex justify-between gap-3"
            >
              <div className="min-w-0">
                <div className="font-medium truncate">{n.title}</div>
                {n.body !== n.title && (
                  <div className="text-sm text-neutral-400 truncate">{n.body}</div>
                )}
                <div className="mt-1 text-xs text-neutral-600">
                  {new Date(n.created_at).toLocaleString()} · {n.source}
                </div>
              </div>
              <button
                onClick={() => remove(n.id)}
                className="shrink-0 text-xs text-neutral-500 hover:text-led-error"
              >
                delete
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
