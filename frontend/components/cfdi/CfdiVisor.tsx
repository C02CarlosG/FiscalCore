"use client";

import { useState } from "react";
import { Download, Printer } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { CfdiNotas } from "@/components/cfdi/CfdiNotas";
import { ETIQUETA_TIPO } from "@/components/cfdi/CfdiTabs";
import { ErrorState } from "@/components/shared/ErrorState";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { useCfdiDetalle } from "@/hooks/useCfdis";
import { apiDescargar } from "@/lib/api-client";
import type { Tipo } from "@/lib/cfdi-url";
import { guardarArchivo } from "@/lib/descarga";
import { formatearFechaHora, formatearMoneda } from "@/lib/formato";
import type { CfdiDetalle } from "@/types/api";

const SIN_DATO = "—";
const ENTERO = new Intl.NumberFormat("es-MX", { maximumFractionDigits: 6 });

const texto = (valor: unknown): string => (valor === null || valor === undefined || valor === "" ? SIN_DATO : String(valor));
const importe = (valor: unknown): string => formatearMoneda(typeof valor === "number" ? valor : null);

function Dato({ etiqueta, children }: { etiqueta: string; children: React.ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs text-muted-foreground">{etiqueta}</dt>
      <dd className="break-words text-sm">{children}</dd>
    </div>
  );
}

function Parte({ titulo, parte, domicilio }: { titulo: string; parte: CfdiDetalle["emisor"]; domicilio: string }) {
  return (
    <section className="space-y-2 rounded-md border p-3">
      <h3 className="text-xs font-bold uppercase text-muted-foreground">{titulo}</h3>
      <dl className="space-y-2">
        <Dato etiqueta="Nombre">{texto(parte.nombre)}</Dato>
        <Dato etiqueta="RFC">{parte.rfc}</Dato>
        <Dato etiqueta="Régimen fiscal">{texto(parte.regimen_desc ?? parte.regimen)}</Dato>
        <Dato etiqueta={domicilio}>{texto(parte.domicilio_fiscal ?? null)}</Dato>
      </dl>
    </section>
  );
}

function Contenido({ detalle }: { detalle: CfdiDetalle }) {
  const e = detalle.encabezado;
  const retenciones = Number(e.iva_retenido ?? 0) + Number(e.isr_retenido ?? 0);
  const filasTotales: [string, number][] = [["Subtotal", Number(e.subtotal ?? 0)]];
  if (Number(e.descuento ?? 0) > 0) filasTotales.push(["Descuento", Number(e.descuento)]);
  if (Number(e.iva_trasladado ?? 0) > 0) filasTotales.push(["Traslados", Number(e.iva_trasladado)]);
  if (retenciones > 0) filasTotales.push(["Retenciones", retenciones]);

  return (
    <div className="space-y-5">
      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <Dato etiqueta="Folio fiscal (UUID)">{texto(e.uuid)}</Dato>
        <Dato etiqueta="Fecha de expedición">{formatearFechaHora(String(e.fecha_emision))}</Dato>
        <Dato etiqueta="Fecha de timbrado">{formatearFechaHora(e.fecha_timbrado === null ? null : String(e.fecha_timbrado))}</Dato>
        <Dato etiqueta="No. de certificado">{texto(e.no_certificado)}</Dato>
        <Dato etiqueta="Lugar de expedición">{texto(e.lugar_expedicion)}</Dato>
        <Dato etiqueta="Versión">{texto(e.version)}</Dato>
      </dl>

      <div className="grid gap-3 sm:grid-cols-2">
        <Parte titulo="Emisor" parte={detalle.emisor} domicilio="Lugar de expedición" />
        <Parte titulo="Receptor" parte={detalle.receptor} domicilio="Domicilio fiscal (C.P.)" />
      </div>

      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <Dato etiqueta="Método de pago">{texto(e.metodo_pago_desc ?? e.metodo_pago)}</Dato>
        <Dato etiqueta="Forma de pago">{texto(e.forma_pago_desc ?? e.forma_pago)}</Dato>
        <Dato etiqueta="Uso del CFDI">{texto(e.uso_cfdi_desc ?? e.uso_cfdi)}</Dato>
        <Dato etiqueta="Moneda">{texto(e.moneda)}</Dato>
        <Dato etiqueta="Tipo de cambio">{typeof e.tipo_cambio === "number" ? ENTERO.format(e.tipo_cambio) : SIN_DATO}</Dato>
        {e.saldo !== null && e.saldo !== undefined && <Dato etiqueta="Saldo por cobrar o pagar">{importe(e.saldo)}</Dato>}
      </dl>

      <section className="space-y-2">
        <h3 className="text-xs font-bold uppercase text-muted-foreground">Conceptos</h3>
        <div className="overflow-x-auto rounded-md border">
          <Table aria-label="Conceptos">
            <TableHeader>
              <TableRow>
                <TableHead>Clave</TableHead>
                <TableHead>Descripción</TableHead>
                <TableHead className="text-right">Cantidad</TableHead>
                <TableHead>Unidad</TableHead>
                <TableHead className="text-right">V. unitario</TableHead>
                <TableHead className="text-right">Importe</TableHead>
                <TableHead className="text-right">Descuento</TableHead>
                <TableHead className="text-right">IVA</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {detalle.conceptos.map((c) => (
                <TableRow key={String(c.linea)}>
                  <TableCell>{texto(c.clave_prod_serv)}</TableCell>
                  <TableCell className="min-w-48">{texto(c.descripcion)}</TableCell>
                  <TableCell className="text-right tabular-nums">{typeof c.cantidad === "number" ? ENTERO.format(c.cantidad) : SIN_DATO}</TableCell>
                  <TableCell>{texto(c.unidad ?? c.clave_unidad)}</TableCell>
                  <TableCell className="text-right tabular-nums">{importe(c.valor_unitario)}</TableCell>
                  <TableCell className="text-right tabular-nums">{importe(c.importe)}</TableCell>
                  <TableCell className="text-right tabular-nums">{importe(c.descuento)}</TableCell>
                  <TableCell className="text-right tabular-nums">{importe(c.iva_traslado_importe)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
        {detalle.total_conceptos > detalle.conceptos.length && (
          <p className="text-xs text-muted-foreground">
            {`Se muestran los primeros ${detalle.conceptos.length} de ${detalle.total_conceptos} conceptos`}
          </p>
        )}
      </section>

      <Table aria-label="Totales" className="ml-auto w-full sm:w-72">
        <TableBody>
          {filasTotales.map(([nombre, valor]) => (
            <TableRow key={nombre}>
              <TableHead scope="row" className="h-8 normal-case">{nombre}</TableHead>
              <TableCell className="py-1 text-right tabular-nums">{importe(valor)}</TableCell>
            </TableRow>
          ))}
          <TableRow className="font-semibold">
            <TableHead scope="row" className="h-8 normal-case">Total</TableHead>
            <TableCell className="py-1 text-right tabular-nums">{importe(e.total)}</TableCell>
          </TableRow>
        </TableBody>
      </Table>

      {detalle.pagos.length > 0 && (
        <section className="space-y-2">
          <h3 className="text-xs font-bold uppercase text-muted-foreground">Pagos que lo liquidan</h3>
          <div className="overflow-x-auto rounded-md border">
            <Table aria-label="Pagos aplicados">
              <TableHeader>
                <TableRow>
                  <TableHead>CFDI de pago</TableHead>
                  <TableHead>Fecha de pago</TableHead>
                  <TableHead className="text-right">Parcialidad</TableHead>
                  <TableHead className="text-right">Importe pagado</TableHead>
                  <TableHead className="text-right">Saldo restante</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {detalle.pagos.map((p) => (
                  <TableRow key={`${p.uuid_pago}-${p.parcialidad}-${p.fecha_pago}`}>
                    <TableCell className="font-mono text-xs">{p.uuid_pago}</TableCell>
                    <TableCell>{formatearFechaHora(p.fecha_pago)}</TableCell>
                    <TableCell className="text-right tabular-nums">{texto(p.parcialidad)}</TableCell>
                    <TableCell className="text-right tabular-nums">{importe(p.importe_pagado)}</TableCell>
                    <TableCell className="text-right tabular-nums">{importe(p.saldo_restante)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </section>
      )}

      {detalle.relacionados.length > 0 && (
        <section className="space-y-2">
          <h3 className="text-xs font-bold uppercase text-muted-foreground">CFDI relacionados</h3>
          {detalle.relacionados.map((r) => (
            <div key={r.tipo_relacion} className="rounded-md border p-3 text-sm">
              <p className="font-medium">{texto(r.descripcion)}</p>
              <ul className="mt-1 space-y-0.5 font-mono text-xs">
                {r.uuids.map((u) => (
                  <li key={u}>{u}</li>
                ))}
              </ul>
            </div>
          ))}
        </section>
      )}
    </div>
  );
}

/**
 * Visor de un CFDI en una ventana: datos del comprobante, partes, conceptos, totales,
 * pagos y relacionados. Permite descargar el XML e imprimir (la hoja de estilos de
 * impresión deja solo esta ventana; el usuario la guarda como PDF desde el navegador).
 */
export function CfdiVisor({
  empresaId,
  uuid,
  onCerrar,
}: {
  empresaId: string;
  uuid: string | null;
  onCerrar: () => void;
}) {
  const consulta = useCfdiDetalle(empresaId, uuid);
  const [errorXml, setErrorXml] = useState(false);
  const detalle = consulta.data;

  async function descargarXml() {
    if (!uuid) return;
    setErrorXml(false);
    try {
      const archivo = await apiDescargar(`/api/v1/empresas/${empresaId}/cfdis/${encodeURIComponent(uuid)}/xml`);
      guardarArchivo(archivo, `${uuid}.xml`);
    } catch {
      setErrorXml(true);
    }
  }

  const tipo = detalle ? ETIQUETA_TIPO[detalle.encabezado.tipo_comprobante as Tipo] ?? "CFDI" : "CFDI";
  const folio = detalle
    ? [detalle.encabezado.serie, detalle.encabezado.folio].filter(Boolean).join("-")
    : "";

  return (
    <Dialog open={Boolean(uuid)} onOpenChange={(abierto) => !abierto && onCerrar()}>
      <DialogContent className="cfdi-visor max-h-[90vh] max-w-4xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex flex-wrap items-center gap-2">
            <span>{folio ? `${tipo} ${folio}` : tipo}</span>
            {detalle && <StatusBadge status={String(detalle.encabezado.estado)} />}
          </DialogTitle>
          <DialogDescription className="sr-only">Detalle del comprobante fiscal</DialogDescription>
        </DialogHeader>

        {consulta.isError && !detalle ? (
          <ErrorState message="No se pudo cargar el CFDI." onRetry={() => consulta.refetch()} />
        ) : !detalle ? (
          <Skeleton role="status" aria-label="Cargando CFDI" className="h-64 rounded-md" />
        ) : (
          <>
            <Contenido detalle={detalle} />
            {uuid && <CfdiNotas empresaId={empresaId} uuid={uuid} />}
            {errorXml && (
              <p role="alert" className="text-sm text-destructive">
                No se pudo descargar el XML.
              </p>
            )}
            <div className="flex flex-wrap justify-end gap-2 print:hidden">
              <Button type="button" variant="outline" disabled={!detalle.tiene_xml} onClick={descargarXml}>
                <Download className="mr-2 h-4 w-4" />
                Descargar XML
              </Button>
              <Button type="button" variant="outline" onClick={() => window.print()}>
                <Printer className="mr-2 h-4 w-4" />
                Imprimir
              </Button>
            </div>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
