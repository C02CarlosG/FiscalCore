"use client";

import { EmpresaForm } from "@/components/empresas/EmpresaForm";
import { EmpresaList } from "@/components/empresas/EmpresaList";
import { ErrorState } from "@/components/shared/ErrorState";
import { useEmpresas } from "@/hooks/useEmpresas";

export default function EmpresasPage() {
  const { data: empresas, isLoading, isError, refetch } = useEmpresas();

  return (
    <main className="mx-auto max-w-3xl space-y-6 p-6">
      <h1 className="text-2xl font-semibold">Empresas</h1>

      <EmpresaForm />

      {isLoading && <p>Cargando empresas...</p>}
      {isError && (
        <ErrorState
          message="No se pudieron cargar las empresas."
          onRetry={() => refetch()}
        />
      )}
      {empresas && <EmpresaList empresas={empresas} />}
    </main>
  );
}
