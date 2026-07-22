import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AppHeader } from "./AppHeader";
import { saveSession, getToken } from "@/lib/auth";
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

describe("AppHeader", () => {
  beforeEach(() => {
    replaceMock.mockClear();
    window.localStorage.clear();
  });

  it("shows navigation links to /empresas and /dashboard", () => {
    render(<AppHeader />);

    expect(screen.getByRole("link", { name: "Empresas" })).toHaveAttribute(
      "href",
      "/empresas",
    );
    expect(screen.getByRole("link", { name: "Dashboard" })).toHaveAttribute(
      "href",
      "/dashboard",
    );
  });

  it("clears the session and redirects to /login when clicking Cerrar sesión", async () => {
    saveSession(loginResponse);
    const user = userEvent.setup();
    render(<AppHeader />);

    await user.click(screen.getByRole("button", { name: "Cerrar sesión" }));

    expect(getToken()).toBeNull();
    expect(replaceMock).toHaveBeenCalledWith("/login");
  });
});
