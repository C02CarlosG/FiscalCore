"use client";

import { useEffect, useState } from "react";
import { AdminSuscripciones } from "@/components/suscripcion/AdminSuscripciones";
import { MiSuscripcion } from "@/components/suscripcion/MiSuscripcion";
import { PageHeader } from "@/components/shared/PageHeader";
import { loadSession } from "@/lib/auth";

export default function SuscripcionPage() {
  // La sección de administración solo se muestra al admin de la plataforma; el backend lo exige igual.
  const [esAdmin, setEsAdmin] = useState(false);
  useEffect(() => setEsAdmin(loadSession()?.rol === "admin"), []);

  return (
    <main className="space-y-7">
      <PageHeader eyebrow="Cuenta" title="Suscripción" description="Tu plan, cuántos RFC usas y los planes disponibles." />
      <MiSuscripcion />
      {esAdmin && <AdminSuscripciones />}
    </main>
  );
}
