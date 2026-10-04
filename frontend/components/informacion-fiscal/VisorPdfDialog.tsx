"use client";

import { useEffect, useState } from "react";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { ErrorState } from "@/components/shared/ErrorState";
import { apiDescargar } from "@/lib/api-client";
import { rutaPdf, type DocumentoFiscal } from "./tipos";

/**
 * Muestra el PDF dentro de la app. El archivo se pide con la sesión (la ruta exige el
 * token, así que un `iframe` no puede apuntarle directo) y se libera al cerrar.
 */
export function VisorPdfDialog({
  empresaId,
  documento,
  onCerrar,
}: {
  empresaId: string;
  documento: DocumentoFiscal | null;
  onCerrar: () => void;
}) {
  const [url, setUrl] = useState<string | null>(null);
  const [error, setError] = useState(false);
  const documentoId = documento?.id;

  useEffect(() => {
    if (!documentoId) return;
    let vigente = true;
    let creada: string | null = null;
    setUrl(null);
    setError(false);
    apiDescargar(rutaPdf(empresaId, documentoId))
      .then((blob) => {
        if (!vigente) return;
        creada = URL.createObjectURL(new Blob([blob], { type: "application/pdf" }));
        setUrl(creada);
      })
      .catch(() => vigente && setError(true));
    return () => {
      vigente = false;
      if (creada) URL.revokeObjectURL(creada);
    };
  }, [empresaId, documentoId]);

  return (
    <Dialog open={Boolean(documento)} onOpenChange={(abierto) => !abierto && onCerrar()}>
      <DialogContent className="flex h-[90vh] max-w-4xl flex-col">
        <DialogHeader>
          <DialogTitle className="truncate pr-6">{documento?.nombre_archivo}</DialogTitle>
          <DialogDescription className="sr-only">Visor del documento PDF</DialogDescription>
        </DialogHeader>
        {error && <ErrorState message="No se pudo abrir el PDF." />}
        {!error && !url && <p className="text-sm text-muted-foreground">Cargando PDF…</p>}
        {url && (
          <iframe
            src={url}
            title={`Visor de ${documento?.nombre_archivo}`}
            className="min-h-0 w-full flex-1 rounded-md border border-border"
          />
        )}
      </DialogContent>
    </Dialog>
  );
}
