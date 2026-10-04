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
  // Sin diagonal final: "/" queda en "" y las rutas salen relativas al mismo
  // origen (despliegue en Vercel, donde frontend y API comparten dominio).
  return url.replace(/\/+$/, "");
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

async function pedir(path: string, options: RequestInit): Promise<Response> {
  const token = getToken();
  const isFormData = options.body instanceof FormData;
  const headers: Record<string, string> = {
    ...(isFormData ? {} : { "Content-Type": "application/json" }),
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

  return response;
}

export async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const response = await pedir(path, options);

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

/** Descarga un archivo (con la sesión). Devuelve el contenido y el nombre que propone el servidor. */
export async function apiDownload(
  path: string,
  nombreFallback: string,
): Promise<{ blob: Blob; nombre: string }> {
  const response = await pedir(path, {});
  const disposicion = response.headers.get("Content-Disposition") ?? "";
  const nombre = /filename="?([^";]+)"?/.exec(disposicion)?.[1] ?? nombreFallback;
  return { blob: await response.blob(), nombre };
}
