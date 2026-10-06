"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { CAMPOS_POR_IMPUESTO, ETIQUETA_IMPUESTO, importeValido, valoresIniciales } from "@/lib/declaraciones";
import { etiquetaPeriodo } from "@/lib/periodo";
import type { Declaracion, DeclaracionIn, ImpuestoDeclarado } from "@/types/api";

/**
 * Captura de una declaración presentada: la normal (o su corrección mientras no haya complementarias) o una complementaria,
 * que se agrega al historial. Los importes son opcionales: solo se compara lo capturado.
 */
export function DeclaracionDialog({
  abierto, impuesto, periodo, tipo, vigente, enviando, error, onGuardar, onCerrar,
}: {
  abierto: boolean;
  impuesto: ImpuestoDeclarado;
  periodo: string;
  tipo: "normal" | "complementaria";
  vigente: Declaracion | null;
  enviando: boolean;
  error: string | null;
  onGuardar: (datos: DeclaracionIn) => void;
  onCerrar: () => void;
}) {
  const [v, setV] = useState<Record<string, string>>({});
  useEffect(() => setV(valoresIniciales(impuesto, vigente)), [impuesto, vigente, abierto, tipo]);

  const campos = CAMPOS_POR_IMPUESTO[impuesto];
  const invalidos = campos.filter(({ campo, signo }) => !importeValido(v[campo] ?? "", Boolean(signo))).map((c) => c.campo);
  const cambiar = (clave: string) => (e: { target: { value: string } }) => setV((x) => ({ ...x, [clave]: e.target.value }));

  return (
    <Dialog open={abierto} onOpenChange={(a) => !a && onCerrar()}>
      <DialogContent className="max-h-[90vh] max-w-lg overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{`${tipo === "complementaria" ? "Agregar complementaria" : "Declaración normal"} de ${ETIQUETA_IMPUESTO[impuesto]}`}</DialogTitle>
          <DialogDescription>
            {`${etiquetaPeriodo(periodo)}. Importes como aparecen en la declaración, en pesos y con hasta dos decimales.`}
            {impuesto === "isr" && " En ISR son las cifras del mes, no las acumuladas."}
          </DialogDescription>
        </DialogHeader>
        <form
          className="space-y-3"
          onSubmit={(e) => {
            e.preventDefault();
            if (invalidos.length > 0 || enviando) return;
            const datos: DeclaracionIn = {
              tipo, fecha_presentacion: v.fecha_presentacion || null, numero_operacion: v.numero_operacion?.trim() || null, notas: v.notas ?? "",
            };
            for (const { campo } of campos) datos[campo] = (v[campo] ?? "").trim() === "" ? null : v[campo].trim();
            onGuardar(datos);
          }}
        >
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label htmlFor="dec-fecha">Fecha de presentación</Label>
              <Input id="dec-fecha" type="date" value={v.fecha_presentacion ?? ""} onChange={cambiar("fecha_presentacion")} />
            </div>
            <div className="space-y-1">
              <Label htmlFor="dec-operacion">Número de operación</Label>
              <Input id="dec-operacion" value={v.numero_operacion ?? ""} onChange={cambiar("numero_operacion")} maxLength={40} />
            </div>
          </div>
          {campos.map(({ campo, etiqueta }) => (
            <div key={campo} className="space-y-1">
              <Label htmlFor={`dec-${campo}`}>{etiqueta}</Label>
              <Input
                id={`dec-${campo}`}
                inputMode="decimal"
                value={v[campo] ?? ""}
                onChange={cambiar(campo)}
                aria-invalid={invalidos.includes(campo)}
                className={invalidos.includes(campo) ? "border-destructive" : undefined}
              />
              {invalidos.includes(campo) && <p className="text-xs text-destructive">Importe inválido: hasta dos decimales y sin signo negativo.</p>}
            </div>
          ))}
          <div className="space-y-1">
            <Label htmlFor="dec-notas">Notas</Label>
            <textarea id="dec-notas" rows={2} maxLength={500} value={v.notas ?? ""} onChange={cambiar("notas")}
              className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm" />
          </div>
          {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onCerrar}>Cancelar</Button>
            <Button type="submit" disabled={invalidos.length > 0 || enviando}>{enviando ? "Guardando…" : "Guardar"}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
