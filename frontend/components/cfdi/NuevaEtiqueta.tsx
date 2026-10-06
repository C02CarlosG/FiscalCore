"use client";

import { useState } from "react";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useCrearEtiqueta } from "@/hooks/useNotasCfdi";
import type { Etiqueta } from "@/types/api";

const COLORES = ["#ef4444", "#f59e0b", "#10b981", "#3b82f6", "#8b5cf6", "#64748b"];

/** Alta de una etiqueta del catálogo de la empresa (nombre y color). */
export function NuevaEtiqueta({ empresaId, onCreada }: { empresaId: string; onCreada?: (e: Etiqueta) => void }) {
  const [nombre, setNombre] = useState("");
  const [color, setColor] = useState(COLORES[3]);
  const crear = useCrearEtiqueta(empresaId);

  function enviar(evento: React.FormEvent) {
    evento.preventDefault();
    if (!nombre.trim()) return;
    crear.mutate(
      { nombre: nombre.trim(), color },
      { onSuccess: (e) => { setNombre(""); onCreada?.(e); } },
    );
  }

  return (
    <form onSubmit={enviar} className="space-y-1.5">
      <div className="flex flex-wrap items-center gap-2">
        <Input
          aria-label="Nombre de la etiqueta nueva"
          placeholder="Nueva etiqueta"
          maxLength={40}
          value={nombre}
          onChange={(e) => setNombre(e.target.value)}
          className="h-8 w-44"
        />
        <div role="radiogroup" aria-label="Color" className="flex gap-1">
          {COLORES.map((c) => (
            <button
              key={c}
              type="button"
              role="radio"
              aria-checked={c === color}
              aria-label={`Color ${c}`}
              onClick={() => setColor(c)}
              className={`h-5 w-5 rounded-full border-2 ${c === color ? "border-foreground" : "border-transparent"}`}
              style={{ backgroundColor: c }}
            />
          ))}
        </div>
        <Button type="submit" size="sm" variant="outline" disabled={crear.isPending || !nombre.trim()}>
          <Plus className="mr-1 h-3.5 w-3.5" />
          Crear
        </Button>
      </div>
      {crear.isError && (
        <p role="alert" className="text-xs text-destructive">
          {crear.error instanceof Error ? crear.error.message : "No se pudo crear la etiqueta."}
        </p>
      )}
    </form>
  );
}
