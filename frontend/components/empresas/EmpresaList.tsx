"use client";

import Link from "next/link";
import { MoreHorizontal } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { DataTable, type DataTableColumn } from "@/components/shared/DataTable";
import type { Empresa } from "@/types/api";

const columns: DataTableColumn<Empresa>[] = [
  {
    key: "rfc",
    header: "RFC",
    cell: (e) => <span className="font-mono">{e.rfc}</span>,
    sortValue: (e) => e.rfc,
  },
  {
    key: "razon_social",
    header: "Razón social",
    cell: (e) => e.razon_social,
    sortValue: (e) => e.razon_social,
    searchable: true,
  },
  {
    key: "regimen_fiscal",
    header: "Régimen fiscal",
    cell: (e) => e.regimen_fiscal ?? "—",
  },
  {
    key: "acciones",
    header: "",
    cell: (empresa) => (
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button
            type="button"
            aria-label={`Acciones para ${empresa.razon_social}`}
            className="rounded-md p-1.5 text-muted-foreground hover:bg-accent hover:text-foreground"
          >
            <MoreHorizontal className="h-4 w-4" />
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem asChild>
            <Link href={`/empresas/${empresa.id}/ingesta`}>Ingesta</Link>
          </DropdownMenuItem>
          <DropdownMenuItem asChild>
            <Link href={`/empresas/${empresa.id}/cedula-iva`}>Cédula de IVA</Link>
          </DropdownMenuItem>
          <DropdownMenuItem asChild>
            <Link href={`/empresas/${empresa.id}/conciliacion`}>Conciliación</Link>
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    ),
  },
];

export function EmpresaList({ empresas }: { empresas: Empresa[] }) {
  return (
    <DataTable
      data={empresas}
      columns={columns}
      getRowId={(e) => e.id}
      searchPlaceholder="Buscar por RFC o razón social..."
      emptyMessage="Aún no hay empresas registradas."
    />
  );
}
