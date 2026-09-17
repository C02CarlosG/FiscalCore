import { describe, expect, it, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ThemeToggle } from "./ThemeToggle";

describe("ThemeToggle", () => {
  beforeEach(() => {
    document.documentElement.classList.remove("dark");
    window.localStorage.clear();
  });

  it("shows 'Modo claro' by default and toggles to dark on click", async () => {
    const user = userEvent.setup();
    render(<ThemeToggle />);

    expect(screen.getByText("Modo claro")).toBeInTheDocument();

    await user.click(screen.getByRole("button"));

    expect(document.documentElement.classList.contains("dark")).toBe(true);
    expect(screen.getByText("Modo oscuro")).toBeInTheDocument();
    expect(window.localStorage.getItem("fiscalcore-theme")).toBe("dark");
  });

  it("reads a previously saved dark preference on mount", () => {
    window.localStorage.setItem("fiscalcore-theme", "dark");
    render(<ThemeToggle />);

    expect(document.documentElement.classList.contains("dark")).toBe(true);
    expect(screen.getByText("Modo oscuro")).toBeInTheDocument();
  });
});
