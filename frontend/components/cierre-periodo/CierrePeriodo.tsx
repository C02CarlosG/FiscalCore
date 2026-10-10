"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { Download, RotateCcw, Lock } from "lucide-react";
import { ErrorState } from "@/components/shared/ErrorState";
import { PageHeader } from "@/components/shared/PageHeader";
import { PeriodSelector } from "@/components/shared/PeriodSelector";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { AlertCircle, CheckCircle2, XCircle } from "lucide-react";
import { useCierre } from "@/hooks/useCierre";
import { usePeriodoGlobal } from "@/hooks/usePeriodoGlobal";
import { usePeriodos } from "@/hooks/usePeriodos";
import { ApiError } from "@/lib/api-client";
import { guardarArchivo } from "@/lib/descarga";
import { ModalValidacionesYCierre } from "./ModalValidacionesYCierre";

const mensajeDe = (e: unknown, porDefecto: string) => (e instanceof ApiError ? e.message : porDefecto);

/**
 * Cierre de período fiscal: descarga del papel de trabajo y cierre de período con validaciones obligatorias y recomendaciones.
 */
export function CierrePeriodo() {
  const { empresaId } = useParams<{ empresaId: string }>();
  const [periodo, cambiarPeriodo] = usePeriodoGlobal(empresaId);
  const periodos = usePeriodos(empresaId);
  const cierre = useCierre(empresaId, periodo);
  const [showModal, setShowModal] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const validaciones = cierre.validaciones;
  const estado = cierre.estado;
  const puedeDescargar = !!validaciones;
  const estaCerrado = estado?.cerrado && !estado?.reabierto;

  async function descargarPapelTrabajo() {
    setError(null);
    try {
      await cierre.descargarPapelTrabajo();
      setSuccess("Papel de trabajo descargado correctamente.");
      setTimeout(() => setSuccess(null), 3000);
    } catch (e) {
      setError(mensajeDe(e, "No se pudo descargar el papel de trabajo."));
    }
  }

  async function cerrarPeriodo() {
    setError(null);
    setSuccess(null);
    try {
      await cierre.cerrar();
      setShowModal(false);
      await cierre.refetchEstado();
      setSuccess("Período cerrado correctamente.");
      setTimeout(() => setSuccess(null), 3000);
    } catch (e) {
      const msg = mensajeDe(e, "No se pudo cerrar el período.");
      setError(msg);
    }
  }

  async function reabrirPeriodo() {
    setError(null);
    setSuccess(null);
    try {
      await cierre.reabrir();
      await cierre.refetchEstado();
      setSuccess("Período reabierto correctamente.");
      setTimeout(() => setSuccess(null), 3000);
    } catch (e) {
      setError(mensajeDe(e, "No se pudo reabrir el período."));
    }
  }

  return (
    <main className="space-y-6">
      <PageHeader
        eyebrow="Administración"
        title="Cierre de período"
        description="Descarga el papel de trabajo y cierra el período fiscal después de validar todos los datos."
        actions={
          !estaCerrado ? (
            <Button
              type="button"
              variant="outline"
              onClick={descargarPapelTrabajo}
              disabled={!puedeDescargar || cierre.isLoadingValidaciones}
            >
              <Download className="mr-2 h-4 w-4" />
              Descargar papel de trabajo
            </Button>
          ) : (
            <Button
              type="button"
              variant="outline"
              onClick={reabrirPeriodo}
              disabled={cierre.isReopening}
              className="text-amber-600 hover:text-amber-700"
            >
              <RotateCcw className="mr-2 h-4 w-4" />
              Reabrir período
            </Button>
          )
        }
      />

      <PeriodSelector value={periodo} onChange={cambiarPeriodo} periodosConDatos={periodos.data?.periodos ?? []} />

      {error && (
        <div className="rounded-md border border-destructive/40 bg-destructive/10 p-4">
          <p className="text-sm font-medium text-destructive">{error}</p>
        </div>
      )}

      {success && (
        <div className="rounded-md border border-green-500/40 bg-green-500/10 p-4">
          <p className="text-sm font-medium text-green-700">{success}</p>
        </div>
      )}

      {cierre.isLoadingValidaciones ? (
        <Skeleton role="status" aria-label="Cargando validaciones" className="h-96 rounded-md" />
      ) : cierre.isErrorValidaciones ? (
        <ErrorState
          message="No se pudo cargar las validaciones del período."
          onRetry={() => cierre.refetchValidaciones()}
        />
      ) : !validaciones ? null : estaCerrado ? (
        <div className="rounded-lg border border-blue-200 bg-blue-50 p-6">
          <div className="flex items-center gap-3 mb-4">
            <Lock className="h-5 w-5 text-blue-600" />
            <h3 className="font-semibold text-blue-900">Período cerrado</h3>
          </div>
          <div className="space-y-2 text-sm text-blue-800">
            <p>
              <strong>Cerrado por:</strong> {estado?.cerrado_por || "—"}
            </p>
            <p>
              <strong>Fecha de cierre:</strong> {estado?.fecha_cierre ? new Date(estado.fecha_cierre).toLocaleDateString("es-MX") : "—"}
            </p>
            {estado?.reabierto_por && (
              <>
                <p>
                  <strong>Reabierto por:</strong> {estado.reabierto_por}
                </p>
                <p>
                  <strong>Fecha de reapertura:</strong>{" "}
                  {estado.fecha_reapertura ? new Date(estado.fecha_reapertura).toLocaleDateString("es-MX") : "—"}
                </p>
              </>
            )}
          </div>
        </div>
      ) : (
        <>
          <div className="rounded-lg border bg-card p-6">
            <h3 className="mb-4 font-semibold">Validaciones</h3>
            <div className="space-y-3">
              {validaciones.validaciones.map((v) => (
                <div key={v.nombre} className="flex items-start gap-3 rounded-md bg-muted p-3">
                  <div className="flex-shrink-0 pt-0.5">
                    {v.pasó ? (
                      <CheckCircle2 className="h-5 w-5 text-green-600" />
                    ) : v.bloquea ? (
                      <XCircle className="h-5 w-5 text-red-600" />
                    ) : (
                      <AlertCircle className="h-5 w-5 text-amber-600" />
                    )}
                  </div>
                  <div className="flex-1">
                    <p className="font-medium text-sm">{v.nombre}</p>
                    <p className="text-xs text-muted-foreground">{v.mensaje}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {validaciones.puede_cerrar && (
            <div className="flex justify-end gap-2">
              <Button
                type="button"
                onClick={() => setShowModal(true)}
                disabled={cierre.isClosing}
              >
                Cerrar período
              </Button>
            </div>
          )}

          {!validaciones.puede_cerrar && (
            <div className="rounded-md border border-amber-200 bg-amber-50 p-4">
              <p className="text-sm text-amber-800">
                No se puede cerrar el período hasta que todas las validaciones obligatorias pasen.
              </p>
            </div>
          )}
        </>
      )}

      <ModalValidacionesYCierre
        open={showModal}
        onOpenChange={setShowModal}
        validaciones={validaciones?.validaciones ?? []}
        onConfirm={cerrarPeriodo}
        loading={cierre.isClosing}
      />
    </main>
  );
}
