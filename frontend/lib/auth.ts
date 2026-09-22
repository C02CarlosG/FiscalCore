import type { LoginResponse } from "@/types/api";

const STORAGE_KEY = "fiscalcore.session";

export interface Session {
  accessToken: string;
  userId: string;
  email: string;
  nombre: string | null;
  empresas: LoginResponse["empresas"];
}

export function saveSession(login: LoginResponse): Session {
  const session: Session = {
    accessToken: login.access_token,
    userId: login.user_id,
    email: login.email,
    nombre: login.nombre,
    empresas: login.empresas,
  };
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
  return session;
}

export function loadSession(): Session | null {
  const raw = window.localStorage.getItem(STORAGE_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as Session;
  } catch {
    return null;
  }
}

export function clearSession(): void {
  window.localStorage.removeItem(STORAGE_KEY);
}

export function getToken(): string | null {
  return loadSession()?.accessToken ?? null;
}
