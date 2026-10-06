"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import { ChevronRight, Menu, Search } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useEmpresaContext } from "@/components/providers/EmpresaProvider";
import { clearSession, loadSession } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";

const LABELS: Record<string, string> = {
  dashboard: "Dashboard",
  empresas: "Empresas",
  cfdi: "CFDIs",
  emitidos: "CFDI Emitidos",
  recibidos: "CFDI Recibidos",
  ingesta: "Ingesta",
  conciliacion: "Conciliación",
  "cedula-iva": "Cédula de IVA",
  "iva-flujo": "IVA base flujo",
  diot: "DIOT por flujo",
  sat: "Conexión SAT",
  "informacion-fiscal": "Información fiscal",
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
    <header className="sticky top-0 z-30 flex h-16 flex-none items-center gap-3 border-b border-border bg-background/95 px-4 backdrop-blur-sm sm:gap-5 sm:px-6 lg:px-8">
      <Button
        type="button"
        onClick={onMenuClick}
        aria-label="Abrir menú"
        variant="ghost"
        size="icon"
        className="shrink-0 lg:hidden"
      >
        <Menu className="h-5 w-5" />
      </Button>

      <nav aria-label="Breadcrumb" className="flex min-w-0 items-center gap-1.5 text-sm">
        <span className="hidden text-muted-foreground sm:inline">Panel</span>
        <ChevronRight className="hidden h-3.5 w-3.5 text-muted-foreground sm:block" />
        <span className="truncate font-semibold text-foreground">
          {breadcrumbLabel(pathname)}
        </span>
      </nav>

      <div ref={searchRef} className="relative ml-auto hidden max-w-sm flex-1 md:block">
        <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
        <Input
          type="text"
          role="combobox"
          aria-expanded={resultados.length > 0}
          aria-controls="empresa-search-listbox"
          aria-activedescendant={
            activeIndex >= 0 && resultados[activeIndex]
              ? `empresa-option-${resultados[activeIndex].id}`
              : undefined
          }
          placeholder="Buscar empresa o RFC"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleSearchKeyDown}
          className="h-9 w-full border-transparent bg-muted/70 pl-8 pr-3 shadow-none focus-visible:border-ring focus-visible:bg-background"
        />
        {resultados.length > 0 && (
          <ul
            id="empresa-search-listbox"
            role="listbox"
            className="absolute left-0 right-0 top-full z-40 mt-2 rounded-md border border-border bg-popover p-1.5 shadow-lg"
          >
            {resultados.map((empresa, index) => (
              <li key={empresa.id} role="presentation">
                <button
                  type="button"
                  id={`empresa-option-${empresa.id}`}
                  role="option"
                  aria-selected={index === activeIndex}
                  onClick={() => seleccionarEmpresa(empresa.id)}
                  className={`w-full rounded px-2.5 py-2 text-left text-sm hover:bg-accent ${
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

      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button
            type="button"
            aria-label={session?.nombre ?? "Cuenta"}
          >
            <Avatar className="h-9 w-9 border border-border">
              <AvatarFallback className="bg-accent text-xs font-bold text-accent-foreground">
                {iniciales}
              </AvatarFallback>
            </Avatar>
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
