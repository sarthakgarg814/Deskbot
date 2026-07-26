// Thin REST client. Same-origin in prod (backend serves the bundle); the Vite
// dev server proxies /api -> :8000.

export interface SystemStatus {
  cpu_percent: number;
  ram_percent: number;
  ram_used_mb: number;
  ram_total_mb: number;
  temp_c: number | null;
  storage_percent: number;
  uptime_s: number;
  services: Record<string, boolean>;
}

export interface Note {
  id: number;
  title: string;
  body: string;
  tags: string[];
  source: string;
  created_at: string;
  updated_at: string;
}

export interface Setting {
  key: string;
  value: unknown;
  type: string;
  namespace: string;
  updated_at: string;
}

export interface Face {
  cx: number;
  cy: number;
  err_x: number;
  err_y: number;
  score: number;
}

export interface ServoState {
  pan: number;
  tilt: number;
  owner: string;
}

export interface CameraStatus {
  running: boolean;
  fps?: number;
  detect_ms?: number;
  present?: boolean;
  faces?: number;
  preview?: boolean;
  tracking?: boolean;
  face?: Face | null;
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  if (res.status === 204) return undefined as T;
  return res.json();
}

export const api = {
  system: () => req<SystemStatus>("/system"),

  listNotes: (q = "") => req<Note[]>(`/notes${q ? `?q=${encodeURIComponent(q)}` : ""}`),
  createNote: (body: string, tags: string[] = []) =>
    req<Note>("/notes", { method: "POST", body: JSON.stringify({ body, tags }) }),
  updateNote: (id: number, patch: Partial<Pick<Note, "title" | "body" | "tags">>) =>
    req<Note>(`/notes/${id}`, { method: "PUT", body: JSON.stringify(patch) }),
  deleteNote: (id: number) => req<void>(`/notes/${id}`, { method: "DELETE" }),

  listSettings: (ns = "") => req<Setting[]>(`/settings${ns ? `?ns=${ns}` : ""}`),
  updateSettings: (updates: { key: string; value: unknown }[]) =>
    req<Setting[]>("/settings", { method: "POST", body: JSON.stringify(updates) }),

  servoTest: (pan: number, tilt: number) =>
    req<{ pan: number; tilt: number }>("/servo/test", {
      method: "POST",
      body: JSON.stringify({ pan, tilt }),
    }),
  servoStatus: () => req<ServoState>("/servo/status"),
  ledState: (state: string) =>
    req<{ state: string; valid_states: string[] }>("/led/state", {
      method: "POST",
      body: JSON.stringify({ state }),
    }),
  oledPreview: () => req<{ lines: string[] }>("/oled/preview"),

  cameraStatus: () => req<CameraStatus>("/camera/status"),
  cameraCenter: () => req<{ ok: boolean }>("/camera/center", { method: "POST" }),
};
