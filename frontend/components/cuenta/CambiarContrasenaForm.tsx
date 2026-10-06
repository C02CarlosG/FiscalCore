"use client";

import { FormEvent, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useCambiarContrasena } from "@/hooks/useCuenta";
import { ApiError } from "@/lib/api-client";

const VACIO = { actual: "", nueva: "", confirmar: "" };

export function CambiarContrasenaForm() {
  const cambiar = useCambiarContrasena();
  const [valores, setValores] = useState(VACIO);
  const [mensaje, setMensaje] = useState<{ tipo: "ok" | "error"; texto: string } | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMensaje(null);
    if (valores.nueva.length < 8) {
      setMensaje({ tipo: "error", texto: "La contraseña nueva debe tener al menos 8 caracteres" });
      return;
    }
    if (valores.nueva !== valores.confirmar) {
      setMensaje({ tipo: "error", texto: "La confirmación no coincide" });
      return;
    }
    try {
      await cambiar.mutateAsync({ actual: valores.actual, nueva: valores.nueva });
      setMensaje({ tipo: "ok", texto: "Contraseña actualizada" });
    } catch (err) {
      setMensaje({ tipo: "error", texto: err instanceof ApiError ? err.message : "No se pudo cambiar la contraseña" });
    } finally {
      // Las contraseñas no se conservan en el navegador más allá del envío.
      setValores(VACIO);
      cambiar.reset();
    }
  }

  const campo = (clave: keyof typeof VACIO, etiqueta: string, autoComplete: string) => (
    <div className="space-y-1.5">
      <Label htmlFor={`contrasena-${clave}`}>{etiqueta}</Label>
      <Input
        id={`contrasena-${clave}`}
        type="password"
        autoComplete={autoComplete}
        value={valores[clave]}
        onChange={(e) => setValores({ ...valores, [clave]: e.target.value })}
      />
    </div>
  );

  return (
    <Card>
      <CardHeader className="px-5 py-5 sm:px-6">
        <CardTitle className="font-display text-base">Contraseña</CardTitle>
        <CardDescription>Usa al menos 8 caracteres.</CardDescription>
      </CardHeader>
      <CardContent className="px-5 pb-5 sm:px-6">
        <form onSubmit={handleSubmit} className="space-y-4" noValidate>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            {campo("actual", "Contraseña actual", "current-password")}
            {campo("nueva", "Contraseña nueva", "new-password")}
            {campo("confirmar", "Confirma la contraseña nueva", "new-password")}
          </div>
          {mensaje && (
            <p role={mensaje.tipo === "ok" ? "status" : "alert"}
               className={`text-sm ${mensaje.tipo === "ok" ? "text-status-ok" : "text-destructive"}`}>
              {mensaje.texto}
            </p>
          )}
          <Button type="submit" disabled={cambiar.isPending}>Cambiar contraseña</Button>
        </form>
      </CardContent>
    </Card>
  );
}
