"use client";

import { useEffect, useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import {
  ETIQUETA_OPERADOR,
  MAX_FILTROS,
  SEPARADOR,
  leerFiltros,
  operadoresDe,
  renglonCompleto,
  renglonConOperador,
  renglonNuevo,
  serializarFiltros,
  type Operador,
  type RenglonFiltro,
} from "@/lib/cfdi-filtros";
import type { CfdiColumna } from "@/types/api";

const CONTROL = "h-9 rounded-md border border-input bg-background px-2 text-sm";

function ValorControl({
  columna,
  renglon,
  onChange,
  etiqueta,
}: {
  columna: CfdiColumna;
  renglon: RenglonFiltro;
  onChange: (valor: string) => void;
  etiqueta: string;
}) {
  const { op, valor } = renglon;

  if (columna.tipo_dato === "booleano") {
    return (
      <select aria-label={`Valor de ${etiqueta}`} className={CONTROL} value={valor} onChange={(e) => onChange(e.target.value)}>
        <option value="true">Sí</option>
        <option value="false">No</option>
      </select>
    );
  }

  if (columna.tipo_dato === "catalogo" && op === "en") {
    const elegidos = new Set(valor.split(SEPARADOR).filter(Boolean));
    return (
      <div role="group" aria-label={`Valores de ${etiqueta}`} className="flex flex-wrap gap-x-3 gap-y-1">
        {columna.opciones.map((opcion) => (
          <label key={opcion} className="flex items-center gap-1.5 text-sm">
            <input
              type="checkbox"
              className="h-4 w-4 accent-primary"
              checked={elegidos.has(opcion)}
              onChange={() => {
                const siguiente = new Set(elegidos);
                if (siguiente.has(opcion)) siguiente.delete(opcion);
                else siguiente.add(opcion);
                onChange(columna.opciones.filter((o) => siguiente.has(o)).join(SEPARADOR));
              }}
            />
            {opcion}
          </label>
        ))}
      </div>
    );
  }

  if (columna.tipo_dato === "catalogo") {
    return (
      <select aria-label={`Valor de ${etiqueta}`} className={CONTROL} value={valor} onChange={(e) => onChange(e.target.value)}>
        <option value="">Elige…</option>
        {columna.opciones.map((o) => (
          <option key={o} value={o}>{o}</option>
        ))}
      </select>
    );
  }

  const tipo = columna.tipo_dato === "fecha" || columna.tipo_dato === "fecha_hora"
    ? "date"
    : columna.tipo_dato === "texto" ? "text" : "number";
  const atributos = tipo === "number" ? { step: "any" } : {};

  if (op === "entre") {
    const [desde = "", hasta = ""] = valor.split(SEPARADOR);
    return (
      <div className="flex items-center gap-2">
        <Input type={tipo} {...atributos} aria-label={`${etiqueta}, desde`} className="h-9 w-36" value={desde}
          onChange={(e) => onChange(`${e.target.value}${SEPARADOR}${hasta}`)} />
        <span className="text-xs text-muted-foreground">y</span>
        <Input type={tipo} {...atributos} aria-label={`${etiqueta}, hasta`} className="h-9 w-36" value={hasta}
          onChange={(e) => onChange(`${desde}${SEPARADOR}${e.target.value}`)} />
      </div>
    );
  }

  return (
    <Input type={tipo} {...atributos} aria-label={`Valor de ${etiqueta}`} className="h-9 w-48" value={valor}
      onChange={(e) => onChange(e.target.value)} />
  );
}

/**
 * Ventana del filtro avanzado: renglones de campo, operador y valor. El operador y el
 * control del valor dependen del tipo de dato del campo. "Aplicar" escribe el JSON en
 * la URL; con renglones incompletos no se puede aplicar.
 */
export function FiltroAvanzado({
  abierto,
  onAbiertoChange,
  columnas,
  filtros,
  onAplicar,
}: {
  abierto: boolean;
  onAbiertoChange: (abierto: boolean) => void;
  columnas: CfdiColumna[];
  filtros: string;
  onAplicar: (filtros: string) => void;
}) {
  const filtrables = columnas.filter((c) => c.filtrable && operadoresDe(c).length > 0);
  const porClave = new Map(filtrables.map((c) => [c.clave, c]));
  const [renglones, setRenglones] = useState<RenglonFiltro[]>([]);

  // Al abrir se parte de lo que está en la URL; los campos que ya no existen se descartan.
  useEffect(() => {
    if (abierto) setRenglones(leerFiltros(filtros).filter((r) => porClave.has(r.campo)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [abierto]);

  const cambiar = (indice: number, nuevo: RenglonFiltro) =>
    setRenglones((actual) => actual.map((r, i) => (i === indice ? nuevo : r)));

  const completos = renglones.every((r) => renglonCompleto(r, porClave.get(r.campo)));

  return (
    <Dialog open={abierto} onOpenChange={onAbiertoChange}>
      <DialogContent className="max-h-[85vh] overflow-hidden sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle>Filtro avanzado</DialogTitle>
          <DialogDescription>
            Todos los filtros se aplican a la vez. Se suman a la búsqueda, el estado y el método de pago.
          </DialogDescription>
        </DialogHeader>

        <div className="max-h-[50vh] space-y-3 overflow-y-auto pr-1">
          {renglones.length === 0 && (
            <p className="text-sm text-muted-foreground">No hay filtros. Agrega uno para empezar.</p>
          )}
          {renglones.map((renglon, indice) => {
            const columna = porClave.get(renglon.campo);
            if (!columna) return null;
            return (
              <div key={indice} role="group" aria-label={`Filtro ${indice + 1}`}
                className="flex flex-wrap items-center gap-2 rounded-md border bg-card p-2">
                <select
                  aria-label="Campo"
                  className={CONTROL}
                  value={renglon.campo}
                  onChange={(e) => cambiar(indice, renglonNuevo(porClave.get(e.target.value)!))}
                >
                  {filtrables.map((c) => (
                    <option key={c.clave} value={c.clave}>{c.etiqueta}</option>
                  ))}
                </select>
                <select
                  aria-label="Operador"
                  className={CONTROL}
                  value={renglon.op}
                  onChange={(e) => cambiar(indice, renglonConOperador(renglon, e.target.value as Operador))}
                >
                  {operadoresDe(columna).map((op) => (
                    <option key={op} value={op}>{ETIQUETA_OPERADOR[op]}</option>
                  ))}
                </select>
                <ValorControl columna={columna} renglon={renglon} etiqueta={columna.etiqueta}
                  onChange={(valor) => cambiar(indice, { ...renglon, valor })} />
                <Button type="button" variant="ghost" size="icon" className="ml-auto h-8 w-8"
                  aria-label={`Quitar filtro ${indice + 1}`}
                  onClick={() => setRenglones((actual) => actual.filter((_, i) => i !== indice))}>
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            );
          })}
        </div>

        {!completos && (
          <p role="status" className="text-xs text-muted-foreground">
            Completa el valor de cada filtro, o quítalo, para poder aplicar.
          </p>
        )}

        <DialogFooter className="gap-2 sm:justify-between">
          <Button type="button" variant="outline" disabled={renglones.length >= MAX_FILTROS || filtrables.length === 0}
            onClick={() => setRenglones((actual) => [...actual, renglonNuevo(filtrables[0])])}>
            <Plus className="mr-1.5 h-4 w-4" />
            Agregar filtro
          </Button>
          <div className="flex gap-2">
            <Button type="button" variant="outline" onClick={() => { onAplicar(""); onAbiertoChange(false); }}>
              Quitar todos
            </Button>
            <Button type="button" disabled={!completos}
              onClick={() => { onAplicar(serializarFiltros(renglones, columnas)); onAbiertoChange(false); }}>
              Aplicar
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
