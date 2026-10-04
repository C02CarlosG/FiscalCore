"use client";

import { FormEvent, useState } from "react";
import { AlertCircle, Building2, FileUp, LoaderCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
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
    // Se guarda antes del await: React deja event.currentTarget en null al
    // terminar el manejador síncrono, y el reset() posterior tronaba.
    const form = event.currentTarget;
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
      form.reset();
    } catch (err) {
      if (err instanceof ApiError) {
        setFormError(err.message);
      } else {
        setFormError("No se pudo subir el estado de cuenta, intenta de nuevo");
      }
    }
  }

  return (
    <Card className="h-full overflow-hidden">
      <CardHeader className="border-b bg-muted/30 px-5 py-5 sm:px-6">
        <div className="flex items-start gap-3">
          <span className="flex h-10 w-10 flex-none items-center justify-center rounded-md bg-accent text-accent-foreground">
            <Building2 className="h-5 w-5" />
          </span>
          <div className="space-y-1">
            <CardTitle className="font-display text-base">Subir estado de cuenta</CardTitle>
            <CardDescription>Archivo XLSX o CSV del banco</CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardContent className="p-5 sm:p-6">
        <form onSubmit={handleSubmit} className="space-y-5">
          <div className="space-y-2">
            <Label htmlFor="banco-periodo">Periodo (YYYY-MM)</Label>
            <Input
              id="banco-periodo"
              type="month"
              value={periodo}
              onChange={(e) => setPeriodo(e.target.value)}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="banco-select">Banco</Label>
            <Select
              value={bancoSeleccionado}
              onValueChange={setBancoSeleccionado}
            >
              <SelectTrigger id="banco-select" aria-label="Banco">
                <SelectValue placeholder="Selecciona un banco" />
              </SelectTrigger>
              <SelectContent>
                {BANCOS_COMUNES.map((banco) => (
                  <SelectItem key={banco.value} value={banco.value}>
                    {banco.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
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
              className="h-auto min-h-11 cursor-pointer py-2 file:mr-3 file:rounded file:border-0 file:bg-primary/10 file:px-3 file:py-1.5 file:text-xs file:font-semibold file:text-primary"
              onChange={(e) => setArchivo(e.target.files?.[0] ?? null)}
            />
            <p className="text-xs text-muted-foreground">Formatos aceptados: .xlsx y .csv.</p>
          </div>

          {formError && (
            <p role="alert" className="flex items-center gap-2 text-sm font-medium text-status-error">
              <AlertCircle className="h-4 w-4 flex-none" />
              {formError}
            </p>
          )}

          <Button type="submit" disabled={subirBanco.isPending} className="w-full sm:w-auto">
            {subirBanco.isPending ? <LoaderCircle className="animate-spin" /> : <FileUp />}
            {subirBanco.isPending ? "Subiendo..." : "Subir estado de cuenta"}
          </Button>

          {resultado && <IngestaResultado resultado={resultado} />}
        </form>
      </CardContent>
    </Card>
  );
}
