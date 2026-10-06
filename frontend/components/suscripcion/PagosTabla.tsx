"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { formatearFecha, formatearMoneda } from "@/lib/formato";
import type { PagoSuscripcion } from "./tipos";

function Anular({ pago, onAnular }: { pago: PagoSuscripcion; onAnular: (motivo: string) => Promise<unknown> }) {
  const [abierto, setAbierto] = useState(false);
  const [motivo, setMotivo] = useState("");
  const [enviando, setEnviando] = useState(false);
  if (!abierto) {
    return (
      <Button type="button" size="sm" variant="ghost" aria-label={`Anular pago del ${formatearFecha(pago.fecha)}`}
              onClick={() => setAbierto(true)}>
        Anular
      </Button>
    );
  }
  return (
    <span className="flex items-center gap-1">
      <Input aria-label="Motivo de la anulación" className="h-8 w-40" value={motivo} maxLength={500}
             onChange={(e) => setMotivo(e.target.value)} />
      <Button type="button" size="sm" variant="destructive" disabled={!motivo.trim() || enviando}
              onClick={async () => {
                setEnviando(true);
                try {
                  await onAnular(motivo.trim());
                  setAbierto(false);
                } finally {
                  setEnviando(false);
                }
              }}>
        Confirmar
      </Button>
    </span>
  );
}

/**
 * Pagos registrados a mano (D10). Con `onAnular` (administrador) se ven quién registró, el
 * motivo de las anulaciones y el botón para anular.
 */
export function PagosTabla({
  pagos,
  onAnular,
}: {
  pagos: PagoSuscripcion[];
  onAnular?: (pagoId: string, motivo: string) => Promise<unknown>;
}) {
  if (pagos.length === 0) return <p className="text-sm text-muted-foreground">Aún no hay pagos registrados.</p>;
  const admin = Boolean(onAnular);
  return (
    <div className="overflow-x-auto rounded-md border border-border">
      <table aria-label="Pagos de la suscripción" className="w-full text-sm">
        <thead className="bg-muted/50 text-left text-xs text-muted-foreground">
          <tr>
            <th className="px-3 py-2 font-semibold">Fecha</th>
            <th className="px-3 py-2 text-right font-semibold">Monto</th>
            <th className="px-3 py-2 font-semibold">Meses</th>
            <th className="px-3 py-2 font-semibold">Vigencia hasta</th>
            <th className="px-3 py-2 font-semibold">Referencia</th>
            <th className="px-3 py-2 font-semibold">CFDI</th>
            {admin && <th className="px-3 py-2 font-semibold">Registró</th>}
            {admin && <th className="px-3 py-2" />}
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {pagos.map((p) => (
            <tr key={p.id} className={p.estado === "anulado" ? "text-muted-foreground" : undefined}>
              <td className="px-3 py-2">
                {formatearFecha(p.fecha)}
                {p.estado === "anulado" && (
                  <span className="ml-2 rounded border border-border px-1.5 py-0.5 text-[10px] font-medium uppercase">
                    Anulado
                  </span>
                )}
                {admin && p.motivo_anulacion && <span className="block text-xs">{p.motivo_anulacion}</span>}
              </td>
              <td className={`px-3 py-2 text-right ${p.estado === "anulado" ? "line-through" : ""}`}>
                {formatearMoneda(Number(p.monto))}
              </td>
              <td className="px-3 py-2">{p.meses}</td>
              <td className="px-3 py-2">{formatearFecha(p.vigente_hasta_nueva)}</td>
              <td className="px-3 py-2">{p.referencia ?? "—"}</td>
              <td className="px-3 py-2">
                <span className="block">{p.folio_cfdi ?? (p.uuid_cfdi ? "" : "Sin CFDI")}</span>
                {p.uuid_cfdi && <span className="block font-mono text-[11px]">{p.uuid_cfdi}</span>}
              </td>
              {admin && <td className="px-3 py-2">{p.registrado_por ?? "—"}</td>}
              {admin && (
                <td className="px-3 py-2">
                  {p.estado === "activo" && onAnular && <Anular pago={p} onAnular={(m) => onAnular(p.id, m)} />}
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
