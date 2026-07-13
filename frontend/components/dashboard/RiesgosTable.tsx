import type { RiesgoAbierto } from "@/types/api";

export function RiesgosTable({ riesgos }: { riesgos: RiesgoAbierto[] }) {
  if (riesgos.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No hay riesgos abiertos en este periodo.
      </p>
    );
  }

  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="border-b text-left">
          <th className="py-2">Severidad</th>
          <th className="py-2">Riesgo</th>
          <th className="py-2">Monto afectado</th>
          <th className="py-2">Descripción</th>
        </tr>
      </thead>
      <tbody>
        {riesgos.map((riesgo) => (
          <tr key={riesgo.id} className="border-b">
            <td className="py-2 capitalize">{riesgo.severidad}</td>
            <td className="py-2">{riesgo.nombre}</td>
            <td className="py-2">
              {riesgo.monto_afectado != null
                ? `$${riesgo.monto_afectado.toLocaleString("es-MX")}`
                : "—"}
            </td>
            <td className="py-2">{riesgo.descripcion ?? "—"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
