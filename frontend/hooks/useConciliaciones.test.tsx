import { describe, expect, it, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  useConciliacionResumen,
  useConciliacionesAccionables,
} from "./useConciliaciones";

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

describe("useConciliacionResumen", () => {
  beforeEach(() => {
    vi.mocked(apiFetch).mockReset();
  });

  it("does not fetch when there is no empresaId", () => {
    renderHook(() => useConciliacionResumen("", ""), { wrapper });
    expect(apiFetch).not.toHaveBeenCalled();
  });

  it("fetches without a periodo query param when periodo is empty", async () => {
    vi.mocked(apiFetch).mockResolvedValue({});
    renderHook(() => useConciliacionResumen("empresa-1", ""), { wrapper });

    await waitFor(() =>
      expect(apiFetch).toHaveBeenCalledWith(
        "/api/v1/empresas/empresa-1/conciliaciones",
      ),
    );
  });

  it("fetches with a periodo query param when periodo is set", async () => {
    vi.mocked(apiFetch).mockResolvedValue({});
    renderHook(() => useConciliacionResumen("empresa-1", "2026-07"), {
      wrapper,
    });

    await waitFor(() =>
      expect(apiFetch).toHaveBeenCalledWith(
        "/api/v1/empresas/empresa-1/conciliaciones?periodo=2026-07",
      ),
    );
  });
});

describe("useConciliacionesAccionables", () => {
  beforeEach(() => {
    vi.mocked(apiFetch).mockReset();
  });

  it("does not fetch when there is no empresaId", () => {
    renderHook(() => useConciliacionesAccionables("", ""), { wrapper });
    expect(apiFetch).not.toHaveBeenCalled();
  });

  it("fetches without a periodo query param when periodo is empty", async () => {
    vi.mocked(apiFetch).mockResolvedValue({});
    renderHook(() => useConciliacionesAccionables("empresa-1", ""), {
      wrapper,
    });

    await waitFor(() =>
      expect(apiFetch).toHaveBeenCalledWith(
        "/api/v1/empresas/empresa-1/conciliaciones/accionables",
      ),
    );
  });

  it("fetches with a periodo query param when periodo is set", async () => {
    vi.mocked(apiFetch).mockResolvedValue({});
    renderHook(
      () => useConciliacionesAccionables("empresa-1", "2026-07"),
      { wrapper },
    );

    await waitFor(() =>
      expect(apiFetch).toHaveBeenCalledWith(
        "/api/v1/empresas/empresa-1/conciliaciones/accionables?periodo=2026-07",
      ),
    );
  });
});
