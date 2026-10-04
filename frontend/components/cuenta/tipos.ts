export type RolEmpresa = "administrador" | "contador";

export interface Perfil {
  id: string;
  email: string;
  nombre: string | null;
  telefono: string | null;
  rfc: string | null;
  nombre_despacho: string | null;
  cedula_profesional: string | null;
}

export type CambiosPerfil = Partial<Pick<Perfil, "nombre" | "telefono" | "rfc" | "nombre_despacho" | "cedula_profesional">>;

export interface UsuarioEmpresa {
  usuario_id: string;
  email: string;
  nombre: string | null;
  rol: RolEmpresa;
  desde: string | null;
  soy_yo: boolean;
}

export interface InvitacionEmpresa {
  id: string;
  email: string;
  rol: RolEmpresa;
  estado: "pendiente" | "aceptada" | "rechazada" | "cancelada";
  creada: string | null;
}

export interface UsuariosDeEmpresa {
  mi_rol: RolEmpresa | null;
  puede_administrar: boolean;
  usuarios: UsuarioEmpresa[];
  invitaciones: InvitacionEmpresa[];
}

export interface InvitacionInput {
  email: string;
  rol: RolEmpresa;
}

export interface MiInvitacion {
  id: string;
  rol: RolEmpresa;
  creada: string;
  rfc: string;
  razon_social: string;
  invitada_por: string | null;
}

export const ETIQUETA_ROL_EMPRESA: Record<RolEmpresa, string> = {
  administrador: "Administrador",
  contador: "Contador",
};

export const rutaUsuarios = (empresaId: string) => `/api/v1/cuenta/empresas/${empresaId}/usuarios`;
export const rutaInvitaciones = (empresaId: string) => `/api/v1/cuenta/empresas/${empresaId}/invitaciones`;
