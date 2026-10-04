"use client";

import { Suspense } from "react";
import { IvaFlujoPantalla } from "@/components/iva-flujo/IvaFlujoPantalla";
import { LoadingState } from "@/components/shared/LoadingState";

export default function IvaFlujoPage() {
  return (
    <Suspense fallback={<LoadingState label="Cargando IVA" />}>
      <IvaFlujoPantalla />
    </Suspense>
  );
}
