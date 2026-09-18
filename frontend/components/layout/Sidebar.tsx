"use client";

import Link from "next/link";
import { useRouter, usePathname } from "next/navigation";
import {
  FileSpreadsheet,
  FileText,
  GitBranch,
  LayoutGrid,
  LogOut,
  Upload,
} from "lucide-react";
import { Sheet, SheetContent } from "@/components/ui/sheet";
import { EmpresaSwitcher } from "@/components/layout/EmpresaSwitcher";
import { ThemeToggle } from "@/components/shared/ThemeToggle";
import { useEmpresaContext } from "@/components/providers/EmpresaProvider";
import { clearSession, loadSession } from "@/lib/auth";

const NAV_ITEMS = [
  { slug: "dashboard", label: "Dashboard", icon: LayoutGrid, requiresEmpresa: true },
  { slug: "cfdi", label: "Gestión de CFDI", icon: FileSpreadsheet, requiresEmpresa: true },
  { slug: "ingesta", label: "Ingesta", icon: Upload, requiresEmpresa: true },
  { slug: "conciliacion", label: "Conciliación", icon: GitBranch, requiresEmpresa: true },
  { slug: "cedula-iva", label: "Cédula de IVA", icon: FileText, requiresEmpresa: true },
] as const;

function isActive(pathname: string, slug: string): boolean {
  return pathname.includes(`/${slug}`);
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
    <div className="flex h-full flex-col gap-5 p-3.5">
      <div className="flex items-center gap-2 px-1.5 py-1 font-display text-[17px] font-bold">
        <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-primary text-primary-foreground">
          <FileText className="h-4 w-4" />
        </span>
        FiscalCore
      </div>

      <EmpresaSwitcher />

      <nav className="flex flex-1 flex-col gap-0.5">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const disabled = item.requiresEmpresa && !empresaId;
          const href = `/empresas/${empresaId}/${item.slug}`;
          const active = isActive(pathname, item.slug);

          if (disabled) {
            return (
              <span
                key={item.slug}
                className="flex cursor-not-allowed items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm font-medium text-muted-foreground/40"
              >
                <Icon className="h-4 w-4" />
                {item.label}
              </span>
            );
          }

          return (
            <Link
              key={item.slug}
              href={href}
              className={`flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm font-medium transition-colors ${
                active
                  ? "bg-accent text-accent-foreground"
                  : "text-muted-foreground hover:bg-accent/50 hover:text-foreground"
              }`}
            >
              <Icon className="h-4 w-4" />
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="flex flex-col gap-2.5 border-t border-border pt-3.5">
        <ThemeToggle />
        <div className="flex items-center gap-2.5 px-1">
          <span className="flex h-8 w-8 flex-none items-center justify-center rounded-full bg-gradient-to-br from-primary to-primary/60 text-xs font-bold text-primary-foreground">
            {iniciales}
          </span>
          <span className="min-w-0 flex-1">
            <span className="block truncate text-xs font-semibold">
              {session?.nombre ?? session?.email ?? "Usuario"}
            </span>
            <span className="block truncate text-[11px] text-muted-foreground">
              Contador
            </span>
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
      <aside className="hidden w-64 flex-none border-r border-border bg-card lg:flex">
        <SidebarBody />
      </aside>
      <Sheet open={mobileOpen} onOpenChange={onMobileOpenChange}>
        <SheetContent side="left" className="w-64 p-0">
          <SidebarBody />
        </SheetContent>
      </Sheet>
    </>
  );
}
