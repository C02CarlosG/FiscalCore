"use client";

import { FormEvent, useState } from "react";
import { AlertCircle, FileCode2, FileUp, LoaderCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
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
    <Card className="h-full overflow-hidden">
      <CardHeader className="border-b bg-muted/30 px-5 py-5 sm:px-6">
        <div className="flex items-start gap-3">
          <span className="flex h-10 w-10 flex-none items-center justify-center rounded-md bg-primary/10 text-primary">
            <FileCode2 className="h-5 w-5" />
          </span>
          <div className="space-y-1">
            <CardTitle className="font-display text-base">Subir CFDI</CardTitle>
            <CardDescription>Archivos XML · carga múltiple disponible</CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardContent className="p-5 sm:p-6">
        <form onSubmit={handleSubmit} className="space-y-5">
          <div className="space-y-2">
            <Label htmlFor="cfdi-periodo">Periodo (YYYY-MM)</Label>
            <Input
              id="cfdi-periodo"
              type="month"
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
              className="h-auto min-h-11 cursor-pointer py-2 file:mr-3 file:rounded file:border-0 file:bg-primary/10 file:px-3 file:py-1.5 file:text-xs file:font-semibold file:text-primary"
              onChange={(e) => setArchivos(e.target.files)}
            />
            <p className="text-xs text-muted-foreground">Selecciona uno o varios archivos con extensión .xml.</p>
          </div>

          {formError && (
            <p role="alert" className="flex items-center gap-2 text-sm font-medium text-status-error">
              <AlertCircle className="h-4 w-4 flex-none" />
              {formError}
            </p>
          )}

          <Button type="submit" disabled={subirCfdi.isPending} className="w-full sm:w-auto">
            {subirCfdi.isPending ? <LoaderCircle className="animate-spin" /> : <FileUp />}
            {subirCfdi.isPending ? "Subiendo..." : "Subir CFDI"}
          </Button>

          {resultado && <IngestaResultado resultado={resultado} />}
        </form>
      </CardContent>
    </Card>
  );
}
