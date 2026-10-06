"use client";

import { ErrorState } from "@/components/shared/ErrorState";
import { LoadingState } from "@/components/shared/LoadingState";
import { useResumenInformacionFiscal } from "@/hooks/useInformacionFiscal";
import { DocumentoFiscalCard } from "./DocumentoFiscalCard";
import { HistorialDocumentos } from "./HistorialDocumentos";
import { RegimenEmpresaCard } from "./RegimenEmpresaCard";

export function InformacionFiscalPanel({ empresaId }: { empresaId: string }) {
  const resumen = useResumenInformacionFiscal(empresaId);

  if (resumen.isLoading) return <LoadingState label="Consultando información fiscal" />;
  if (resumen.isError || !resumen.data) {
    return (
      <ErrorState
        message="No se pudo consultar la información fiscal de la empresa."
        onRetry={() => resumen.refetch()}
      />
    );
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <DocumentoFiscalCard empresaId={empresaId} tipo="opinion" documento={resumen.data.opinion} />
        <DocumentoFiscalCard empresaId={empresaId} tipo="constancia" documento={resumen.data.constancia} />
      </div>
      <RegimenEmpresaCard empresaId={empresaId} />
      <HistorialDocumentos empresaId={empresaId} />
    </div>
  );
}
