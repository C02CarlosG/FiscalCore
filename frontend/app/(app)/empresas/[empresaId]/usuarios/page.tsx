"use client";

import { useParams } from "next/navigation";
import { UsuariosEmpresa } from "@/components/cuenta/UsuariosEmpresa";
import { PageHeader } from "@/components/shared/PageHeader";

export default function UsuariosPage() {
  const params = useParams<{ empresaId: string }>();
  return (
    <main className="space-y-7">
      <PageHeader
        eyebrow="Configuración"
        title="Usuarios"
        description="Quién tiene acceso a esta empresa y con qué rol."
      />
      <UsuariosEmpresa empresaId={params.empresaId} />
    </main>
  );
}
