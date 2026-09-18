"use client";

import { useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import { Bell, Menu, Search } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useEmpresaContext } from "@/components/providers/EmpresaProvider";
import { clearSession, loadSession } from "@/lib/auth";

const LABELS: Record<string, string> = {
  dashboard: "Dashboard",
  empresas: "Empresas",
  cfdi: "Gestión de CFDI",
  ingesta: "Ingesta",
  conciliacion: "Conciliación",
  "cedula-iva": "Cédula de IVA",
};

function breadcrumbLabel(pathname: string): string {
  const segmentos = pathname.split("/").filter(Boolean);
  for (let i = segmentos.length - 1; i >= 0; i -= 1) {
    if (LABELS[segmentos[i]]) return LABELS[segmentos[i]];
  }
  return "Panel";
}

export function Header({ onMenuClick }: { onMenuClick: () => void }) {
  const router = useRouter();
  const pathname = usePathname();
  const { empresas } = useEmpresaContext();
  const [query, setQuery] = useState("");
  const session = typeof window !== "undefined" ? loadSession() : null;

  function handleLogout() {
    clearSession();
    router.replace("/login");
  }

  const resultados =
    query.trim().length > 0
      ? empresas.filter(
          (e) =>
            e.razon_social.toLowerCase().includes(query.toLowerCase()) ||
            e.rfc.toLowerCase().includes(query.toLowerCase()),
        )
      : [];

  const iniciales = (session?.nombre ?? session?.email ?? "?")
    .split(" ")
    .map((p) => p[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();

  return (
    <header className="flex h-14 flex-none items-center gap-4 border-b border-border bg-card px-4 lg:px-6">
      <button
        type="button"
        onClick={onMenuClick}
        aria-label="Abrir menú"
        className="text-muted-foreground lg:hidden"
      >
        <Menu className="h-5 w-5" />
      </button>

      <div className="flex items-center gap-1.5 text-sm text-muted-foreground">
        <span>Panel</span>
        <span>/</span>
        <span className="font-medium text-foreground">
          {breadcrumbLabel(pathname)}
        </span>
      </div>

      <div className="relative ml-auto hidden max-w-xs flex-1 sm:block">
        <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
        <input
          type="text"
          placeholder="Buscar empresa, RFC…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="w-full rounded-lg border border-border bg-background py-1.5 pl-8 pr-3 text-sm outline-none focus:ring-1 focus:ring-ring"
        />
        {resultados.length > 0 && (
          <ul
            role="listbox"
            className="absolute left-0 right-0 top-full z-20 mt-1 rounded-lg border border-border bg-popover p-1 shadow-md"
          >
            {resultados.map((empresa) => (
              <li key={empresa.id} role="presentation">
                <button
                  type="button"
                  role="option"
                  aria-selected={false}
                  onClick={() => {
                    setQuery("");
                    router.push(`/empresas/${empresa.id}/dashboard`);
                  }}
                  className="w-full rounded-md px-2 py-1.5 text-left text-sm hover:bg-accent"
                >
                  {empresa.razon_social}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      <button
        type="button"
        aria-label="Notificaciones"
        className="relative text-muted-foreground hover:text-foreground"
      >
        {/* Sin badge de conteo: no hay endpoint de notificaciones todavía. */}
        <Bell className="h-4.5 w-4.5" />
      </button>

      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button
            type="button"
            aria-label={session?.nombre ?? "Cuenta"}
            className="flex h-8 w-8 flex-none items-center justify-center rounded-full bg-gradient-to-br from-primary to-primary/60 text-xs font-bold text-primary-foreground"
          >
            {iniciales}
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem disabled>Perfil</DropdownMenuItem>
          <DropdownMenuItem onSelect={handleLogout}>
            Cerrar sesión
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </header>
  );
}
