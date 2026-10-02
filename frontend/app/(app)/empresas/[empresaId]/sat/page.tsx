"use client";

import { useParams } from "next/navigation";
import { FielCard } from "@/components/sat/FielCard";
import { DescargaSatCard } from "@/components/sat/DescargaSatCard";
import { PageHeader } from "@/components/shared/PageHeader";

export default function ConexionSatPage() {
  const params = useParams<{ empresaId: string }>();

  return (
    <main className="space-y-7">
      <PageHeader
        eyebrow="Sincronización"
        title="Conexión SAT"
        description="Guarda la e.firma de la empresa y descarga sus CFDI emitidos y recibidos directamente del SAT."
      />
      <FielCard empresaId={params.empresaId} />
      <DescargaSatCard empresaId={params.empresaId} />
    </main>
  );
}
