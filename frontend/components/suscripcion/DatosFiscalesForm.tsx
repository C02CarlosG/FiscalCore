"use client";

import { FormEvent, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError } from "@/lib/api-client";
import type { DatosFiscalesCliente } from "./tipos";

const VACIOS: DatosFiscalesCliente = {
  rfc: "", razon_social: "", regimen_fiscal: "", codigo_postal: "", uso_cfdi: "", correo: "",
};
const CAMPOS: { campo: Exclude<keyof DatosFiscalesCliente, "actualizado">; etiqueta: string; ayuda?: string }[] = [
  { campo: "rfc", etiqueta: "RFC" },
  { campo: "razon_social", etiqueta: "Razón social" },
  { campo: "regimen_fiscal", etiqueta: "Régimen fiscal", ayuda: "Clave del SAT, p. ej. 601 o 612" },
  { campo: "codigo_postal", etiqueta: "Código postal" },
  { campo: "uso_cfdi", etiqueta: "Uso del CFDI", ayuda: "p. ej. G03" },
  { campo: "correo", etiqueta: "Correo para el CFDI" },
];

/** Datos fiscales con los que se emite el CFDI de la suscripción; lo usan la cuenta y el administrador. */
export function DatosFiscalesForm({
  id,
  nombre,
  inicial,
  guardar,
  pendiente,
}: {
  id: string;
  nombre: string;
  inicial: DatosFiscalesCliente | null | undefined;
  guardar: (datos: DatosFiscalesCliente) => Promise<unknown>;
  pendiente: boolean;
}) {
  const [valores, setValores] = useState<DatosFiscalesCliente>(VACIOS);
  const [mensaje, setMensaje] = useState<{ ok: boolean; texto: string } | null>(null);

  useEffect(() => {
    if (inicial) setValores({ ...VACIOS, ...inicial, correo: inicial.correo ?? "" });
  }, [inicial]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMensaje(null);
    try {
      const { actualizado: _ignorado, ...cuerpo } = valores;
      await guardar({ ...cuerpo, correo: cuerpo.correo?.trim() || null });
      setMensaje({ ok: true, texto: "Datos fiscales guardados." });
    } catch (err) {
      setMensaje({ ok: false, texto: err instanceof ApiError ? err.message : "No se pudieron guardar los datos fiscales" });
    }
  }

  return (
    <form aria-label={nombre} onSubmit={handleSubmit} className="space-y-3" noValidate>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        {CAMPOS.map(({ campo, etiqueta, ayuda }) => (
          <div key={campo} className="space-y-1">
            <Label htmlFor={`${id}-${campo}`}>{etiqueta}</Label>
            <Input id={`${id}-${campo}`} value={valores[campo] ?? ""} placeholder={ayuda}
                   type={campo === "correo" ? "email" : "text"}
                   onChange={(e) => setValores({ ...valores, [campo]: e.target.value })} />
          </div>
        ))}
      </div>
      {mensaje && (
        <p role={mensaje.ok ? "status" : "alert"} className={`text-sm ${mensaje.ok ? "text-status-ok" : "text-destructive"}`}>
          {mensaje.texto}
        </p>
      )}
      <Button type="submit" size="sm" disabled={pendiente}>Guardar datos fiscales</Button>
    </form>
  );
}
