"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { ErrorState } from "@/components/shared/ErrorState";
import { PageHeader } from "@/components/shared/PageHeader";
import { PeriodSelector } from "@/components/shared/PeriodSelector";
import { Skeleton } from "@/components/ui/skeleton";
import { useComparativoDeclarado, useEliminarDeclaracion, useGuardarDeclaracion } from "@/hooks/useDeclaraciones";
import { usePeriodoGlobal } from "@/hooks/usePeriodoGlobal";
import { usePeriodos } from "@/hooks/usePeriodos";
import { ApiError } from "@/lib/api-client";
import type { DeclaracionIn, ImpuestoDeclarado } from "@/types/api";
import { DeclaracionDialog } from "./DeclaracionDialog";
import { ImpuestoComparadoCard } from "./ImpuestoComparadoCard";

const mensajeDe = (e: unknown, porDefecto: string) => (e instanceof ApiError ? e.message : porDefecto);

/**
 * Comparativo contra lo declarado: lo que se capturó de cada declaración (IVA e ISR) frente a lo que calculan los motores de
 * flujo. Hasta $1.00 de diferencia es redondeo (las declaraciones van en pesos). En ISR las cifras son del mes.
 */
export function DeclaracionesPantalla() {
  const { empresaId } = useParams<{ empresaId: string }>();
  const [periodo, cambiarPeriodo] = usePeriodoGlobal(empresaId);
  const periodos = usePeriodos(empresaId);
  const comparativo = useComparativoDeclarado(empresaId, periodo);
  const guardar = useGuardarDeclaracion(empresaId, periodo);
  const eliminar = useEliminarDeclaracion(empresaId, periodo);
  const [dialogo, setDialogo] = useState<{ impuesto: ImpuestoDeclarado; tipo: "normal" | "complementaria" } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [errorAccion, setErrorAccion] = useState<string | null>(null);

  const datos = comparativo.data;

  async function confirmar(entrada: DeclaracionIn) {
    if (!dialogo) return;
    setError(null);
    try {
      await guardar.mutateAsync({ impuesto: dialogo.impuesto, datos: entrada });
      setDialogo(null);
    } catch (e) {
      setError(mensajeDe(e, "No se pudo guardar la declaración."));
    }
  }

  async function quitar(impuesto: ImpuestoDeclarado) {
    setErrorAccion(null);
    try {
      await eliminar.mutateAsync(impuesto);
    } catch (e) {
      setErrorAccion(mensajeDe(e, "No se pudo eliminar la declaración."));
    }
  }

  const abrir = (impuesto: ImpuestoDeclarado, tipo: "normal" | "complementaria") => {
    setError(null);
    setDialogo({ impuesto, tipo });
  };

  return (
    <main className="space-y-6">
      <PageHeader
        eyebrow="Impuestos"
        title="Declaraciones"
        description="Lo que se declaró y pagó de IVA e ISR contra lo que calcula el flujo, con la diferencia por concepto."
      />

      <PeriodSelector value={periodo} onChange={cambiarPeriodo} periodosConDatos={periodos.data?.periodos ?? []} />

      {comparativo.isError && !datos ? (
        <ErrorState message="No se pudo cargar el comparativo del periodo." onRetry={() => comparativo.refetch()} />
      ) : !datos ? (
        <Skeleton role="status" aria-label="Cargando comparativo" className="h-80 rounded-md" />
      ) : (
        <>
          {errorAccion && <p role="alert" className="text-sm text-destructive">{errorAccion}</p>}
          <p className="text-xs text-muted-foreground">
            {datos.aviso} En ISR se comparan las cifras del mes. Hasta $1.00 de diferencia cuenta como redondeo.
          </p>
          <div className="grid gap-4 xl:grid-cols-2">
            {(["iva", "isr"] as const).map((impuesto) => (
              <ImpuestoComparadoCard
                key={impuesto}
                datos={datos[impuesto]}
                onCapturar={() => abrir(impuesto, "normal")}
                onComplementaria={() => abrir(impuesto, "complementaria")}
                onEliminar={() => quitar(impuesto)}
              />
            ))}
          </div>
        </>
      )}

      <DeclaracionDialog
        abierto={dialogo !== null}
        impuesto={dialogo?.impuesto ?? "iva"}
        periodo={periodo}
        tipo={dialogo?.tipo ?? "normal"}
        vigente={dialogo && datos ? datos[dialogo.impuesto].declaracion : null}
        enviando={guardar.isPending}
        error={error}
        onGuardar={confirmar}
        onCerrar={() => setDialogo(null)}
      />
    </main>
  );
}
