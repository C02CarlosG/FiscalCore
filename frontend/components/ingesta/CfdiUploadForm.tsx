"use client";

import { FormEvent, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useSubirCfdi } from "@/hooks/useIngesta";
import { ApiError } from "@/lib/api-client";
import { IngestaResultado } from "@/components/ingesta/IngestaResultado";
import type { IngestaResponse } from "@/types/api";

export function CfdiUploadForm({ empresaId }: { empresaId: string }) {
  const subirCfdi = useSubirCfdi(empresaId);
  const [periodo, setPeriodo] = useState("");
  const [archivos, setArchivos] = useState<FileList | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [resultado, setResultado] = useState<IngestaResponse | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError(null);
    setResultado(null);

    if (!periodo.trim()) {
      setFormError("El periodo es obligatorio");
      return;
    }
    if (!archivos || archivos.length === 0) {
      setFormError("Selecciona al menos un archivo XML");
      return;
    }

    try {
      const response = await subirCfdi.mutateAsync({
        archivos: Array.from(archivos),
        periodo: periodo.trim(),
      });
      setResultado(response);
      setArchivos(null);
      setPeriodo("");
      event.currentTarget.reset();
    } catch (err) {
      if (err instanceof ApiError) {
        setFormError(err.message);
      } else {
        setFormError("No se pudo subir el CFDI, intenta de nuevo");
      }
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Subir CFDI</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="cfdi-periodo">Periodo (YYYY-MM)</Label>
            <Input
              id="cfdi-periodo"
              placeholder="2026-07"
              value={periodo}
              onChange={(e) => setPeriodo(e.target.value)}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="cfdi-archivos">Archivos XML</Label>
            <Input
              id="cfdi-archivos"
              type="file"
              multiple
              accept=".xml"
              onChange={(e) => setArchivos(e.target.files)}
            />
          </div>

          {formError && (
            <p role="alert" className="text-sm text-status-error">
              {formError}
            </p>
          )}

          <Button type="submit" disabled={subirCfdi.isPending}>
            {subirCfdi.isPending ? "Subiendo..." : "Subir CFDI"}
          </Button>

          {resultado && <IngestaResultado resultado={resultado} />}
        </form>
      </CardContent>
    </Card>
  );
}
