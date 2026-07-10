import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { apiFetch, ApiError } from "./api-client";
import { saveSession, getToken } from "./auth";
import type { LoginResponse } from "@/types/api";

const loginResponse: LoginResponse = {
  access_token: "token-123",
  token_type: "bearer",
  user_id: "u1",
  email: "test@example.com",
  nombre: "Test",
  empresas: [],
};

function mockResponse(status: number, body: unknown) {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: "error",
    json: async () => body,
  };
}

describe("apiFetch", () => {
  beforeEach(() => {
    process.env.NEXT_PUBLIC_API_URL = "http://localhost:8000";
    window.localStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("adds the Authorization header when there is a session", async () => {
    saveSession(loginResponse);
    const fetchMock = vi.fn().mockResolvedValue(mockResponse(200, { ok: true }));
    vi.stubGlobal("fetch", fetchMock);

    await apiFetch("/api/v1/empresas");

    const [, options] = fetchMock.mock.calls[0];
    expect((options.headers as Record<string, string>)["Authorization"]).toBe(
      "Bearer token-123",
    );
  });

  it("does not add an Authorization header without a session", async () => {
    const fetchMock = vi.fn().mockResolvedValue(mockResponse(200, { ok: true }));
    vi.stubGlobal("fetch", fetchMock);

    await apiFetch("/api/v1/empresas");

    const [, options] = fetchMock.mock.calls[0];
    expect(
      (options.headers as Record<string, string>)["Authorization"],
    ).toBeUndefined();
  });

  it("throws ApiError with the backend detail on a non-2xx response", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(mockResponse(401, { detail: "Credenciales incorrectas" }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(apiFetch("/api/v1/auth/login")).rejects.toMatchObject({
      status: 401,
      message: "Credenciales incorrectas",
    });
  });

  it("clears the session when the response is 401", async () => {
    saveSession(loginResponse);
    const fetchMock = vi
      .fn()
      .mockResolvedValue(mockResponse(401, { detail: "no autorizado" }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(apiFetch("/api/v1/auth/me")).rejects.toBeInstanceOf(ApiError);
    expect(getToken()).toBeNull();
  });

  it("maps 422 validation errors to field errors", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      mockResponse(422, {
        detail: [{ loc: ["body", "rfc"], msg: "campo requerido" }],
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    try {
      await apiFetch("/api/v1/mis-empresas", { method: "POST" });
      throw new Error("no debería llegar aquí");
    } catch (err) {
      expect(err).toBeInstanceOf(ApiError);
      expect((err as ApiError).fieldErrors).toEqual({ rfc: "campo requerido" });
    }
  });
});
