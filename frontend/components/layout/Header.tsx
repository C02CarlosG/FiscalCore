"use client";

import { useEffect, useRef, useState } from "react";
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
  cfdi: "Visor SAT",
  emitidos: "CFDI Emitidos",
  recibidos: "CFDI Recibidos",
  nomina: "CFDI Nómina",
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
  const [activeIndex, setActiveIndex] = useState(-1);
  const searchRef = useRef<HTMLDivElement>(null);
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

  useEffect(() => {
    setActiveIndex(-1);
  }, [query]);

  useEffect(() => {
    if (resultados.length === 0) return;
    function handleClickOutside(event: MouseEvent) {
      if (searchRef.current && !searchRef.current.contains(event.target as Node)) {
        setQuery("");
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resultados.length]);

  function seleccionarEmpresa(empresaId: string) {
    setQuery("");
    setActiveIndex(-1);
    router.push(`/empresas/${empresaId}/dashboard`);
  }

  function handleSearchKeyDown(event: React.KeyboardEvent<HTMLInputElement>) {
    if (resultados.length === 0) return;
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActiveIndex((i) => (i + 1) % resultados.length);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveIndex((i) => (i <= 0 ? resultados.length - 1 : i - 1));
    } else if (event.key === "Enter") {
      if (activeIndex >= 0 && resultados[activeIndex]) {
        event.preventDefault();
        seleccionarEmpresa(resultados[activeIndex].id);
      }
    } else if (event.key === "Escape") {
      setQuery("");
      setActiveIndex(-1);
    }
  }

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

      <div ref={searchRef} className="relative ml-auto hidden max-w-xs flex-1 sm:block">
        <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
        <input
          type="text"
          role="combobox"
          aria-expanded={resultados.length > 0}
          aria-controls="empresa-search-listbox"
          aria-activedescendant={
            activeIndex >= 0 && resultados[activeIndex]
              ? `empresa-option-${resultados[activeIndex].id}`
              : undefined
          }
          placeholder="Buscar empresa, RFC…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleSearchKeyDown}
          className="w-full rounded-lg border border-border bg-background py-1.5 pl-8 pr-3 text-sm outline-none focus:ring-1 focus:ring-ring"
        />
        {resultados.length > 0 && (
          <ul
            id="empresa-search-listbox"
            role="listbox"
            className="absolute left-0 right-0 top-full z-20 mt-1 rounded-lg border border-border bg-popover p-1 shadow-md"
          >
            {resultados.map((empresa, index) => (
              <li key={empresa.id} role="presentation">
                <button
                  type="button"
                  id={`empresa-option-${empresa.id}`}
                  role="option"
                  aria-selected={index === activeIndex}
                  onClick={() => seleccionarEmpresa(empresa.id)}
                  className={`w-full rounded-md px-2 py-1.5 text-left text-sm hover:bg-accent ${
                    index === activeIndex ? "bg-accent" : ""
                  }`}
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
