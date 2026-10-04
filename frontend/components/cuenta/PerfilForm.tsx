"use client";

import { FormEvent, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ErrorState } from "@/components/shared/ErrorState";
import { useActualizarPerfil, usePerfil } from "@/hooks/useCuenta";
import { ApiError } from "@/lib/api-client";
import type { CambiosPerfil, Perfil } from "./tipos";

type Campo = keyof CambiosPerfil;

const CAMPOS: { clave: Campo; etiqueta: string; mayusculas?: boolean }[] = [
  { clave: "nombre", etiqueta: "Nombre" },
  { clave: "telefono", etiqueta: "Teléfono" },
  { clave: "rfc", etiqueta: "RFC", mayusculas: true },
  { clave: "nombre_despacho", etiqueta: "Despacho" },
  { clave: "cedula_profesional", etiqueta: "Cédula profesional" },
];

function valoresDe(perfil: Perfil): Record<Campo, string> {
  return Object.fromEntries(CAMPOS.map((c) => [c.clave, perfil[c.clave] ?? ""])) as Record<Campo, string>;
}

export function PerfilForm() {
  const perfil = usePerfil();
  const actualizar = useActualizarPerfil();
  const [valores, setValores] = useState<Record<Campo, string> | null>(null);
  const [mensaje, setMensaje] = useState<{ tipo: "ok" | "error"; texto: string } | null>(null);

  useEffect(() => {
    if (perfil.data) setValores(valoresDe(perfil.data));
  }, [perfil.data]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!perfil.data || !valores) return;
    setMensaje(null);
    const originales = valoresDe(perfil.data);
    const cambios: CambiosPerfil = {};
    for (const c of CAMPOS) {
      const valor = c.mayusculas ? valores[c.clave].trim().toUpperCase() : valores[c.clave].trim();
      if (valor !== originales[c.clave] && valor !== "") cambios[c.clave] = valor;
    }
    if (Object.keys(cambios).length === 0) {
      setMensaje({ tipo: "error", texto: "No hay cambios que guardar" });
      return;
    }
    try {
      await actualizar.mutateAsync(cambios);
      setMensaje({ tipo: "ok", texto: "Perfil guardado" });
    } catch (err) {
      setMensaje({ tipo: "error", texto: err instanceof ApiError ? err.message : "No se pudo guardar el perfil" });
    }
  }

  return (
    <Card>
      <CardHeader className="px-5 py-5 sm:px-6">
        <CardTitle className="font-display text-base">Datos del perfil</CardTitle>
        <CardDescription>
          {perfil.data ? <span>{perfil.data.email}</span> : "Tu información como contador."}
        </CardDescription>
      </CardHeader>
      <CardContent className="px-5 pb-5 sm:px-6">
        {perfil.isLoading && <p className="text-sm text-muted-foreground">Cargando perfil…</p>}
        {perfil.isError && <ErrorState message="No se pudo cargar el perfil." onRetry={() => perfil.refetch()} />}
        {valores && (
          <form onSubmit={handleSubmit} className="space-y-4" noValidate>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              {CAMPOS.map((c) => (
                <div key={c.clave} className="space-y-1.5">
                  <Label htmlFor={`perfil-${c.clave}`}>{c.etiqueta}</Label>
                  <Input
                    id={`perfil-${c.clave}`}
                    value={valores[c.clave]}
                    onChange={(e) => setValores({ ...valores, [c.clave]: e.target.value })}
                  />
                </div>
              ))}
            </div>
            {mensaje && (
              <p role={mensaje.tipo === "ok" ? "status" : "alert"}
                 className={`text-sm ${mensaje.tipo === "ok" ? "text-status-ok" : "text-destructive"}`}>
                {mensaje.texto}
              </p>
            )}
            <Button type="submit" disabled={actualizar.isPending}>Guardar perfil</Button>
          </form>
        )}
      </CardContent>
    </Card>
  );
}
