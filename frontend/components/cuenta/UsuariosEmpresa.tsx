"use client";

import { FormEvent, useState } from "react";
import { Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ErrorState } from "@/components/shared/ErrorState";
import { LoadingState } from "@/components/shared/LoadingState";
import {
  useCambiarRol,
  useCancelarInvitacion,
  useInvitar,
  useQuitarUsuario,
  useUsuariosEmpresa,
} from "@/hooks/useCuenta";
import { ApiError } from "@/lib/api-client";
import { formatearFecha } from "@/lib/formato";
import { ETIQUETA_ROL_EMPRESA, type InvitacionEmpresa, type RolEmpresa } from "./tipos";

const SELECT_CLASS =
  "h-9 rounded-md border border-input bg-background px-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring";
const INVITACION_VACIA = { email: "", rol: "contador" as RolEmpresa };

const mensajeDe = (err: unknown, otro: string) => (err instanceof ApiError ? err.message : otro);

function InvitarForm({ empresaId }: { empresaId: string }) {
  const invitar = useInvitar(empresaId);
  const [valores, setValores] = useState(INVITACION_VACIA);
  const [mensaje, setMensaje] = useState<{ tipo: "ok" | "error"; texto: string } | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMensaje(null);
    try {
      await invitar.mutateAsync({ email: valores.email.trim(), rol: valores.rol });
      setMensaje({
        tipo: "ok",
        texto:
          "Invitación enviada. La persona la acepta en «Mi perfil»; si aún no tiene cuenta, que se registre con ese correo.",
      });
      setValores(INVITACION_VACIA);
    } catch (err) {
      setMensaje({ tipo: "error", texto: mensajeDe(err, "No se pudo enviar la invitación") });
    }
  }

  return (
    <form aria-label="Invitar a la empresa" onSubmit={handleSubmit} className="space-y-4 border-t border-border pt-5" noValidate>
      <h3 className="text-sm font-semibold">Invitar a otra persona</h3>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-[1fr_12rem]">
        <div className="space-y-1.5">
          <Label htmlFor="invitar-email">Correo</Label>
          <Input id="invitar-email" type="email" value={valores.email}
                 onChange={(e) => setValores({ ...valores, email: e.target.value })} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="invitar-rol">Rol</Label>
          <select id="invitar-rol" className={`${SELECT_CLASS} w-full`} value={valores.rol}
                  onChange={(e) => setValores({ ...valores, rol: e.target.value as RolEmpresa })}>
            <option value="contador">Contador</option>
            <option value="administrador">Administrador</option>
          </select>
        </div>
      </div>
      {mensaje && (
        <p role={mensaje.tipo === "ok" ? "status" : "alert"}
           className={`text-sm ${mensaje.tipo === "ok" ? "text-status-ok" : "text-destructive"}`}>
          {mensaje.texto}
        </p>
      )}
      <Button type="submit" disabled={invitar.isPending}>Invitar</Button>
    </form>
  );
}

function InvitacionesPendientes({ empresaId, invitaciones }: { empresaId: string; invitaciones: InvitacionEmpresa[] }) {
  const cancelar = useCancelarInvitacion(empresaId);
  if (invitaciones.length === 0) return null;
  return (
    <div className="space-y-2">
      <h3 className="text-sm font-semibold">Invitaciones pendientes</h3>
      <ul className="divide-y divide-border rounded-md border border-dashed border-border">
        {invitaciones.map((i) => (
          <li key={i.id} className="flex items-center justify-between gap-2 p-3 text-sm">
            <span className="min-w-0 truncate">
              {i.email} · {ETIQUETA_ROL_EMPRESA[i.rol]}
            </span>
            <Button type="button" size="sm" variant="ghost" aria-label={`Cancelar invitación a ${i.email}`}
                    disabled={cancelar.isPending} onClick={() => cancelar.mutate(i.id)}>
              Cancelar
            </Button>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function UsuariosEmpresa({ empresaId }: { empresaId: string }) {
  const consulta = useUsuariosEmpresa(empresaId);
  const cambiarRol = useCambiarRol(empresaId);
  const quitar = useQuitarUsuario(empresaId);
  const [confirmando, setConfirmando] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (consulta.isLoading) return <LoadingState label="Consultando usuarios" />;
  if (consulta.isError || !consulta.data) {
    return <ErrorState message="No se pudieron consultar los usuarios." onRetry={() => consulta.refetch()} />;
  }
  const { usuarios, puede_administrar, invitaciones = [] } = consulta.data;

  async function handleRol(usuarioId: string, rol: RolEmpresa) {
    setError(null);
    try {
      await cambiarRol.mutateAsync({ usuarioId, rol });
    } catch (err) {
      setError(mensajeDe(err, "No se pudo cambiar el rol"));
    }
  }

  async function handleQuitar(usuarioId: string) {
    setError(null);
    try {
      await quitar.mutateAsync(usuarioId);
    } catch (err) {
      setError(mensajeDe(err, "No se pudo quitar el acceso"));
    } finally {
      setConfirmando(null);
    }
  }

  return (
    <Card>
      <CardHeader className="px-5 py-5 sm:px-6">
        <CardTitle className="font-display text-base">Usuarios con acceso</CardTitle>
        <CardDescription>
          El administrador invita y gestiona quién tiene acceso; el contador trabaja la empresa.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-5 px-5 pb-5 sm:px-6">
        {!puede_administrar && (
          <p className="rounded-md border border-dashed border-border p-3 text-sm text-muted-foreground">
            Solo un administrador de la empresa puede invitar, cambiar roles o quitar usuarios.
          </p>
        )}
        {error && (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        )}
        <ul className="divide-y divide-border rounded-md border border-border">
          {usuarios.map((u) => (
            <li key={u.usuario_id} className="flex flex-col gap-2 p-3 sm:flex-row sm:items-center sm:justify-between">
              <div className="min-w-0">
                <p className="truncate text-sm font-medium">
                  {u.nombre ?? "Sin nombre"} {u.soy_yo && <span className="text-muted-foreground">(tú)</span>}
                </p>
                <p className="truncate text-xs text-muted-foreground">
                  <span>{u.email}</span> · desde {formatearFecha(u.desde)}
                </p>
              </div>
              <div className="flex flex-none items-center gap-2">
                {puede_administrar ? (
                  <select
                    aria-label={`Rol de ${u.email}`}
                    className={SELECT_CLASS}
                    value={u.rol}
                    disabled={cambiarRol.isPending}
                    onChange={(e) => handleRol(u.usuario_id, e.target.value as RolEmpresa)}
                  >
                    <option value="contador">Contador</option>
                    <option value="administrador">Administrador</option>
                  </select>
                ) : (
                  <span className="text-sm">{ETIQUETA_ROL_EMPRESA[u.rol]}</span>
                )}
                {puede_administrar &&
                  (confirmando === u.usuario_id ? (
                    <>
                      <Button type="button" size="sm" variant="destructive"
                              aria-label={`Confirmar: quitar acceso a ${u.email}`}
                              disabled={quitar.isPending} onClick={() => handleQuitar(u.usuario_id)}>
                        Quitar
                      </Button>
                      <Button type="button" size="sm" variant="outline" onClick={() => setConfirmando(null)}>
                        Cancelar
                      </Button>
                    </>
                  ) : (
                    <Button type="button" size="sm" variant="ghost" aria-label={`Quitar acceso a ${u.email}`}
                            onClick={() => setConfirmando(u.usuario_id)}>
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  ))}
              </div>
            </li>
          ))}
        </ul>
        {puede_administrar && <InvitacionesPendientes empresaId={empresaId} invitaciones={invitaciones} />}
        {puede_administrar && <InvitarForm empresaId={empresaId} />}
      </CardContent>
    </Card>
  );
}
