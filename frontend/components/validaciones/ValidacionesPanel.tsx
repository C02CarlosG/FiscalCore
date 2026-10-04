"use client";

import { useState } from "react";
import { Settings } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/shared/ErrorState";
import { LoadingState } from "@/components/shared/LoadingState";
import { useResumenValidaciones } from "@/hooks/useValidacionesCfdi";
import { ConfiguracionValidacionesDialog } from "./ConfiguracionValidacionesDialog";
import { ListaCfdiDialog, type SeleccionTarjeta } from "./ListaCfdiDialog";
import { TITULO_DIRECCION, type DireccionValidacion, type TarjetaValidacion } from "./tipos";

const ENTERO = new Intl.NumberFormat("es-MX");

function Tarjeta({ tarjeta, onAbrir }: { tarjeta: TarjetaValidacion; onAbrir: () => void }) {
  const conCasos = (tarjeta.periodo ?? 0) > 0;
  return (
    <button
      type="button"
      onClick={onAbrir}
      disabled={!tarjeta.activa}
      title={tarjeta.descripcion}
      className={`flex min-h-32 flex-col justify-between rounded-md border p-4 text-left transition-colors disabled:cursor-not-allowed disabled:opacity-60 ${
        conCasos
          ? "border-status-pendiente/40 bg-status-pendiente-soft hover:border-status-pendiente"
          : "border-border bg-card hover:border-primary/40"
      }`}
    >
      <span className="text-sm font-semibold">{tarjeta.titulo}</span>
      {tarjeta.activa ? (
        <span>
          <span className="block font-display text-3xl font-bold">{ENTERO.format(tarjeta.periodo ?? 0)}</span>
          <span className="block text-xs text-muted-foreground">
            Acumulado: {ENTERO.format(tarjeta.acumulado ?? 0)}
          </span>
        </span>
      ) : (
        <span className="text-xs text-muted-foreground">Desactivada</span>
      )}
    </button>
  );
}

export function ValidacionesPanel({ empresaId, periodo }: { empresaId: string; periodo: string }) {
  const resumen = useResumenValidaciones(empresaId, periodo);
  const [seleccion, setSeleccion] = useState<SeleccionTarjeta | null>(null);
  const [configurando, setConfigurando] = useState(false);

  if (resumen.isLoading) return <LoadingState label="Revisando CFDI" />;
  if (resumen.isError || !resumen.data) {
    return <ErrorState message="No se pudieron calcular las validaciones." onRetry={() => resumen.refetch()} />;
  }

  const datos = resumen.data;
  // Una tarjeta por clave, en el orden del catálogo (recibidos trae todas).
  const catalogo = [...datos.recibidos];

  return (
    <div className="space-y-6">
      <div className="flex justify-end">
        <Button type="button" variant="outline" size="sm" onClick={() => setConfigurando(true)}>
          <Settings className="h-4 w-4" />
          Configurar validaciones
        </Button>
      </div>
      {(["emitidos", "recibidos"] as DireccionValidacion[]).map((direccion) => (
        <section key={direccion} aria-labelledby={`validaciones-${direccion}`} className="space-y-3">
          <h2 id={`validaciones-${direccion}`} className="font-display text-base font-semibold">
            {TITULO_DIRECCION[direccion]}
          </h2>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {datos[direccion].map((t) => (
              <Tarjeta key={t.clave} tarjeta={t} onAbrir={() => setSeleccion({ direccion, tarjeta: t })} />
            ))}
          </div>
        </section>
      ))}
      <ListaCfdiDialog
        empresaId={empresaId}
        periodo={periodo}
        seleccion={seleccion}
        onCerrar={() => setSeleccion(null)}
      />
      <ConfiguracionValidacionesDialog
        empresaId={empresaId}
        abierto={configurando}
        onCerrar={() => setConfigurando(false)}
        configuracion={datos.configuracion}
        validaciones={catalogo}
      />
    </div>
  );
}
