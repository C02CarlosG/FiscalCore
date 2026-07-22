import { getToken, clearSession } from "./auth";

export class ApiError extends Error {
  status: number;
  fieldErrors?: Record<string, string>;

  constructor(status: number, message: string, fieldErrors?: Record<string, string>) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.fieldErrors = fieldErrors;
  }
}

function apiBaseUrl(): string {
  const url = process.env.NEXT_PUBLIC_API_URL;
  if (!url) {
    throw new Error("NEXT_PUBLIC_API_URL no está configurada");
  }
  return url;
}

function parseFieldErrors(detail: unknown): Record<string, string> | undefined {
  if (!Array.isArray(detail)) return undefined;
  const fieldErrors: Record<string, string> = {};
  for (const item of detail) {
    if (item && typeof item === "object" && "loc" in item && "msg" in item) {
      const loc = (item as { loc: unknown[] }).loc;
      const field = String(loc[loc.length - 1]);
      fieldErrors[field] = String((item as { msg: unknown }).msg);
    }
  }
  return Object.keys(fieldErrors).length > 0 ? fieldErrors : undefined;
}

export async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...((options.headers as Record<string, string>) ?? {}),
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(`${apiBaseUrl()}${path}`, {
    ...options,
    headers,
  });

  if (response.status === 401) {
    clearSession();
  }

  if (!response.ok) {
    let detail: unknown = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail ?? detail;
    } catch {
      // respuesta sin cuerpo JSON, se usa statusText
    }
    const fieldErrors = parseFieldErrors(detail);
    const message = typeof detail === "string" ? detail : "Solicitud inválida";
    throw new ApiError(response.status, message, fieldErrors);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}
