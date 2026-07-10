"use client";

import { FormEvent, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useCrearEmpresa } from "@/hooks/useEmpresas";
import { ApiError } from "@/lib/api-client";

interface FieldErrors {
  rfc?: string;
  razon_social?: string;
}

export function EmpresaForm({ onCreated }: { onCreated?: () => void }) {
  const crearEmpresa = useCrearEmpresa();
  const [rfc, setRfc] = useState("");
  const [razonSocial, setRazonSocial] = useState("");
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [formError, setFormError] = useState<string | null>(null);

  function validar(): boolean {
    const errors: FieldErrors = {};
    const rfcNormalizado = rfc.trim().toUpperCase();
    if (!rfcNormalizado) {
      errors.rfc = "El RFC es obligatorio";
    } else if (rfcNormalizado.length < 12 || rfcNormalizado.length > 13) {
      errors.rfc = "El RFC debe tener 12 o 13 caracteres";
    }
    if (!razonSocial.trim()) {
      errors.razon_social = "La razón social es obligatoria";
    }
    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError(null);
    if (!validar()) return;

    try {
      await crearEmpresa.mutateAsync({
        rfc: rfc.trim().toUpperCase(),
        razon_social: razonSocial.trim(),
      });
      setRfc("");
      setRazonSocial("");
      setFieldErrors({});
      onCreated?.();
    } catch (err) {
      if (err instanceof ApiError) {
        setFieldErrors((err.fieldErrors as FieldErrors) ?? {});
        setFormError(err.fieldErrors ? null : err.message);
      } else {
        setFormError("No se pudo dar de alta la empresa, intenta de nuevo");
      }
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4 rounded-lg border p-4">
      <h2 className="text-lg font-semibold">Agregar empresa</h2>

      <div className="space-y-2">
        <Label htmlFor="rfc">RFC</Label>
        <Input id="rfc" value={rfc} onChange={(e) => setRfc(e.target.value)} />
        {fieldErrors.rfc && (
          <p role="alert" className="text-sm text-red-600">
            {fieldErrors.rfc}
          </p>
        )}
      </div>

      <div className="space-y-2">
        <Label htmlFor="razon_social">Razón social</Label>
        <Input
          id="razon_social"
          value={razonSocial}
          onChange={(e) => setRazonSocial(e.target.value)}
        />
        {fieldErrors.razon_social && (
          <p role="alert" className="text-sm text-red-600">
            {fieldErrors.razon_social}
          </p>
        )}
      </div>

      {formError && (
        <p role="alert" className="text-sm text-red-600">
          {formError}
        </p>
      )}

      <Button type="submit" disabled={crearEmpresa.isPending}>
        {crearEmpresa.isPending ? "Guardando..." : "Guardar"}
      </Button>
    </form>
  );
}
