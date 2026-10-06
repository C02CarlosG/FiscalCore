"use client";

import { useRef, useState } from "react";
import { Download, Paperclip, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { EtiquetaChip } from "@/components/cfdi/EtiquetaChip";
import { NuevaEtiqueta } from "@/components/cfdi/NuevaEtiqueta";
import {
  useBorrarComentario,
  useBorrarEvidencia,
  useComentarios,
  useCrearComentario,
  useDescargarEvidencia,
  useEtiquetarLote,
  useEtiquetas,
  useEtiquetasDeCfdi,
  useEvidencias,
  useSubirEvidencia,
} from "@/hooks/useNotasCfdi";
import { formatearFechaHora } from "@/lib/formato";

export const MAX_EVIDENCIA_MB = 5;
const ACEPTADOS = ".pdf,.png,.jpg,.jpeg,.xlsx,.xml,.txt,.csv";

const mensaje = (error: unknown, defecto: string) => (error instanceof Error ? error.message : defecto);

function tamano(bytes: number): string {
  return bytes >= 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

function Titulo({ children }: { children: React.ReactNode }) {
  return <h3 className="text-xs font-bold uppercase text-muted-foreground">{children}</h3>;
}

function Etiquetas({ empresaId, uuid }: { empresaId: string; uuid: string }) {
  const catalogo = useEtiquetas(empresaId);
  const asignadas = useEtiquetasDeCfdi(empresaId, uuid);
  const lote = useEtiquetarLote(empresaId);
  const ids = new Set((asignadas.data ?? []).map((e) => e.id));

  return (
    <section className="space-y-2" aria-label="Etiquetas">
      <Titulo>Etiquetas</Titulo>
      <div className="flex flex-wrap gap-1.5">
        {(catalogo.data ?? []).map((e) => {
          const puesta = ids.has(e.id);
          return (
            <button
              key={e.id}
              type="button"
              aria-pressed={puesta}
              aria-label={`${puesta ? "Quitar" : "Agregar"} etiqueta ${e.nombre}`}
              disabled={lote.isPending}
              onClick={() => lote.mutate({ uuids: [uuid], [puesta ? "quitar" : "agregar"]: [e.id] })}
              className={`rounded-full ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
                puesta ? "" : "opacity-40 hover:opacity-80"
              }`}
            >
              <EtiquetaChip etiqueta={e} />
            </button>
          );
        })}
        {catalogo.data?.length === 0 && <p className="text-xs text-muted-foreground">Aún no hay etiquetas; crea la primera.</p>}
      </div>
      {lote.isError && <p role="alert" className="text-xs text-destructive">{mensaje(lote.error, "No se pudo etiquetar.")}</p>}
      <NuevaEtiqueta empresaId={empresaId} onCreada={(e) => lote.mutate({ uuids: [uuid], agregar: [e.id] })} />
    </section>
  );
}

function Comentarios({ empresaId, uuid }: { empresaId: string; uuid: string }) {
  const lista = useComentarios(empresaId, uuid);
  const crear = useCrearComentario(empresaId, uuid);
  const borrar = useBorrarComentario(empresaId, uuid);
  const [texto, setTexto] = useState("");

  return (
    <section className="space-y-2" aria-label="Comentarios">
      <Titulo>Comentarios</Titulo>
      <ul className="space-y-2">
        {(lista.data ?? []).map((c) => (
          <li key={c.id} className="rounded-md border p-2 text-sm">
            <p className="whitespace-pre-wrap break-words">{c.texto}</p>
            <div className="mt-1 flex items-center justify-between gap-2 text-xs text-muted-foreground">
              <span>{`${c.autor ?? "Usuario eliminado"} · ${formatearFechaHora(c.creado)}`}</span>
              {c.puede_borrar && (
                <Button type="button" variant="ghost" size="icon" className="h-6 w-6" aria-label="Borrar comentario"
                  disabled={borrar.isPending} onClick={() => borrar.mutate(c.id)}>
                  <Trash2 className="h-3.5 w-3.5" />
                </Button>
              )}
            </div>
          </li>
        ))}
      </ul>
      <form
        className="space-y-1.5"
        onSubmit={(e) => {
          e.preventDefault();
          if (texto.trim()) crear.mutate(texto.trim(), { onSuccess: () => setTexto("") });
        }}
      >
        <Textarea aria-label="Nuevo comentario" placeholder="Escribe un comentario" maxLength={2000} rows={2}
          value={texto} onChange={(e) => setTexto(e.target.value)} />
        <Button type="submit" size="sm" variant="outline" disabled={crear.isPending || !texto.trim()}>
          Comentar
        </Button>
        {crear.isError && <p role="alert" className="text-xs text-destructive">{mensaje(crear.error, "No se pudo comentar.")}</p>}
      </form>
    </section>
  );
}

function Evidencias({ empresaId, uuid }: { empresaId: string; uuid: string }) {
  const lista = useEvidencias(empresaId, uuid);
  const subir = useSubirEvidencia(empresaId, uuid);
  const borrar = useBorrarEvidencia(empresaId, uuid);
  const descargar = useDescargarEvidencia(empresaId, uuid);
  const campo = useRef<HTMLInputElement>(null);
  const [aviso, setAviso] = useState<string | null>(null);

  function elegir(archivo: File | undefined) {
    setAviso(null);
    if (!archivo) return;
    if (archivo.size > MAX_EVIDENCIA_MB * 1024 * 1024) {
      setAviso(`El archivo excede el máximo de ${MAX_EVIDENCIA_MB} MB.`);
    } else {
      subir.mutate(archivo);
    }
    if (campo.current) campo.current.value = "";
  }

  const error = aviso ?? (subir.isError ? mensaje(subir.error, "No se pudo subir el archivo.") : null)
    ?? (descargar.isError ? "No se pudo descargar el archivo." : null)
    ?? (borrar.isError ? mensaje(borrar.error, "No se pudo borrar el archivo.") : null);

  return (
    <section className="space-y-2" aria-label="Evidencias">
      <Titulo>Evidencias</Titulo>
      <ul className="space-y-1.5">
        {(lista.data ?? []).map((v) => (
          <li key={v.id} className="flex items-center justify-between gap-2 rounded-md border p-2 text-sm">
            <span className="min-w-0 truncate" title={v.nombre}>
              {v.nombre} <span className="text-xs text-muted-foreground">{`· ${tamano(v.tamano)} · ${v.autor ?? "Usuario eliminado"}`}</span>
            </span>
            <span className="flex flex-none gap-0.5">
              <Button type="button" variant="ghost" size="icon" className="h-7 w-7" aria-label={`Descargar ${v.nombre}`}
                disabled={descargar.isPending} onClick={() => descargar.mutate(v)}>
                <Download className="h-4 w-4" />
              </Button>
              {v.puede_borrar && (
                <Button type="button" variant="ghost" size="icon" className="h-7 w-7" aria-label={`Borrar ${v.nombre}`}
                  disabled={borrar.isPending} onClick={() => borrar.mutate(v.id)}>
                  <Trash2 className="h-4 w-4" />
                </Button>
              )}
            </span>
          </li>
        ))}
      </ul>
      <input ref={campo} type="file" accept={ACEPTADOS} aria-label="Adjuntar evidencia" className="sr-only"
        onChange={(e) => elegir(e.target.files?.[0])} />
      <Button type="button" size="sm" variant="outline" disabled={subir.isPending} onClick={() => campo.current?.click()}>
        <Paperclip className="mr-1.5 h-4 w-4" />
        {subir.isPending ? "Subiendo…" : "Adjuntar evidencia"}
      </Button>
      <p className="text-xs text-muted-foreground">
        {`PDF, imagen, XLSX, XML, TXT o CSV de hasta ${MAX_EVIDENCIA_MB} MB; máximo 20 por CFDI.`}
      </p>
      {error && <p role="alert" className="text-xs text-destructive">{error}</p>}
    </section>
  );
}

/** Pie del visor: etiquetas, comentarios y evidencias del CFDI. */
export function CfdiNotas({ empresaId, uuid }: { empresaId: string; uuid: string }) {
  return (
    <div className="space-y-5 border-t pt-4 print:hidden">
      <Etiquetas empresaId={empresaId} uuid={uuid} />
      <Comentarios empresaId={empresaId} uuid={uuid} />
      <Evidencias empresaId={empresaId} uuid={uuid} />
    </div>
  );
}
