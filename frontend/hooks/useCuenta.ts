"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import {
  rutaInvitaciones,
  rutaUsuarios,
  type CambiosPerfil,
  type InvitacionEmpresa,
  type InvitacionInput,
  type MiInvitacion,
  type Perfil,
  type RolEmpresa,
  type UsuarioEmpresa,
  type UsuariosDeEmpresa,
} from "@/components/cuenta/tipos";

const MIS_INVITACIONES = ["cuenta", "invitaciones"];

const PERFIL = ["cuenta", "perfil"];
const usuarios = (empresaId: string) => ["cuenta", "usuarios", empresaId];

export function usePerfil() {
  return useQuery({ queryKey: PERFIL, queryFn: () => apiFetch<Perfil>("/api/v1/auth/me") });
}

export function useActualizarPerfil() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (cambios: CambiosPerfil) =>
      apiFetch<Perfil>("/api/v1/usuarios/perfil", { method: "PATCH", body: JSON.stringify(cambios) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: PERFIL }),
  });
}

export function useCambiarContrasena() {
  return useMutation({
    // Las contraseñas viajan en las variables de la mutación: no se conservan en caché.
    gcTime: 0,
    mutationFn: (datos: { actual: string; nueva: string }) =>
      apiFetch<void>("/api/v1/cuenta/contrasena", { method: "POST", body: JSON.stringify(datos) }),
  });
}

export function useUsuariosEmpresa(empresaId: string) {
  return useQuery({
    queryKey: usuarios(empresaId),
    queryFn: () => apiFetch<UsuariosDeEmpresa>(rutaUsuarios(empresaId)),
    enabled: Boolean(empresaId),
  });
}

export function useInvitar(empresaId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (invitacion: InvitacionInput) =>
      apiFetch<InvitacionEmpresa>(rutaInvitaciones(empresaId), {
        method: "POST",
        body: JSON.stringify(invitacion),
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: usuarios(empresaId) }),
  });
}

export function useCancelarInvitacion(empresaId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (invitacionId: string) =>
      apiFetch<void>(`${rutaInvitaciones(empresaId)}/${invitacionId}`, { method: "DELETE" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: usuarios(empresaId) }),
  });
}

export function useMisInvitaciones() {
  return useQuery({
    queryKey: MIS_INVITACIONES,
    queryFn: () => apiFetch<MiInvitacion[]>("/api/v1/cuenta/invitaciones"),
  });
}

export function useResponderInvitacion() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, aceptar }: { id: string; aceptar: boolean }) =>
      apiFetch<unknown>(`/api/v1/cuenta/invitaciones/${id}/${aceptar ? "aceptar" : "rechazar"}`, { method: "POST" }),
    // Aceptar no da acceso todavía: la invitación queda esperando la aprobación de un administrador.
    onSuccess: () => queryClient.invalidateQueries({ queryKey: MIS_INVITACIONES }),
  });
}

/** Un administrador aprueba (da acceso) o rechaza a quien aceptó una invitación. */
export function useResolverAceptacion(empresaId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, aprobar }: { id: string; aprobar: boolean }) =>
      apiFetch<void>(`${rutaInvitaciones(empresaId)}/${id}/${aprobar ? "aprobar" : "rechazar"}`, { method: "POST" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: usuarios(empresaId) }),
  });
}

export function useCambiarRol(empresaId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ usuarioId, rol }: { usuarioId: string; rol: RolEmpresa }) =>
      apiFetch<UsuarioEmpresa>(`${rutaUsuarios(empresaId)}/${usuarioId}`, {
        method: "PATCH",
        body: JSON.stringify({ rol }),
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: usuarios(empresaId) }),
  });
}

export function useQuitarUsuario(empresaId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (usuarioId: string) =>
      apiFetch<void>(`${rutaUsuarios(empresaId)}/${usuarioId}`, { method: "DELETE" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: usuarios(empresaId) }),
  });
}
