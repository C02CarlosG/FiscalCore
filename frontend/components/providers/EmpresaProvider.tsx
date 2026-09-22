"use client";

import { createContext, useContext, useEffect, useMemo } from "react";
import { useParams } from "next/navigation";
import { useEmpresas } from "@/hooks/useEmpresas";
import type { Empresa } from "@/types/api";

const LAST_EMPRESA_KEY = "fiscalcore-last-empresa";

interface EmpresaContextValue {
  empresaId: string | null;
  empresas: Empresa[];
  setLastEmpresaId: (id: string) => void;
}

const EmpresaContext = createContext<EmpresaContextValue | null>(null);

export function EmpresaProvider({ children }: { children: React.ReactNode }) {
  const params = useParams<{ empresaId?: string }>();
  const { data: empresas } = useEmpresas();
  const empresaId = params.empresaId ?? null;

  useEffect(() => {
    if (!empresaId) return;
    try {
      window.localStorage.setItem(LAST_EMPRESA_KEY, empresaId);
    } catch {
      // localStorage no disponible; el switcher simplemente no pre-selecciona.
    }
  }, [empresaId]);

  function setLastEmpresaId(id: string) {
    try {
      window.localStorage.setItem(LAST_EMPRESA_KEY, id);
    } catch {
      // no-op
    }
  }

  const value = useMemo(
    () => ({ empresaId, empresas: empresas ?? [], setLastEmpresaId }),
    [empresaId, empresas],
  );

  return (
    <EmpresaContext.Provider value={value}>{children}</EmpresaContext.Provider>
  );
}

export function useEmpresaContext(): EmpresaContextValue {
  const ctx = useContext(EmpresaContext);
  if (!ctx) {
    throw new Error("useEmpresaContext debe usarse dentro de <EmpresaProvider>");
  }
  return ctx;
}

export function readLastEmpresaId(): string | null {
  try {
    return window.localStorage.getItem(LAST_EMPRESA_KEY);
  } catch {
    return null;
  }
}
