"use client";

import { useState } from "react";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
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
import { PageHeader } from "@/components/shared/PageHeader";
import { LoadingState } from "@/components/shared/LoadingState";

export default function EmpresasPage() {
  const { data: empresas, isLoading, isError, refetch } = useEmpresas();
  const [open, setOpen] = useState(false);

  return (
    <main className="space-y-7">
      <PageHeader
        eyebrow="Workspace"
        title="Empresas"
        description="Entidades y registros fiscales asociados a tu cuenta."
        actions={
          <>
            {empresas && <Badge variant="secondary" className="hidden h-8 sm:inline-flex">{empresas.length} registradas</Badge>}
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
          </>
        }
      />

      {isLoading && <LoadingState label="Cargando empresas" />}
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
