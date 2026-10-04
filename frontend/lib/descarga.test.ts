import { afterEach, describe, expect, it, vi } from "vitest";
import { guardarArchivo } from "./descarga";

describe("guardarArchivo", () => {
  afterEach(() => vi.restoreAllMocks());

  it("dispara la descarga con el nombre indicado y libera la URL", () => {
    const crear = vi.fn().mockReturnValue("blob:abc");
    const revocar = vi.fn();
    Object.assign(URL, { createObjectURL: crear, revokeObjectURL: revocar });
    const clic = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) {
      expect(this.download).toBe("U-1.xml");
      expect(this.href).toBe("blob:abc");
    });
    const blob = new Blob(["<x/>"]);

    guardarArchivo(blob, "U-1.xml");

    expect(crear).toHaveBeenCalledWith(blob);
    expect(clic).toHaveBeenCalledTimes(1);
    expect(revocar).toHaveBeenCalledWith("blob:abc");
    expect(document.querySelector("a[download]")).toBeNull();
  });
});
