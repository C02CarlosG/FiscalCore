"use client";

import Link from "next/link";
import { useRouter, usePathname } from "next/navigation";
import { useState } from "react";
import {
  ChevronDown,
  Building2,
  Calculator,
  CloudDownload,
  FileCheck2,
  FileSpreadsheet,
  FileText,
  GitBranch,
  LayoutGrid,
  LogOut,
  Upload,
} from "lucide-react";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { EmpresaSwitcher } from "@/components/layout/EmpresaSwitcher";
import { ThemeToggle } from "@/components/shared/ThemeToggle";
import { useEmpresaContext } from "@/components/providers/EmpresaProvider";
import { clearSession, loadSession } from "@/lib/auth";

const NAV_ITEMS = [
  { slug: "dashboard", label: "Dashboard", icon: LayoutGrid },
  { slug: "ingesta", label: "Ingesta", icon: Upload },
  { slug: "conciliacion", label: "Conciliación", icon: GitBranch },
  { slug: "cedula-iva", label: "Cédula de IVA", icon: FileText },
  { slug: "iva-flujo", label: "IVA base flujo", icon: Calculator },
  { slug: "sat", label: "Conexión SAT", icon: CloudDownload },
  { slug: "informacion-fiscal", label: "Información fiscal", icon: FileCheck2 },
] as const;

const CFDI_GROUP = {
  slug: "cfdi",
  label: "CFDIs",
  icon: FileSpreadsheet,
  children: [
    { slug: "cfdi/emitidos", label: "Emitidos" },
    { slug: "cfdi/recibidos", label: "Recibidos" },
  ],
} as const;

const ETIQUETA_ROL: Record<string, string> = {
  admin: "Administrador",
  contador: "Contador",
};

function isActive(pathname: string, slug: string): boolean {
  return pathname.includes(`/${slug}`);
}

function NavLink({
  href,
  disabled,
  active,
  icon: Icon,
  label,
}: {
  href: string;
  disabled: boolean;
  active: boolean;
  icon: typeof LayoutGrid;
  label: string;
}) {
  if (disabled) {
    return (
      <span className="flex cursor-not-allowed items-center gap-2.5 rounded-md px-2.5 py-2 text-sm font-medium text-muted-foreground/40">
        <Icon className="h-4 w-4" />
        {label}
      </span>
    );
  }

  return (
    <Link
      href={href}
      className={`flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm transition-colors ${
        active
          ? "bg-accent font-semibold text-accent-foreground shadow-sm"
          : "font-medium text-muted-foreground hover:bg-accent/60 hover:text-foreground"
      }`}
    >
      <Icon className="h-4 w-4" />
      {label}
    </Link>
  );
}

function CfdiNavGroup({ empresaId, pathname }: { empresaId: string | null; pathname: string }) {
  const grupoActivo = isActive(pathname, CFDI_GROUP.slug);
  const [abierto, setAbierto] = useState(grupoActivo);
  const disabled = !empresaId;

  if (disabled) {
    return (
      <span className="flex cursor-not-allowed items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm font-medium text-muted-foreground/40">
        <CFDI_GROUP.icon className="h-4 w-4" />
        {CFDI_GROUP.label}
      </span>
    );
  }

  return (
    <div>
      <button
        type="button"
        onClick={() => setAbierto((v) => !v)}
        aria-expanded={abierto || grupoActivo}
        className={`flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm font-medium transition-colors ${
          grupoActivo
            ? "text-accent-foreground"
            : "text-muted-foreground hover:bg-accent/50 hover:text-foreground"
        }`}
      >
        <CFDI_GROUP.icon className="h-4 w-4" />
        <span className="flex-1 text-left">{CFDI_GROUP.label}</span>
        <ChevronDown
          className={`h-3.5 w-3.5 flex-none transition-transform ${
            abierto || grupoActivo ? "rotate-180" : ""
          }`}
        />
      </button>
      {(abierto || grupoActivo) && (
        <div className="ml-3.5 mt-0.5 flex flex-col gap-0.5 border-l border-border pl-3">
          {CFDI_GROUP.children.map((child) => {
            const href = `/empresas/${empresaId}/${child.slug}`;
            const active = pathname === href;
            return (
              <Link
                key={child.slug}
                href={href}
                className={`rounded-lg px-2.5 py-1.5 text-sm font-medium transition-colors ${
                  active
                    ? "bg-accent text-accent-foreground"
                    : "text-muted-foreground hover:bg-accent/50 hover:text-foreground"
                }`}
              >
                {child.label}
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}

function SidebarBody() {
  const router = useRouter();
  const pathname = usePathname();
  const { empresaId } = useEmpresaContext();
  const session = typeof window !== "undefined" ? loadSession() : null;

  function handleLogout() {
    clearSession();
    router.replace("/login");
  }

  const iniciales = (session?.nombre ?? session?.email ?? "?")
    .split(" ")
    .map((p) => p[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();

  return (
      <div className="flex h-full flex-col gap-6 p-4">
      <div className="flex items-center gap-2.5 px-1 py-1 font-display text-[17px] font-bold">
        <span className="flex h-8 w-8 items-center justify-center rounded-md bg-primary text-primary-foreground shadow-sm">
          <FileText className="h-4 w-4" />
        </span>
        FiscalCore
      </div>

      <EmpresaSwitcher />

      <nav aria-label="Navegación principal" className="flex flex-1 flex-col gap-1">
        <span className="px-2.5 pb-1 text-[10px] font-bold uppercase text-muted-foreground">
          Workspace
        </span>
        <Link
          href="/empresas"
          aria-current={pathname === "/empresas" ? "page" : undefined}
          className={`flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm transition-colors ${
            pathname === "/empresas"
              ? "bg-accent font-semibold text-accent-foreground shadow-sm"
              : "font-medium text-muted-foreground hover:bg-accent/60 hover:text-foreground"
          }`}
        >
          <Building2 className="h-4 w-4" />
          Empresas
        </Link>

        <span className="px-2.5 pb-1 pt-4 text-[10px] font-bold uppercase text-muted-foreground">
          Fiscal
        </span>
        <NavLink
          href={`/empresas/${empresaId}/${NAV_ITEMS[0].slug}`}
          disabled={!empresaId}
          active={isActive(pathname, NAV_ITEMS[0].slug)}
          icon={NAV_ITEMS[0].icon}
          label={NAV_ITEMS[0].label}
        />

        <CfdiNavGroup empresaId={empresaId} pathname={pathname} />

        {NAV_ITEMS.slice(1).map((item) => (
          <NavLink
            key={item.slug}
            href={`/empresas/${empresaId}/${item.slug}`}
            disabled={!empresaId}
            active={isActive(pathname, item.slug)}
            icon={item.icon}
            label={item.label}
          />
        ))}
      </nav>

      <div className="flex flex-col gap-3 border-t border-border pt-4">
        <ThemeToggle />
        <div className="flex items-center gap-2.5 px-1">
          <span className="flex h-8 w-8 flex-none items-center justify-center rounded-full bg-gradient-to-br from-primary to-primary/60 text-xs font-bold text-primary-foreground">
            {iniciales}
          </span>
          <span className="min-w-0 flex-1">
            <span className="block truncate text-xs font-semibold">
              {session?.nombre ?? session?.email ?? "Usuario"}
            </span>
            {session?.rol && ETIQUETA_ROL[session.rol] && (
              <span className="block truncate text-[11px] text-muted-foreground">
                {ETIQUETA_ROL[session.rol]}
              </span>
            )}
          </span>
          <button
            type="button"
            onClick={handleLogout}
            aria-label="Cerrar sesión"
            className="flex-none text-muted-foreground hover:text-destructive"
          >
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );
}

interface SidebarProps {
  mobileOpen: boolean;
  onMobileOpenChange: (open: boolean) => void;
}

export function Sidebar({ mobileOpen, onMobileOpenChange }: SidebarProps) {
  return (
    <>
      <aside className="sticky top-0 hidden h-screen w-[17rem] flex-none border-r border-border bg-card lg:flex">
        <SidebarBody />
      </aside>
      <Sheet open={mobileOpen} onOpenChange={onMobileOpenChange}>
        <SheetContent side="left" className="w-64 p-0">
          <SheetTitle className="sr-only">Menú principal</SheetTitle>
          <SidebarBody />
        </SheetContent>
      </Sheet>
    </>
  );
}
