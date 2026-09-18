import { describe, expect, it, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useDashboard } from "./useDashboard";

vi.mock("@/lib/api-client", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api-client")>(
    "@/lib/api-client",
  );
  return { ...actual, apiFetch: vi.fn() };
});

import { apiFetch } from "@/lib/api-client";

function wrapper({ children }: { children: React.ReactNode }) {
  const queryClient = new QueryClient();
  return (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

describe("useDashboard", () => {
  beforeEach(() => {
    vi.mocked(apiFetch).mockReset();
  });

  it("does not fetch when there is no empresaId", () => {
    renderHook(() => useDashboard(undefined, ""), { wrapper });
    expect(apiFetch).not.toHaveBeenCalled();
  });

  it("fetches without a periodo query param when periodo is empty", async () => {
    vi.mocked(apiFetch).mockResolvedValue({});
    renderHook(() => useDashboard("empresa-1", ""), { wrapper });

    await waitFor(() =>
      expect(apiFetch).toHaveBeenCalledWith("/api/v1/dashboard/empresa-1"),
    );
  });

  it("fetches with a periodo query param when periodo is set", async () => {
    vi.mocked(apiFetch).mockResolvedValue({});
    renderHook(() => useDashboard("empresa-1", "2026-07"), { wrapper });

    await waitFor(() =>
      expect(apiFetch).toHaveBeenCalledWith(
        "/api/v1/dashboard/empresa-1?periodo=2026-07",
      ),
    );
  });
});
