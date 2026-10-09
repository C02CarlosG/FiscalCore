"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { Pencil, Plus, Search } from "lucide-react";
import { ErrorState } from "@/components/shared/ErrorState";
import { PageHeader } from "@/components/shared/PageHeader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useCrearProveedor, useEditarProveedor, useProveedores } from "@/hooks/useProveedores";
import { ApiError } from "@/lib/api-client";
import { ETIQUETA_TERCERO } from "@/lib/diot";
import type { Proveedor, ProveedorIn } from "@/types/api";
import { ProveedorDialog } from "./ProveedorDialog";

const mensajeDe = (e: unknown, porDefecto: string) => (e instanceof ApiError ? e.message : porDefecto);

/**
 * Catálogo de proveedores de la empresa: se alimenta de los CFDI recibidos y se completa a mano (alta y edición del tipo de
 * tercero y de la operación por omisión). La columna «Lista 69-B» queda reservada para la alerta de EFOS (M3).
 */
export function ProveedoresPantalla() {
  const { empresaId } = useParams<{ empresaId: string }>();
  const [busqueda, setBusqueda] = useState("");
  const [q, setQ] = useState("");
  const lista = useProveedores(empresaId, q);
  const crear = useCrearProveedor(empresaId);
  const editar = useEditarProveedor(empresaId);
  const [dialogo, setDialogo] = useState<{ proveedor: Proveedor | null } | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function guardar(datos: ProveedorIn) {
    setError(null);
    try {
      if (dialogo?.proveedor) {
        const { rfc: _rfc, ...cambios } = datos;
        await editar.mutateAsync({ id: dialogo.proveedor.id, cambios });
      } else {
        await crear.mutateAsync(datos);
      }
      setDialogo(null);
    } catch (e) {
      setError(mensajeDe(e, "No se pudo guardar el proveedor."));
    }
  }

  const datos = lista.data;

  return (
    <main className="space-y-6">
      <PageHeader
        eyebrow="Catálogos"
        title="Proveedores"
        description="Proveedores de la empresa con su tipo de tercero y operación por omisión, que la DIOT usa."
        actions={
          <Button type="button" onClick={() => { setError(null); setDialogo({ proveedor: null }); }}>
            <Plus className="mr-2 h-4 w-4" />
            Agregar proveedor
          </Button>
        }
      />

      <form
        role="search"
        className="flex max-w-md gap-2"
        onSubmit={(e) => { e.preventDefault(); setQ(busqueda.trim()); }}
      >
        <Input aria-label="Buscar proveedor" placeholder="RFC, nombre o ID fiscal" value={busqueda} onChange={(e) => setBusqueda(e.target.value)} maxLength={100} />
        <Button type="submit" variant="outline"><Search className="mr-2 h-4 w-4" />Buscar</Button>
      </form>

      {lista.isError && !datos ? (
        <ErrorState message="No se pudo cargar el catálogo de proveedores." onRetry={() => lista.refetch()} />
      ) : !datos ? (
        <Skeleton role="status" aria-label="Cargando proveedores" className="h-64 rounded-md" />
      ) : datos.items.length === 0 ? (
        <p className="rounded-md border border-dashed bg-card p-8 text-center text-sm text-muted-foreground">
          {q ? "Ningún proveedor coincide con la búsqueda." : "Todavía no hay proveedores: se agregan solos con los CFDI recibidos o con «Agregar proveedor»."}
        </p>
      ) : (
        <div className="space-y-2">
          <p className="text-xs text-muted-foreground">
            {`${datos.total} proveedores`}{datos.agregados > 0 ? ` · ${datos.agregados} nuevos desde los CFDI recibidos` : ""}
            {datos.omitidos > 0 ? ` · ${datos.omitidos} RFC con formato inválido sin agregar` : ""}
          </p>
          <div className="overflow-x-auto rounded-md border bg-card">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>RFC</TableHead>
                  <TableHead>Nombre</TableHead>
                  <TableHead>Tipo de tercero</TableHead>
                  <TableHead>Operación</TableHead>
                  <TableHead>País / ID fiscal</TableHead>
                  <TableHead>Lista 69-B</TableHead>
                  <TableHead><span className="sr-only">Acciones</span></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {datos.items.map((p) => (
                  <TableRow key={p.id}>
                    <TableCell className="whitespace-nowrap font-mono text-xs">{p.rfc}</TableCell>
                    <TableCell className="min-w-48">
                      <span className="block truncate">{p.nombre || "—"}</span>
                      <span className="text-xs text-muted-foreground">{p.origen === "manual" ? "Alta manual" : "De los CFDI"}</span>
                    </TableCell>
                    <TableCell>{p.tipo_tercero ? ETIQUETA_TERCERO[p.tipo_tercero] ?? p.tipo_tercero : "—"}</TableCell>
                    <TableCell className="font-mono">{p.tipo_operacion ?? "—"}</TableCell>
                    <TableCell className="text-xs">
                      {p.pais || p.id_fiscal ? `${p.pais ?? "—"} · ${p.id_fiscal ?? "—"}` : "—"}
                      {p.pendiente && <Badge variant="secondary" className="ml-2 font-normal">Faltan datos</Badge>}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">Sin verificar</TableCell>
                    <TableCell>
                      <Button type="button" variant="ghost" size="icon" className="h-7 w-7" aria-label={`Editar ${p.nombre || p.rfc}`}
                        onClick={() => { setError(null); setDialogo({ proveedor: p }); }}>
                        <Pencil className="h-4 w-4" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </div>
      )}

      <ProveedorDialog
        abierto={dialogo !== null}
        proveedor={dialogo?.proveedor ?? null}
        enviando={crear.isPending || editar.isPending}
        error={error}
        onGuardar={guardar}
        onCerrar={() => setDialogo(null)}
      />
    </main>
  );
}
