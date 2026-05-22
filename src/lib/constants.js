export const FORMA_PAGO = {
  "01":"Efectivo","02":"Cheque nominativo","03":"Transferencia",
  "04":"Tarjeta de crédito","05":"Monedero electrónico","06":"Dinero electrónico",
  "08":"Vales de despensa","28":"Tarjeta de débito","99":"Por definir",
};

export const TIPO_LABEL = { I:"Ingreso", E:"Egreso", T:"Traslado", N:"Nómina", P:"Pago" };

export const TIPO_CLS = {
  I:"text-emerald-700 bg-emerald-50 border-emerald-200",
  E:"text-amber-700  bg-amber-50  border-amber-200",
  T:"text-sky-700    bg-sky-50    border-sky-200",
  N:"text-slate-600  bg-slate-50  border-slate-200",
  P:"text-yellow-700 bg-yellow-50 border-yellow-200",
};

export const MET_CLS = {
  PUE:"text-emerald-700 bg-emerald-50 border-emerald-200",
  PPD:"text-amber-700  bg-amber-50  border-amber-200",
};

export const NS4   = "http://www.sat.gob.mx/cfd/4";
export const NSTFD = "http://www.sat.gob.mx/TimbreFiscalDigital";

export const SEV_VARIANT = { critico:"critical", alto:"high", medio:"medium", bajo:"low" };
export const SEV_LABEL   = { critico:"CRÍTICO", alto:"ALTO", medio:"MEDIO", bajo:"BAJO" };
export const SEV_COLOR   = { critico:"#DC2626", alto:"#EA580C", medio:"#D97706", bajo:"#16A34A" };

export const ESTADO_LABEL = {
  abierto:        { label:"Abierto",       cls:"text-red-700     bg-red-50     border-red-200"     },
  pendiente:      { label:"Pendiente",     cls:"text-slate-600   bg-slate-50   border-slate-200"   },
  en_revision:    { label:"En revisión",   cls:"text-sky-700     bg-sky-50     border-sky-200"     },
  en_espera_cfdi: { label:"Esp. CFDI",     cls:"text-amber-700   bg-amber-50   border-amber-200"   },
  confirmado:     { label:"Confirmado",    cls:"text-emerald-700 bg-emerald-50 border-emerald-200" },
  resuelto:       { label:"Resuelto",      cls:"text-emerald-700 bg-emerald-50 border-emerald-200" },
  descartado:     { label:"Descartado",    cls:"text-slate-500   bg-slate-50   border-slate-200"   },
  falso_positivo: { label:"Falso +",       cls:"text-slate-500   bg-slate-50   border-slate-200"   },
};

export const MESES = ["Ene","Feb","Mar","Abr","May","Jun","Jul","Ago","Sep","Oct","Nov","Dic"];

export const fmt    = (n) => new Intl.NumberFormat("es-MX",{style:"currency",currency:"MXN",maximumFractionDigits:0}).format(n??0);
export const fmtDec = (n) => new Intl.NumberFormat("es-MX",{style:"currency",currency:"MXN",minimumFractionDigits:2,maximumFractionDigits:2}).format(n??0);
export const fmtK   = (n) => (n??0)>=1e6?`$${((n??0)/1e6).toFixed(1)}M`:`$${((n??0)/1e3).toFixed(0)}K`;

export const periodoLabel = (yyyymm) => {
  if (!yyyymm) return "—";
  const [y,m] = yyyymm.split("-");
  return `${MESES[parseInt(m,10)-1]} ${y}`;
};

export const scoreColor  = (s) => s >= 85 ? "#16A34A" : s >= 70 ? "#2563EB" : s >= 50 ? "#EA580C" : "#DC2626";
export const scoreClasif = (s) => s >= 85 ? "SALUDABLE" : s >= 70 ? "ACEPTABLE" : s >= 50 ? "EN RIESGO" : "CRÍTICO";
