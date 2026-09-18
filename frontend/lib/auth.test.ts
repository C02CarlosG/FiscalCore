import { describe, it, expect, beforeEach } from "vitest";
import { saveSession, loadSession, clearSession, getToken } from "./auth";
import type { LoginResponse } from "@/types/api";

const loginResponse: LoginResponse = {
  access_token: "abc123",
  token_type: "bearer",
  user_id: "u1",
  email: "test@example.com",
  nombre: "Test",
  empresas: [],
};

describe("auth session storage", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("saves and loads a session", () => {
    saveSession(loginResponse);
    const session = loadSession();
    expect(session?.accessToken).toBe("abc123");
    expect(session?.email).toBe("test@example.com");
  });

  it("returns null when there is no session", () => {
    expect(loadSession()).toBeNull();
  });

  it("clears the session", () => {
    saveSession(loginResponse);
    clearSession();
    expect(loadSession()).toBeNull();
  });

  it("getToken returns the stored token", () => {
    saveSession(loginResponse);
    expect(getToken()).toBe("abc123");
  });

  it("getToken returns null without a session", () => {
    expect(getToken()).toBeNull();
  });
});
