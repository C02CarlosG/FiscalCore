import Link from "next/link";
import type { Empresa } from "@/types/api";

export function EmpresaList({ empresas }: { empresas: Empresa[] }) {
  if (empresas.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        Aún no hay empresas registradas.
      </p>
    );
  }

  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="border-b text-left">
          <th className="py-2">RFC</th>
          <th className="py-2">Razón social</th>
          <th className="py-2">Régimen fiscal</th>
          <th className="py-2"></th>
        </tr>
      </thead>
      <tbody>
        {empresas.map((empresa) => (
          <tr key={empresa.id} className="border-b">
            <td className="py-2">{empresa.rfc}</td>
            <td className="py-2">{empresa.razon_social}</td>
            <td className="py-2">{empresa.regimen_fiscal ?? "—"}</td>
            <td className="py-2">
              <Link
                className="text-blue-600 hover:underline"
                href={`/empresas/${empresa.id}/cedula-iva`}
              >
                Cédula de IVA
              </Link>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
