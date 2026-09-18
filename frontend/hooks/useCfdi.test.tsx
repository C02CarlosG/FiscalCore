import { describe, expect, it, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useEmitidos, useRecibidos, useVisorSat, useNominaCfdi } from "./useCfdi";

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

describe("useEmitidos", () => {
  beforeEach(() => {
    vi.mocked(apiFetch).mockReset();
  });

  it("does not fetch when there is no empresaId", () => {
    renderHook(() => useEmitidos("", "2026-07"), { wrapper });
    expect(apiFetch).not.toHaveBeenCalled();
  });

  it("does not fetch when there is no periodo", () => {
    renderHook(() => useEmitidos("empresa-1", ""), { wrapper });
    expect(apiFetch).not.toHaveBeenCalled();
  });

  it("fetches with empresaId and periodo", async () => {
    vi.mocked(apiFetch).mockResolvedValue({});
    renderHook(() => useEmitidos("empresa-1", "2026-07"), { wrapper });

    await waitFor(() =>
      expect(apiFetch).toHaveBeenCalledWith(
        "/api/v1/empresas/empresa-1/emitidos?periodo=2026-07",
      ),
    );
  });
});

describe("useRecibidos", () => {
  beforeEach(() => {
    vi.mocked(apiFetch).mockReset();
  });

  it("does not fetch when there is no empresaId", () => {
    renderHook(() => useRecibidos("", "2026-07"), { wrapper });
    expect(apiFetch).not.toHaveBeenCalled();
  });

  it("does not fetch when there is no periodo", () => {
    renderHook(() => useRecibidos("empresa-1", ""), { wrapper });
    expect(apiFetch).not.toHaveBeenCalled();
  });

  it("fetches with empresaId and periodo", async () => {
    vi.mocked(apiFetch).mockResolvedValue({});
    renderHook(() => useRecibidos("empresa-1", "2026-07"), { wrapper });

    await waitFor(() =>
      expect(apiFetch).toHaveBeenCalledWith(
        "/api/v1/empresas/empresa-1/recibidos?periodo=2026-07",
      ),
    );
  });
});

describe("useVisorSat", () => {
  beforeEach(() => {
    vi.mocked(apiFetch).mockReset();
  });

  it("does not fetch when there is no empresaId", () => {
    renderHook(() => useVisorSat("", "2026-07"), { wrapper });
    expect(apiFetch).not.toHaveBeenCalled();
  });

  it("does not fetch when there is no periodo", () => {
    renderHook(() => useVisorSat("empresa-1", ""), { wrapper });
    expect(apiFetch).not.toHaveBeenCalled();
  });

  it("fetches with empresaId and periodo", async () => {
    vi.mocked(apiFetch).mockResolvedValue({});
    renderHook(() => useVisorSat("empresa-1", "2026-07"), { wrapper });

    await waitFor(() =>
      expect(apiFetch).toHaveBeenCalledWith(
        "/api/v1/empresas/empresa-1/cfdi/visor?periodo=2026-07",
      ),
    );
  });
});

describe("useNominaCfdi", () => {
  beforeEach(() => {
    vi.mocked(apiFetch).mockReset();
  });

  it("does not fetch when there is no empresaId", () => {
    renderHook(() => useNominaCfdi("", "2026-07"), { wrapper });
    expect(apiFetch).not.toHaveBeenCalled();
  });

  it("does not fetch when there is no periodo", () => {
    renderHook(() => useNominaCfdi("empresa-1", ""), { wrapper });
    expect(apiFetch).not.toHaveBeenCalled();
  });

  it("fetches with empresaId and periodo", async () => {
    vi.mocked(apiFetch).mockResolvedValue({});
    renderHook(() => useNominaCfdi("empresa-1", "2026-07"), { wrapper });

    await waitFor(() =>
      expect(apiFetch).toHaveBeenCalledWith(
        "/api/v1/empresas/empresa-1/cfdi/nomina?periodo=2026-07",
      ),
    );
  });
});
