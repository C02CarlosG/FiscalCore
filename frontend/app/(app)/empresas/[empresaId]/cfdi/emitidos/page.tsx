"use client";

import { useParams } from "next/navigation";
import { ListadoCfdi } from "@/components/cfdi/ListadoCfdi";
import { PageHeader } from "@/components/shared/PageHeader";

export default function CfdiEmitidosPage() {
  const params = useParams<{ empresaId: string }>();

  return (
    <main className="space-y-6">
      <PageHeader
        eyebrow="CFDIs"
        title="Emitidos"
        description="Comprobantes que la empresa emitió, por tipo, estado y método de pago."
      />
      <ListadoCfdi empresaId={params.empresaId} direccion="emitidos" />
    </main>
  );
}
