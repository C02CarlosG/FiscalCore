import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, waitFor } from "@testing-library/react";
import HomePage from "./page";
import { saveSession } from "@/lib/auth";
import type { LoginResponse } from "@/types/api";

const replaceMock = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: replaceMock }),
}));

const loginResponse: LoginResponse = {
  access_token: "token-123",
  token_type: "bearer",
  user_id: "u1",
  email: "test@example.com",
  nombre: "Test",
  empresas: [],
};

describe("HomePage", () => {
  beforeEach(() => {
    replaceMock.mockClear();
    window.localStorage.clear();
  });

  it("redirects to /login when there is no session", async () => {
    render(<HomePage />);
    await waitFor(() => expect(replaceMock).toHaveBeenCalledWith("/login"));
  });

  it("redirects to /empresas when there is a session", async () => {
    saveSession(loginResponse);
    render(<HomePage />);
    await waitFor(() => expect(replaceMock).toHaveBeenCalledWith("/empresas"));
  });
});
