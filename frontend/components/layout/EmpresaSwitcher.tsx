"use client";

import { useRouter, usePathname } from "next/navigation";
import { Building2, ChevronsUpDown } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useEmpresaContext } from "@/components/providers/EmpresaProvider";

const SUB_RUTAS = ["dashboard", "ingesta", "conciliacion", "cedula-iva"];

function resolverDestino(pathname: string, empresaId: string, nuevoId: string): string {
  const segmentos = pathname.split("/").filter(Boolean);
  const idx = segmentos.indexOf(empresaId);
  const subRuta = idx >= 0 ? segmentos[idx + 1] : undefined;
  const destino = subRuta && SUB_RUTAS.includes(subRuta) ? subRuta : "dashboard";
  return `/empresas/${nuevoId}/${destino}`;
}

export function EmpresaSwitcher() {
  const router = useRouter();
  const pathname = usePathname();
  const { empresaId, empresas, setLastEmpresaId } = useEmpresaContext();

  const activa = empresas.find((e) => e.id === empresaId);

  function elegir(id: string) {
    setLastEmpresaId(id);
    router.push(resolverDestino(pathname, empresaId ?? "", id));
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          className="flex w-full items-center gap-2.5 rounded-xl border border-border bg-card px-2.5 py-2 text-left hover:bg-accent"
        >
          <span className="flex h-8 w-8 flex-none items-center justify-center rounded-lg bg-accent text-xs font-bold text-accent-foreground">
            {activa ? activa.razon_social.slice(0, 2).toUpperCase() : <Building2 className="h-4 w-4" />}
          </span>
          <span className="min-w-0 flex-1">
            <span className="block truncate text-sm font-semibold">
              {activa ? activa.razon_social : "Selecciona una empresa"}
            </span>
            {activa && (
              <span className="block truncate font-mono text-xs text-muted-foreground">
                {activa.rfc}
              </span>
            )}
          </span>
          <ChevronsUpDown className="h-4 w-4 flex-none text-muted-foreground" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-64">
        {empresas.map((empresa) => (
          <DropdownMenuItem key={empresa.id} onSelect={() => elegir(empresa.id)}>
            <span className="truncate">{empresa.razon_social}</span>
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
