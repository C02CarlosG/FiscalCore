"use client";

import { Suspense } from "react";
import { CfdiPantalla } from "@/components/cfdi/CfdiPantalla";
import { LoadingState } from "@/components/shared/LoadingState";

export default function CfdiRecibidosPage() {
  return (
    <Suspense fallback={<LoadingState label="Cargando CFDI" />}>
      <CfdiPantalla direccion="recibidos" />
    </Suspense>
  );
}
