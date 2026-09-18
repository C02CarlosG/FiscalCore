"use client";

import { FormEvent, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useSubirBanco } from "@/hooks/useIngesta";
import { ApiError } from "@/lib/api-client";
import { IngestaResultado } from "@/components/ingesta/IngestaResultado";
import type { IngestaResponse } from "@/types/api";

const BANCOS_COMUNES = [
  { value: "bbva", label: "BBVA" },
  { value: "santander", label: "Santander" },
  { value: "banamex", label: "Banamex" },
  { value: "banorte", label: "Banorte" },
  { value: "hsbc", label: "HSBC" },
  { value: "scotiabank", label: "Scotiabank" },
  { value: "otro", label: "Otro" },
];

export function BancoUploadForm({ empresaId }: { empresaId: string }) {
  const subirBanco = useSubirBanco(empresaId);
  const [periodo, setPeriodo] = useState("");
  const [bancoSeleccionado, setBancoSeleccionado] = useState("");
  const [bancoLibre, setBancoLibre] = useState("");
  const [archivo, setArchivo] = useState<File | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [resultado, setResultado] = useState<IngestaResponse | null>(null);

  const esOtro = bancoSeleccionado === "otro";
  const bancoFinal = esOtro ? bancoLibre.trim() : bancoSeleccionado;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError(null);
    setResultado(null);

    if (!periodo.trim()) {
      setFormError("El periodo es obligatorio");
      return;
    }
    if (!bancoFinal) {
      setFormError("El banco es obligatorio");
      return;
    }
    if (!archivo) {
      setFormError("Selecciona un archivo .xlsx o .csv");
      return;
    }

    try {
      const response = await subirBanco.mutateAsync({
        archivo,
        banco: bancoFinal,
        periodo: periodo.trim(),
      });
      setResultado(response);
      setArchivo(null);
      setBancoSeleccionado("");
      setBancoLibre("");
      setPeriodo("");
      event.currentTarget.reset();
    } catch (err) {
      if (err instanceof ApiError) {
        setFormError(err.message);
      } else {
        setFormError("No se pudo subir el estado de cuenta, intenta de nuevo");
      }
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Subir estado de cuenta</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="banco-periodo">Periodo (YYYY-MM)</Label>
            <Input
              id="banco-periodo"
              placeholder="2026-07"
              value={periodo}
              onChange={(e) => setPeriodo(e.target.value)}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="banco-select">Banco</Label>
            <select
              id="banco-select"
              className="w-full rounded-md border border-input bg-background p-2 text-sm"
              value={bancoSeleccionado}
              onChange={(e) => setBancoSeleccionado(e.target.value)}
            >
              <option value="">Selecciona un banco</option>
              {BANCOS_COMUNES.map((banco) => (
                <option key={banco.value} value={banco.value}>
                  {banco.label}
                </option>
              ))}
            </select>
          </div>

          {esOtro && (
            <div className="space-y-2">
              <Label htmlFor="banco-libre">Nombre del banco</Label>
              <Input
                id="banco-libre"
                value={bancoLibre}
                onChange={(e) => setBancoLibre(e.target.value)}
              />
            </div>
          )}

          <div className="space-y-2">
            <Label htmlFor="banco-archivo">Estado de cuenta (.xlsx o .csv)</Label>
            <Input
              id="banco-archivo"
              type="file"
              accept=".xlsx,.csv"
              onChange={(e) => setArchivo(e.target.files?.[0] ?? null)}
            />
          </div>

          {formError && (
            <p role="alert" className="text-sm text-status-error">
              {formError}
            </p>
          )}

          <Button type="submit" disabled={subirBanco.isPending}>
            {subirBanco.isPending ? "Subiendo..." : "Subir estado de cuenta"}
          </Button>

          {resultado && <IngestaResultado resultado={resultado} />}
        </form>
      </CardContent>
    </Card>
  );
}
