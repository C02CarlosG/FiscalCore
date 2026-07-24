import type { IngestaResponse } from "@/types/api";

export function IngestaResultado({ resultado }: { resultado: IngestaResponse }) {
  const plural = resultado.registros_procesados === 1 ? "" : "s";

  return (
    <div className="space-y-2 rounded-md border p-4 text-sm">
      <p>{resultado.mensaje}</p>
      <p>
        {resultado.registros_procesados} registro{plural} procesado{plural}.
      </p>
      {resultado.errores.length > 0 && (
        <ul className="list-disc space-y-1 pl-5 text-amber-700">
          {resultado.errores.map((error) => (
            <li key={error}>{error}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
