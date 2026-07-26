// Minimal client-side auth: store the bearer token in localStorage.
const KEY = "peekabot_token";

export function getToken(): string | null {
  return localStorage.getItem(KEY);
}
export function setToken(t: string): void {
  localStorage.setItem(KEY, t);
}
export function clearToken(): void {
  localStorage.removeItem(KEY);
}

// Called by the API client on a 401 — drop the token and bounce to login.
export function onUnauthorized(): void {
  clearToken();
  if (location.pathname !== "/") location.assign("/");
  else location.reload();
}
