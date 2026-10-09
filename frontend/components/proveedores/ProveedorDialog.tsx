"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ETIQUETA_TERCERO, TIPOS_OPERACION, TIPOS_TERCERO } from "@/lib/diot";
import type { Proveedor, ProveedorIn } from "@/types/api";

const CAMPO = "flex h-9 w-full rounded-md border border-input bg-background px-3 text-sm";
const vacio = { rfc: "", nombre: "", tipo_tercero: "", tipo_operacion: "", pais: "", id_fiscal: "" };

/** Alta de un proveedor (RFC obligatorio) o edición de uno del catálogo (el RFC no cambia). */
export function ProveedorDialog({
  abierto, proveedor, enviando, error, onGuardar, onCerrar,
}: {
  abierto: boolean;
  proveedor: Proveedor | null;
  enviando: boolean;
  error: string | null;
  onGuardar: (datos: ProveedorIn) => void;
  onCerrar: () => void;
}) {
  const [f, setF] = useState(vacio);
  useEffect(() => {
    setF(proveedor ? {
      rfc: proveedor.rfc, nombre: proveedor.nombre, tipo_tercero: proveedor.tipo_tercero ?? "",
      tipo_operacion: proveedor.tipo_operacion ?? "", pais: proveedor.pais ?? "", id_fiscal: proveedor.id_fiscal ?? "",
    } : vacio);
  }, [proveedor, abierto]);

  const cambiar = (campo: keyof typeof vacio) => (e: { target: { value: string } }) => setF((x) => ({ ...x, [campo]: e.target.value }));
  const valido = f.rfc.trim() !== "";
  const extranjero = f.tipo_tercero === "05";

  return (
    <Dialog open={abierto} onOpenChange={(a) => !a && onCerrar()}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>{proveedor ? "Editar proveedor" : "Agregar proveedor"}</DialogTitle>
          <DialogDescription>El tipo de tercero y la operación por omisión se usan en la DIOT salvo que se corrijan en un periodo.</DialogDescription>
        </DialogHeader>
        <form
          className="space-y-3"
          onSubmit={(e) => {
            e.preventDefault();
            if (!valido || enviando) return;
            onGuardar({
              rfc: f.rfc.trim().toUpperCase(), nombre: f.nombre.trim(), tipo_tercero: f.tipo_tercero || null,
              tipo_operacion: f.tipo_operacion || null, pais: f.pais.trim().toUpperCase() || null, id_fiscal: f.id_fiscal.trim() || null,
            });
          }}
        >
          <div className="space-y-1">
            <Label htmlFor="prov-rfc">RFC</Label>
            <Input id="prov-rfc" value={f.rfc} onChange={cambiar("rfc")} disabled={proveedor !== null} maxLength={30} />
          </div>
          <div className="space-y-1">
            <Label htmlFor="prov-nombre">Nombre</Label>
            <Input id="prov-nombre" value={f.nombre} onChange={cambiar("nombre")} maxLength={300} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label htmlFor="prov-tercero">Tipo de tercero</Label>
              <select id="prov-tercero" className={CAMPO} value={f.tipo_tercero} onChange={cambiar("tipo_tercero")}>
                <option value="">Sin definir</option>
                {TIPOS_TERCERO.map((t) => <option key={t} value={t}>{ETIQUETA_TERCERO[t]}</option>)}
              </select>
            </div>
            <div className="space-y-1">
              <Label htmlFor="prov-operacion">Operación por omisión</Label>
              <select id="prov-operacion" className={CAMPO} value={f.tipo_operacion} onChange={cambiar("tipo_operacion")}>
                <option value="">Sin definir</option>
                {TIPOS_OPERACION.map((t) => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
          </div>
          {(extranjero || f.pais || f.id_fiscal) && (
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <Label htmlFor="prov-pais">País (ISO, 3 letras)</Label>
                <Input id="prov-pais" value={f.pais} onChange={cambiar("pais")} maxLength={3} />
              </div>
              <div className="space-y-1">
                <Label htmlFor="prov-idfiscal">ID fiscal</Label>
                <Input id="prov-idfiscal" value={f.id_fiscal} onChange={cambiar("id_fiscal")} maxLength={40} />
              </div>
            </div>
          )}
          {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onCerrar}>Cancelar</Button>
            <Button type="submit" disabled={!valido || enviando}>{enviando ? "Guardando…" : "Guardar"}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
