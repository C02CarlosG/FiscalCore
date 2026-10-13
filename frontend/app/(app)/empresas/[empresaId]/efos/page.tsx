"use client";

import { Suspense } from "react";
import { CfdiPantalla } from "@/components/cfdi/CfdiPantalla";
import { LoadingState } from "@/components/shared/LoadingState";

export default function EfosPage() {
  return (
    <Suspense fallback={<LoadingState label="Cargando EFOS" />}>
      <CfdiPantalla direccion="recibidos" soloEfos />
    </Suspense>
  );
}
