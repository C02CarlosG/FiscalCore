import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { AuthGuard } from "./AuthGuard";
import { saveSession, getToken } from "@/lib/auth";
import type { LoginResponse } from "@/types/api";

const replaceMock = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: replaceMock }),
}));

vi.mock("@/lib/api-client", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api-client")>(
    "@/lib/api-client",
  );
  return { ...actual, apiFetch: vi.fn() };
});

import { apiFetch, ApiError } from "@/lib/api-client";

const loginResponse: LoginResponse = {
  access_token: "token-123",
  token_type: "bearer",
  user_id: "u1",
  email: "test@example.com",
  nombre: "Test",
  empresas: [],
};

describe("AuthGuard", () => {
  beforeEach(() => {
    replaceMock.mockClear();
    vi.mocked(apiFetch).mockReset();
    window.localStorage.clear();
  });

  it("redirects to /login when there is no session", async () => {
    render(
      <AuthGuard>
        <div>contenido protegido</div>
      </AuthGuard>,
    );

    await waitFor(() => expect(replaceMock).toHaveBeenCalledWith("/login"));
    expect(screen.queryByText("contenido protegido")).not.toBeInTheDocument();
  });

  it("renders children when the session is valid", async () => {
    saveSession(loginResponse);
    vi.mocked(apiFetch).mockResolvedValue({ user_id: "u1" });

    render(
      <AuthGuard>
        <div>contenido protegido</div>
      </AuthGuard>,
    );

    await waitFor(() =>
      expect(screen.getByText("contenido protegido")).toBeInTheDocument(),
    );
  });

  it("clears the session and redirects when /auth/me responds 401", async () => {
    saveSession(loginResponse);
    vi.mocked(apiFetch).mockRejectedValue(new ApiError(401, "no autorizado"));

    render(
      <AuthGuard>
        <div>contenido protegido</div>
      </AuthGuard>,
    );

    await waitFor(() => expect(replaceMock).toHaveBeenCalledWith("/login"));
    expect(getToken()).toBeNull();
  });
});
