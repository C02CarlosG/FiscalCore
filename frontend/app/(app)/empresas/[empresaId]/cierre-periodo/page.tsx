"use client";

import { Suspense } from "react";
import { CierrePeriodo } from "@/components/cierre-periodo/CierrePeriodo";
import { LoadingState } from "@/components/shared/LoadingState";

export default function CierrePeriodoPage() {
  return (
    <Suspense fallback={<LoadingState label="Cargando cierre de período" />}>
      <CierrePeriodo />
    </Suspense>
  );
}
