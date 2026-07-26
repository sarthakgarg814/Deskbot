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
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const j = await res.json();
      detail = j.detail ?? j.error?.message ?? detail;
    } catch {
      /* non-JSON error body */
    }
    throw new Error(`${res.status} · ${detail}`);
  }
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

  calendarAuth: () => req<CalAuth>("/calendar/auth"),
  calendarConfig: () => req<CalConfig>("/calendar/config"),
  calendarCalendars: () => req<CalInfo[]>("/calendar/calendars"),
  calendarToday: () => req<CalEvent[]>("/calendar/today"),
  calendarUpcoming: () => req<CalEvent[]>("/calendar/upcoming"),
  calendarSync: () => req<{ synced: number; events: CalEvent[] }>("/calendar/sync", { method: "POST" }),
  calendarSaveSecret: (content: string) =>
    req<{ ok: boolean }>("/calendar/client-secret", { method: "POST", body: JSON.stringify({ content }) }),
  calendarAuthUrl: () => req<{ url: string }>("/calendar/auth-url"),
  calendarExchange: (code: string) =>
    req<{ ok: boolean; synced: number }>("/calendar/exchange", { method: "POST", body: JSON.stringify({ code }) }),
  calendarDisconnect: () => req<{ ok: boolean }>("/calendar/disconnect", { method: "POST" }),

  waterStatus: () => req<WaterStatus>("/water/status"),
  waterDrank: () => req<WaterStatus>("/water/drank", { method: "POST" }),
  waterTest: () => req<{ ok: boolean }>("/water/test", { method: "POST" }),

  wifiStatus: () => req<WifiStatus>("/wifi/status"),
  wifiScan: () => req<{ available: boolean; networks: WifiNetwork[] }>("/wifi/scan"),
  wifiConnect: (ssid: string, password: string) =>
    req<{ ok: boolean; message?: string }>("/wifi/connect", {
      method: "POST",
      body: JSON.stringify({ ssid, password }),
    }),
};

export interface CalEvent {
  id: number;
  title: string;
  start: string;
  end: string;
  location: string;
  source: string;
  primary: boolean;
  all_day: boolean;
}

export interface CalAuth {
  has_client_secret: boolean;
  connected: boolean;
}

export interface CalConfig extends CalAuth {
  enabled: boolean;
  sync_min: number;
  reminder_min: number;
  hide_busy: boolean;
  meeting_mode: boolean;
  enabled_ids: string[];
}

export interface CalInfo {
  id: string;
  name: string;
  primary: boolean;
  enabled: boolean;
}

export interface WaterStatus {
  reminder_enabled: boolean;
  interval_min: number;
  only_when_present: boolean;
  buzzer_enabled: boolean;
  daily_goal: number;
  active_start: string;
  active_end: string;
  active_days: number[];
  reset_hour: number;
  active_now: boolean;
  count_today: number;
  last_event: string | null;
  seconds_until_next: number;
}

export interface WifiStatus {
  available: boolean;
  connected?: boolean;
  ssid?: string | null;
  signal?: number | null;
  ip?: string | null;
}

export interface WifiNetwork {
  ssid: string;
  signal: number;
  security: string;
  in_use: boolean;
}
