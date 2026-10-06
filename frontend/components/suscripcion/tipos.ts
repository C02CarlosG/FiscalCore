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
  /** Días para el vencimiento si es en 15 días o menos; null si no hay aviso. */
  dias_para_vencer: number | null;
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
  dias_para_vencer: number | null;
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

/** Una asignación de plan del historial (M7.2). */
export interface AsignacionHistorial {
  fecha: string;
  plan_clave: string;
  plan_nombre: string;
  estado: EstadoSuscripcion;
  vigente_hasta: string | null;
  /** Solo en la vista del administrador de la plataforma. */
  notas?: string | null;
  asignada_por?: string | null;
}

export const ETIQUETA_ESTADO: Record<EstadoSuscripcion, string> = {
  activa: "Activa",
  suspendida: "Suspendida",
  cancelada: "Cancelada",
};

/** Datos con los que se emite (fuera de FiscalCore) el CFDI de la suscripción (D10). */
export interface DatosFiscalesCliente {
  rfc: string;
  razon_social: string;
  regimen_fiscal: string;
  codigo_postal: string;
  uso_cfdi: string;
  actualizado?: string;
}

/** Pago registrado a mano por el administrador de la plataforma (D10). */
export interface PagoSuscripcion {
  id: string;
  fecha: string;
  /** MXN con dos decimales. */
  monto: string;
  referencia: string | null;
  folio_cfdi: string | null;
  /** Solo en la vista del administrador. */
  registrado_por?: string | null;
}

export interface PagoInput {
  fecha: string;
  monto: string;
  referencia: string | null;
  folio_cfdi: string | null;
}
