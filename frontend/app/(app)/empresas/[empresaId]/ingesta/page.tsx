"use client";

import { useParams } from "next/navigation";
import { Files, Landmark } from "lucide-react";
import { CfdiUploadForm } from "@/components/ingesta/CfdiUploadForm";
import { BancoUploadForm } from "@/components/ingesta/BancoUploadForm";
import { PageHeader } from "@/components/shared/PageHeader";

export default function IngestaPage() {
  const params = useParams<{ empresaId: string }>();

  return (
    <main className="space-y-7">
      <PageHeader
        eyebrow="Carga de información"
        title="Ingesta"
        description="Importa comprobantes fiscales y estados de cuenta para el periodo correspondiente."
      />
      <section aria-label="Fuentes de datos" className="grid grid-cols-1 items-start gap-5 xl:grid-cols-2">
        <div className="flex items-center gap-2 text-xs font-semibold uppercase text-muted-foreground xl:col-span-2">
          <Files className="h-4 w-4" /> Archivos fiscales y bancarios
        </div>
        <CfdiUploadForm empresaId={params.empresaId} />
        <BancoUploadForm empresaId={params.empresaId} />
      </section>
    </main>
  );
}
