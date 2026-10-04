"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import {
  rutaUsuarios,
  type AltaUsuarioInput,
  type CambiosPerfil,
  type Perfil,
  type RolEmpresa,
  type UsuarioEmpresa,
  type UsuariosDeEmpresa,
} from "@/components/cuenta/tipos";

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

export function useAltaUsuario(empresaId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (alta: AltaUsuarioInput) =>
      apiFetch<{ usuario: UsuarioEmpresa; cuenta_creada: boolean }>(rutaUsuarios(empresaId), {
        method: "POST",
        body: JSON.stringify(alta),
      }),
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
