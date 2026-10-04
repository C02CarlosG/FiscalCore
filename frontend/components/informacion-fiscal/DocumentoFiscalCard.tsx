"use client";

import { FormEvent, useState } from "react";
import { AlertTriangle, Download, Eye, FileCheck2, FileText, LoaderCircle, Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useSubirDocumentoFiscal } from "@/hooks/useInformacionFiscal";
import { ApiError, apiDescargar } from "@/lib/api-client";
import { guardarArchivo } from "@/lib/descarga";
import { formatearFecha, formatearInstante } from "@/lib/formato";
import { VisorPdfDialog } from "./VisorPdfDialog";
import {
  MAX_BYTES_PDF,
  rutaPdf,
  TITULO_DOCUMENTO,
  type DocumentoFiscal,
  type SentidoOpinion,
  type TipoDocumentoFiscal,
} from "./tipos";

const FILE_INPUT_CLASS =
  "h-auto min-h-11 cursor-pointer py-2 file:mr-3 file:rounded file:border-0 file:bg-primary/10 file:px-3 file:py-1.5 file:text-xs file:font-semibold file:text-primary";

const TONO = {
  ok: "border-status-ok/30 bg-status-ok-soft text-status-ok",
  aviso: "border-status-pendiente/30 bg-status-pendiente-soft text-status-pendiente",
  error: "border-status-error/30 bg-status-error-soft text-status-error",
  neutro: "border-border bg-muted text-muted-foreground",
} as const;

const SENTIDO: Record<SentidoOpinion, { texto: string; tono: keyof typeof TONO }> = {
  positivo: { texto: "Positiva", tono: "ok" },
  negativo: { texto: "Negativa", tono: "error" },
  suspension_actividades: { texto: "En suspensión de actividades", tono: "error" },
  inscrito_sin_obligaciones: { texto: "Inscrito sin obligaciones", tono: "neutro" },
  no_inscrito: { texto: "No inscrito", tono: "error" },
};

const DESCRIPCION: Record<TipoDocumentoFiscal, string> = {
  constancia: "Régimen, domicilio y obligaciones registrados en el SAT.",
  opinion: "Opinión del cumplimiento de obligaciones fiscales (32-D). La positiva vale 30 días naturales.",
};

const SUSTANTIVO: Record<TipoDocumentoFiscal, string> = {
  constancia: "la constancia",
  opinion: "la opinión",
};

function Etiqueta({ tono, children }: { tono: keyof typeof TONO; children: React.ReactNode }) {
  return (
    <span className={`inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-semibold ${TONO[tono]}`}>
      {children}
    </span>
  );
}

function Dato({ etiqueta, children }: { etiqueta: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{etiqueta}</dt>
      <dd className="text-sm">{children}</dd>
    </div>
  );
}

function EstadoOpinion({ documento }: { documento: DocumentoFiscal }) {
  const sentido = documento.datos.sentido ? SENTIDO[documento.datos.sentido] : null;
  return (
    <div className="flex flex-wrap items-center gap-2">
      {sentido ? (
        <Etiqueta tono={sentido.tono}>{sentido.texto}</Etiqueta>
      ) : (
        <Etiqueta tono="neutro">Sentido no identificado</Etiqueta>
      )}
      {documento.vigente === true && (
        <Etiqueta tono="ok">Vigente hasta {formatearFecha(documento.vigente_hasta)}</Etiqueta>
      )}
      {documento.motivo === "vencida" && (
        <Etiqueta tono="error">Vencida: valía hasta {formatearFecha(documento.vigente_hasta)}</Etiqueta>
      )}
      {documento.motivo === "sentido_no_positivo" && (
        <Etiqueta tono="error">No vigente: solo la opinión positiva tiene vigencia</Etiqueta>
      )}
      {documento.motivo === "sentido_no_identificado" && (
        <Etiqueta tono="aviso">Sin vigencia: revisa el sentido en el PDF</Etiqueta>
      )}
      {documento.motivo === "sin_fecha" && <Etiqueta tono="aviso">Sin fecha de emisión</Etiqueta>}
    </div>
  );
}

export function textoAntiguedad(dias: number | null): string {
  if (typeof dias !== "number" || dias < 0) return "";
  if (dias === 0) return " · hoy";
  return ` · hace ${dias} ${dias === 1 ? "día" : "días"}`;
}

function DetalleDocumento({ documento }: { documento: DocumentoFiscal }) {
  const { datos } = documento;
  const antiguedad = textoAntiguedad(documento.antiguedad_dias);
  return (
    <div className="space-y-4">
      {documento.tipo === "opinion" && <EstadoOpinion documento={documento} />}
      <dl className="grid grid-cols-1 gap-x-6 gap-y-3 sm:grid-cols-2">
        <Dato etiqueta="Emitida">
          {formatearFecha(documento.fecha_emision)}
          {antiguedad && <span className="text-muted-foreground">{antiguedad}</span>}
        </Dato>
        <Dato etiqueta="RFC">
          <span className="font-mono">{documento.rfc}</span>
        </Dato>
        {documento.tipo === "opinion" && datos.folio && <Dato etiqueta="Folio">{datos.folio}</Dato>}
        {documento.tipo === "constancia" && (
          <>
            {datos.estatus_padron && (
              <Dato etiqueta="Estatus en el padrón">
                {datos.estatus_padron === "ACTIVO" ? (
                  datos.estatus_padron
                ) : (
                  <Etiqueta tono="error">{datos.estatus_padron}</Etiqueta>
                )}
              </Dato>
            )}
            {datos.cp_fiscal && <Dato etiqueta="Código postal">{datos.cp_fiscal}</Dato>}
            {datos.regimenes && datos.regimenes.length > 0 && (
              <div className="sm:col-span-2">
                <dt className="text-xs text-muted-foreground">Regímenes</dt>
                <dd>
                  <ul className="list-inside list-disc text-sm">
                    {datos.regimenes.map((r) => (
                      <li key={r}>{r}</li>
                    ))}
                  </ul>
                </dd>
              </div>
            )}
          </>
        )}
        <Dato etiqueta="Subida el">{formatearInstante(documento.created_at)}</Dato>
      </dl>
      <p className="text-xs text-muted-foreground">
        Datos leídos del PDF cargado, no consultados al SAT. Verifica el folio o el código QR en el portal del SAT.
      </p>
      {documento.tipo === "constancia" && (documento.antiguedad_dias ?? 0) > 30 && (
        <p className="flex items-start gap-2 rounded-md border border-status-pendiente/30 bg-status-pendiente-soft p-3 text-sm text-status-pendiente">
          <AlertTriangle className="mt-0.5 h-4 w-4 flex-none" />
          Tiene más de 30 días; muchos bancos y clientes piden una más reciente.
        </p>
      )}
    </div>
  );
}

export function DocumentoFiscalCard({
  empresaId,
  tipo,
  documento,
}: {
  empresaId: string;
  tipo: TipoDocumentoFiscal;
  documento: DocumentoFiscal | null;
}) {
  const subir = useSubirDocumentoFiscal(empresaId, tipo);
  const [archivo, setArchivo] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [guardado, setGuardado] = useState(false);
  const [viendo, setViendo] = useState<DocumentoFiscal | null>(null);
  const [errorDescarga, setErrorDescarga] = useState(false);
  const idInput = `archivo-${tipo}`;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    setError(null);
    setGuardado(false);
    if (!archivo) {
      setError("Selecciona el PDF");
      return;
    }
    if (!archivo.name.toLowerCase().endsWith(".pdf")) {
      setError("El archivo debe ser un PDF");
      return;
    }
    if (archivo.size > MAX_BYTES_PDF) {
      setError("El PDF no puede pesar más de 5 MB");
      return;
    }
    try {
      await subir.mutateAsync(archivo);
      setGuardado(true);
      setArchivo(null);
      form.reset();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo subir el documento, intenta de nuevo");
    }
  }

  async function handleDescargar(doc: DocumentoFiscal) {
    setErrorDescarga(false);
    try {
      guardarArchivo(await apiDescargar(rutaPdf(empresaId, doc.id, true)), doc.nombre_archivo);
    } catch {
      setErrorDescarga(true);
    }
  }

  const Icono = tipo === "opinion" ? FileCheck2 : FileText;

  return (
    <Card className="overflow-hidden">
      <CardHeader className="border-b bg-muted/30 px-5 py-5 sm:px-6">
        <div className="flex items-start gap-3">
          <span className="flex h-10 w-10 flex-none items-center justify-center rounded-md bg-primary/10 text-primary">
            <Icono className="h-5 w-5" />
          </span>
          <div className="space-y-1">
            <CardTitle className="font-display text-base">{TITULO_DOCUMENTO[tipo]}</CardTitle>
            <CardDescription>{DESCRIPCION[tipo]}</CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-5 p-5 sm:p-6">
        {documento ? (
          <>
            <DetalleDocumento documento={documento} />
            <div className="flex flex-wrap gap-2">
              <Button type="button" variant="outline" size="sm" onClick={() => setViendo(documento)}>
                <Eye className="h-4 w-4" />
                Ver
              </Button>
              <Button type="button" variant="outline" size="sm" onClick={() => handleDescargar(documento)}>
                <Download className="h-4 w-4" />
                Descargar
              </Button>
            </div>
            {errorDescarga && (
              <p role="alert" className="text-sm text-destructive">
                No se pudo descargar el PDF.
              </p>
            )}
          </>
        ) : (
          <div className="rounded-md border border-dashed border-border p-4 text-sm text-muted-foreground">
            Aún no se ha subido ninguna {tipo === "opinion" ? "opinión" : "constancia"}.
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-3 border-t border-border pt-5" noValidate>
          <div className="space-y-1.5">
            <Label htmlFor={idInput}>{documento ? "Reemplazar con un PDF más reciente" : "Subir PDF"}</Label>
            <Input
              id={idInput}
              type="file"
              accept="application/pdf,.pdf"
              aria-label={`Archivo PDF de ${SUSTANTIVO[tipo]}`}
              className={FILE_INPUT_CLASS}
              onChange={(e) => setArchivo(e.target.files?.[0] ?? null)}
            />
            <p className="text-xs text-muted-foreground">
              El PDF que descargaste del SAT, hasta 5 MB. Debe ser del RFC de la empresa.
            </p>
          </div>
          {error && (
            <p role="alert" className="text-sm text-destructive">
              {error}
            </p>
          )}
          {guardado && (
            <p role="status" className="text-sm text-status-ok">
              Documento guardado
            </p>
          )}
          <Button type="submit" size="sm" disabled={subir.isPending}>
            {subir.isPending ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
            Subir
          </Button>
        </form>
      </CardContent>
      <VisorPdfDialog empresaId={empresaId} documento={viendo} onCerrar={() => setViendo(null)} />
    </Card>
  );
}
