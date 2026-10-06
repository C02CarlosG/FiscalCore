import { formatearFecha, formatearMoneda } from "@/lib/formato";
import type { PagoSuscripcion } from "./tipos";

/** Pagos registrados a mano (D10); `conRegistro` agrega quién lo registró (solo admin). */
export function PagosTabla({ pagos, conRegistro = false }: { pagos: PagoSuscripcion[]; conRegistro?: boolean }) {
  if (pagos.length === 0) return <p className="text-sm text-muted-foreground">Aún no hay pagos registrados.</p>;
  return (
    <div className="overflow-x-auto rounded-md border border-border">
      <table aria-label="Pagos de la suscripción" className="w-full text-sm">
        <thead className="bg-muted/50 text-left text-xs text-muted-foreground">
          <tr>
            <th className="px-3 py-2 font-semibold">Fecha</th>
            <th className="px-3 py-2 text-right font-semibold">Monto</th>
            <th className="px-3 py-2 font-semibold">Referencia</th>
            <th className="px-3 py-2 font-semibold">Folio del CFDI</th>
            {conRegistro && <th className="px-3 py-2 font-semibold">Registró</th>}
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {pagos.map((p) => (
            <tr key={p.id}>
              <td className="px-3 py-2">{formatearFecha(p.fecha)}</td>
              <td className="px-3 py-2 text-right">{formatearMoneda(Number(p.monto))}</td>
              <td className="px-3 py-2">{p.referencia ?? "—"}</td>
              <td className="px-3 py-2">{p.folio_cfdi ?? "Sin CFDI"}</td>
              {conRegistro && <td className="px-3 py-2">{p.registrado_por ?? "—"}</td>}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
