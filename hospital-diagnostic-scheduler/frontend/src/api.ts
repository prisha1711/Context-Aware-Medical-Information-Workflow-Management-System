import type { Session } from "./types";

export const API = (import.meta.env.VITE_API_URL as string) || "http://localhost:8000";
let session: Session | null = JSON.parse(localStorage.getItem("hds_session") || "null");

export const getSession = () => session;
export function logout() { session = null; localStorage.removeItem("hds_session"); }

export async function login(username: string, password: string): Promise<Session> {
  const body = new URLSearchParams({ username, password });
  const r = await fetch(`${API}/auth/login`, { method: "POST", body });
  if (!r.ok) throw new Error("Incorrect username or password");
  const j = await r.json();
  session = { token: j.access_token, role: j.role, username: j.username };
  localStorage.setItem("hds_session", JSON.stringify(session));
  return session;
}

export async function api<T = unknown>(path: string, method = "GET", body?: unknown): Promise<T> {
  const r = await fetch(`${API}${path}`, {
    method,
    headers: { "Content-Type": "application/json", ...(session ? { Authorization: `Bearer ${session.token}` } : {}) },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (r.status === 401) { logout(); location.reload(); }
  if (!r.ok) throw new Error((await r.json().catch(() => ({ detail: r.statusText }))).detail || r.statusText);
  return r.json() as Promise<T>;
}

export function openSocket(onMessage: (m: { type: string }) => void): WebSocket | null {
  if (!session) return null;
  const ws = new WebSocket(`${API.replace(/^http/, "ws")}/ws?token=${session.token}`);
  ws.onmessage = (e) => onMessage(JSON.parse(e.data));
  const ping = setInterval(() => ws.readyState === 1 && ws.send("ping"), 20000);
  ws.onclose = () => clearInterval(ping);
  return ws;
}
