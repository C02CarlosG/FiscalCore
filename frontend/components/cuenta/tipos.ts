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

export interface UsuariosDeEmpresa {
  mi_rol: RolEmpresa | null;
  puede_administrar: boolean;
  usuarios: UsuarioEmpresa[];
}

export interface AltaUsuarioInput {
  email: string;
  rol: RolEmpresa;
  nombre?: string;
  password_temporal?: string;
}

export const ETIQUETA_ROL_EMPRESA: Record<RolEmpresa, string> = {
  administrador: "Administrador",
  contador: "Contador",
};

export const rutaUsuarios = (empresaId: string) => `/api/v1/cuenta/empresas/${empresaId}/usuarios`;
