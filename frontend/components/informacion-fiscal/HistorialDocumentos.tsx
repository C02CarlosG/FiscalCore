"use client";

import { useState } from "react";
import { Download, Eye, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorState } from "@/components/shared/ErrorState";
import { useEliminarDocumentoFiscal, useHistorialDocumentos } from "@/hooks/useInformacionFiscal";
import { ApiError, apiDescargar } from "@/lib/api-client";
import { guardarArchivo } from "@/lib/descarga";
import { formatearFecha, formatearInstante } from "@/lib/formato";
import { VisorPdfDialog } from "./VisorPdfDialog";
import { rutaPdf, TITULO_DOCUMENTO, type DocumentoFiscal } from "./tipos";

export function HistorialDocumentos({ empresaId }: { empresaId: string }) {
  const historial = useHistorialDocumentos(empresaId);
  const eliminar = useEliminarDocumentoFiscal(empresaId);
  const [viendo, setViendo] = useState<DocumentoFiscal | null>(null);
  const [confirmando, setConfirmando] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleEliminar(doc: DocumentoFiscal) {
    setError(null);
    try {
      await eliminar.mutateAsync(doc.id);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo eliminar el documento");
    } finally {
      setConfirmando(null);
    }
  }

  async function handleDescargar(doc: DocumentoFiscal) {
    setError(null);
    try {
      guardarArchivo(await apiDescargar(rutaPdf(empresaId, doc.id, true)), doc.nombre_archivo);
    } catch {
      setError("No se pudo descargar el PDF");
    }
  }

  return (
    <Card>
      <CardHeader className="px-5 py-5 sm:px-6">
        <CardTitle className="font-display text-base">Historial</CardTitle>
        <CardDescription>Todas las constancias y opiniones subidas, de la más reciente a la más antigua.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3 px-5 pb-5 sm:px-6">
        {historial.isLoading && <p className="text-sm text-muted-foreground">Cargando historial…</p>}
        {historial.isError && (
          <ErrorState message="No se pudo consultar el historial." onRetry={() => historial.refetch()} />
        )}
        {error && (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        )}
        {historial.data?.length === 0 && (
          <p className="text-sm text-muted-foreground">Todavía no hay documentos cargados.</p>
        )}
        {historial.data && historial.data.length > 0 && (
          <ul className="divide-y divide-border rounded-md border border-border">
            {historial.data.map((doc) => (
              <li key={doc.id} className="flex flex-col gap-2 p-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium">{doc.nombre_archivo}</p>
                  <p className="text-xs text-muted-foreground">
                    <span>{TITULO_DOCUMENTO[doc.tipo]}</span> · emitida <span>{formatearFecha(doc.fecha_emision)}</span> ·
                    subida {formatearInstante(doc.created_at)}
                  </p>
                </div>
                <div className="flex flex-none flex-wrap gap-1.5">
                  <Button type="button" variant="ghost" size="sm" aria-label={`Ver ${doc.nombre_archivo}`} onClick={() => setViendo(doc)}>
                    <Eye className="h-4 w-4" />
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    aria-label={`Descargar ${doc.nombre_archivo}`}
                    onClick={() => handleDescargar(doc)}
                  >
                    <Download className="h-4 w-4" />
                  </Button>
                  {confirmando === doc.id ? (
                    <>
                      <Button
                        type="button"
                        variant="destructive"
                        size="sm"
                        aria-label={`Confirmar eliminación de ${doc.nombre_archivo}`}
                        disabled={eliminar.isPending}
                        onClick={() => handleEliminar(doc)}
                      >
                        Eliminar
                      </Button>
                      <Button type="button" variant="outline" size="sm" onClick={() => setConfirmando(null)}>
                        Cancelar
                      </Button>
                    </>
                  ) : (
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      aria-label={`Eliminar ${doc.nombre_archivo}`}
                      onClick={() => setConfirmando(doc.id)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
      <VisorPdfDialog empresaId={empresaId} documento={viendo} onCerrar={() => setViendo(null)} />
    </Card>
  );
}
