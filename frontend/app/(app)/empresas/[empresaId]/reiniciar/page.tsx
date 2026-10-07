"use client";

import { useParams } from "next/navigation";
import { ReiniciarDatos } from "@/components/reinicio/ReiniciarDatos";
import { PageHeader } from "@/components/shared/PageHeader";

export default function ReiniciarPage() {
  const params = useParams<{ empresaId: string }>();
  return (
    <main className="space-y-7">
      <PageHeader
        eyebrow="Configuración"
        title="Reiniciar datos"
        description="Borra los datos operativos de la empresa para empezar de cero."
      />
      <ReiniciarDatos empresaId={params.empresaId} />
    </main>
  );
}
