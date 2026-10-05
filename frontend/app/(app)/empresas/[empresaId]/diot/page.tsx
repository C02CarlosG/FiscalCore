"use client";

import { Suspense } from "react";
import { DiotPantalla } from "@/components/diot/DiotPantalla";
import { LoadingState } from "@/components/shared/LoadingState";

export default function DiotPage() {
  return (
    <Suspense fallback={<LoadingState label="Cargando DIOT" />}>
      <DiotPantalla />
    </Suspense>
  );
}
