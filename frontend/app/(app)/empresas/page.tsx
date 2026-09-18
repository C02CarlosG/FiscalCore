"use client";

import { useState } from "react";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { EmpresaForm } from "@/components/empresas/EmpresaForm";
import { EmpresaList } from "@/components/empresas/EmpresaList";
import { ErrorState } from "@/components/shared/ErrorState";
import { useEmpresas } from "@/hooks/useEmpresas";

export default function EmpresasPage() {
  const { data: empresas, isLoading, isError, refetch } = useEmpresas();
  const [open, setOpen] = useState(false);

  return (
    <main className="mx-auto max-w-4xl space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Empresas</h1>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button>
              <Plus className="h-4 w-4" />
              Nueva empresa
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Agregar empresa</DialogTitle>
            </DialogHeader>
            <EmpresaForm onCreated={() => setOpen(false)} />
          </DialogContent>
        </Dialog>
      </div>

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
