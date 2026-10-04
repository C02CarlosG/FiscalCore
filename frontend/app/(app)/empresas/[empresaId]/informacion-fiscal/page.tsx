"use client";

import { useParams } from "next/navigation";
import { InformacionFiscalPanel } from "@/components/informacion-fiscal/InformacionFiscalPanel";
import { PageHeader } from "@/components/shared/PageHeader";

export default function InformacionFiscalPage() {
  const params = useParams<{ empresaId: string }>();

  return (
    <main className="space-y-7">
      <PageHeader
        eyebrow="Sincronización"
        title="Información fiscal"
        description="Constancia de situación fiscal y opinión de cumplimiento de la empresa: súbelas en PDF, consúltalas y descárgalas."
      />
      <InformacionFiscalPanel empresaId={params.empresaId} />
    </main>
  );
}
