"use client";

import { CambiarContrasenaForm } from "@/components/cuenta/CambiarContrasenaForm";
import { MisInvitaciones } from "@/components/cuenta/MisInvitaciones";
import { PerfilForm } from "@/components/cuenta/PerfilForm";
import { PageHeader } from "@/components/shared/PageHeader";

export default function PerfilPage() {
  return (
    <main className="space-y-7">
      <PageHeader eyebrow="Cuenta" title="Mi perfil" description="Tus datos como contador y tu contraseña." />
      <MisInvitaciones />
      <PerfilForm />
      <CambiarContrasenaForm />
    </main>
  );
}
