import { getToken } from "../auth.js";

export const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export const authHeaders = () => {
  const token = getToken();
  return token ? { "Authorization": `Bearer ${token}` } : {};
};

export const FORMA_PAGO = {
  "01":"Efectivo","02":"Cheque nominativo","03":"Transferencia",
  "04":"Tarjeta de crédito","05":"Monedero electrónico","06":"Dinero electrónico",
  "08":"Vales de despensa","28":"Tarjeta de débito","99":"Por definir",
};

export const TIPO_LABEL = { I:"Ingreso", E:"Egreso", T:"Traslado", N:"Nómina", P:"Pago" };

export const TIPO_CLS = {
  I:"text-emerald-400 bg-emerald-400/10 border-emerald-400/20",
  E:"text-amber-400  bg-amber-400/10  border-amber-400/20",
  T:"text-sky-400    bg-sky-400/10    border-sky-400/20",
  N:"text-slate-400  bg-slate-400/10  border-slate-400/20",
  P:"text-yellow-400 bg-yellow-400/10 border-yellow-400/20",
};

export const MET_CLS = {
  PUE:"text-emerald-400 bg-emerald-400/10 border-emerald-400/20",
  PPD:"text-amber-400  bg-amber-400/10  border-amber-400/20",
};

export const NS4   = "http://www.sat.gob.mx/cfd/4";
export const NSTFD = "http://www.sat.gob.mx/TimbreFiscalDigital";

export const SEV_VARIANT = { critico:"critical", alto:"high", medio:"medium", bajo:"low" };
export const SEV_LABEL   = { critico:"CRÍTICO", alto:"ALTO", medio:"MEDIO", bajo:"BAJO" };
export const SEV_COLOR   = { critico:"#F87171", alto:"#FB923C", medio:"#FBBF24", bajo:"#34D399" };

export const ESTADO_LABEL = {
  abierto:        { label:"Abierto",       cls:"text-red-400    bg-red-400/10    border-red-400/20"    },
  pendiente:      { label:"Pendiente",     cls:"text-slate-400  bg-slate-400/10  border-slate-400/20"  },
  en_revision:    { label:"En revisión",   cls:"text-sky-400    bg-sky-400/10    border-sky-400/20"    },
  en_espera_cfdi: { label:"Esp. CFDI",     cls:"text-amber-400  bg-amber-400/10  border-amber-400/20"  },
  confirmado:     { label:"Confirmado",    cls:"text-emerald-400 bg-emerald-400/10 border-emerald-400/20"},
  resuelto:       { label:"Resuelto",      cls:"text-emerald-400 bg-emerald-400/10 border-emerald-400/20"},
  descartado:     { label:"Descartado",    cls:"text-slate-400  bg-slate-400/10  border-slate-400/20"  },
  falso_positivo: { label:"Falso +",       cls:"text-slate-400  bg-slate-400/10  border-slate-400/20"  },
};

export const MESES = ["Ene","Feb","Mar","Abr","May","Jun","Jul","Ago","Sep","Oct","Nov","Dic"];

export const fmt  = (n) => new Intl.NumberFormat("es-MX",{style:"currency",currency:"MXN",maximumFractionDigits:0}).format(n??0);
export const fmtK = (n) => (n??0)>=1e6?`$${((n??0)/1e6).toFixed(1)}M`:`$${((n??0)/1e3).toFixed(0)}K`;

export const periodoLabel = (yyyymm) => {
  if (!yyyymm) return "—";
  const [y,m] = yyyymm.split("-");
  return `${MESES[parseInt(m,10)-1]} ${y}`;
};

export const scoreColor  = (s) => s >= 85 ? "#34D399" : s >= 70 ? "#06B6D4" : s >= 50 ? "#FB923C" : "#F87171";
export const scoreClasif = (s) => s >= 85 ? "SALUDABLE" : s >= 70 ? "ACEPTABLE" : s >= 50 ? "EN RIESGO" : "CRÍTICO";
