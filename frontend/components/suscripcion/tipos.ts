export interface Plan {
  clave: string;
  nombre: string;
  /** MXN sin IVA, con dos decimales. */
  precio_mensual: string;
  /** null = ilimitado. */
  max_rfc: number | null;
  activo: boolean;
  por_defecto: boolean;
}

export type EstadoSuscripcion = "activa" | "suspendida" | "cancelada";

export interface MiSuscripcionDatos {
  plan: Plan;
  estado: EstadoSuscripcion | null;
  vigente_hasta: string | null;
  motivo: "sin_suscripcion" | "suspendida" | "cancelada" | "vencida" | "plan_no_disponible" | null;
  uso_rfc: number;
  puede_agregar_rfc: boolean;
  es_admin_plataforma: boolean;
}

export interface CuentaSuscripcion {
  usuario_id: string;
  email: string;
  nombre: string | null;
  es_admin_plataforma: boolean;
  plan_clave: string | null;
  estado: EstadoSuscripcion | null;
  vigente_hasta: string | null;
  notas: string | null;
  uso_rfc: number;
}

export interface Asignacion {
  plan_clave: string;
  estado: EstadoSuscripcion;
  vigente_hasta: string | null;
  notas: string | null;
}

export interface CambioPlan {
  nombre: string;
  precio_mensual: string;
  max_rfc: number | null;
  activo: boolean;
}
