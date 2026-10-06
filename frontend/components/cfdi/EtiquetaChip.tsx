import type { EtiquetaCfdi } from "@/types/api";

/** Texto negro o blanco según el brillo del color de fondo, para que siempre se lea. */
function textoSobre(color: string): string {
  const n = parseInt(color.slice(1), 16);
  const luz = ((n >> 16) * 299 + ((n >> 8) & 255) * 587 + (n & 255) * 114) / 1000;
  return luz > 150 ? "#111827" : "#ffffff";
}

export function EtiquetaChip({ etiqueta }: { etiqueta: EtiquetaCfdi }) {
  return (
    <span
      className="inline-flex max-w-[10rem] items-center truncate rounded-full px-2 py-0.5 text-[11px] font-medium"
      style={{ backgroundColor: etiqueta.color, color: textoSobre(etiqueta.color) }}
      title={etiqueta.nombre}
    >
      {etiqueta.nombre}
    </span>
  );
}
