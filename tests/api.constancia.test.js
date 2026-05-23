import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { api } from "../src/lib/api.js";

describe("api.constancia.parsear", () => {
  beforeEach(() => {
    vi.stubGlobal("localStorage", { getItem: () => null });
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({ ok: true, json: async () => ({ rfc: "XAXX010101000" }) })),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("envía el PDF en el campo 'archivo' (no 'file'), como espera el backend", async () => {
    const file = new Blob(["dummy"], { type: "application/pdf" });
    await api.constancia.parsear(file);

    expect(fetch).toHaveBeenCalledTimes(1);
    const [path, opts] = fetch.mock.calls[0];
    expect(path).toBe("/api/v1/constancia/parsear");

    const body = opts.body;
    expect(body).toBeInstanceOf(FormData);
    expect(body.get("archivo")).not.toBeNull();
    expect(body.get("file")).toBeNull();
  });
});
