import { AlertTriangle, CheckCircle2 } from "lucide-react";
import type { IngestaResponse } from "@/types/api";

export function IngestaResultado({ resultado }: { resultado: IngestaResponse }) {
  const plural = resultado.registros_procesados === 1 ? "" : "s";
  const sinErrores = resultado.errores.length === 0;

  return (
    <div
      className={`space-y-2 rounded-lg border p-4 text-sm ${
        sinErrores
          ? "border-status-ok-soft bg-status-ok-soft"
          : "border-status-pendiente-soft bg-status-pendiente-soft"
      }`}
    >
      <p className="flex items-center gap-2 font-medium">
        {sinErrores ? (
          <CheckCircle2 className="h-4 w-4 flex-none text-status-ok" />
        ) : (
          <AlertTriangle className="h-4 w-4 flex-none text-status-pendiente" />
        )}
        {resultado.mensaje}
      </p>
      <p>
        {resultado.registros_procesados} registro{plural} procesado{plural}.
      </p>
      {resultado.errores.length > 0 && (
        <ul className="list-disc space-y-1 pl-9">
          {resultado.errores.map((error) => (
            <li key={error}>{error}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
