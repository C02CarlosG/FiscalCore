const BASE = "";

function getToken() {
  return localStorage.getItem("fc_token");
}

function authHeaders() {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function req(method, path, body, opts = {}) {
  const isForm = opts.form === true;
  const res = await fetch(BASE + path, {
    method,
    headers: isForm
      ? { ...authHeaders() }
      : { "Content-Type": "application/json", ...authHeaders() },
    body: isForm ? body : (body != null ? JSON.stringify(body) : undefined),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    const e = new Error(err.detail || `HTTP ${res.status}`);
    e.status = res.status;
    throw e;
  }
  return res.json();
}

const get   = (path)       => req("GET",    path);
const post  = (path, body) => req("POST",   path, body);
const patch = (path, body) => req("PATCH",  path, body);
const del   = (path)       => req("DELETE", path);

export const api = {
  auth: {
    login:    (email, password) => post("/api/v1/auth/login", { email, password }),
    register: (data)            => post("/api/v1/auth/register", data),
    me:       ()                => get("/api/v1/auth/me"),
  },

  perfil: {
    update: (data) => patch("/api/v1/usuarios/perfil", data),
  },

  admin: {
    metricas: () => get("/api/v1/admin/metricas"),
  },

  empresas: {
    list:             ()          => get("/api/v1/empresas"),
    get:              (id)        => get(`/api/v1/empresas/${id}`),
    add:              (data)      => post("/api/v1/mis-empresas", data),
    updateImpuestos:  (id, imps)  => patch(`/api/v1/empresas/${id}/impuestos`, { impuestos: imps }),
  },

  constancia: {
    parsear: (file) => {
      const form = new FormData();
      form.append("archivo", file);
      return req("POST", "/api/v1/constancia/parsear", form, { form: true });
    },
  },

  dashboard: {
    get: (empresaId) => get(`/api/v1/dashboard/${empresaId}`),
  },

  cierre: {
    get:      (empresaId, periodo) => get(`/api/v1/empresas/${empresaId}/cierre/${periodo}`),
    periodos: (empresaId)          => get(`/api/v1/empresas/${empresaId}/periodos`),
  },

  riesgos: {
    list:    (empresaId) => get(`/api/v1/empresas/${empresaId}/riesgos`),
    resolver: (id)       => patch(`/api/v1/riesgos/${id}/resolver`, {}),
  },

  acciones: {
    ejecutar: (deteccionId, tipo, notas) =>
      post(`/api/v1/acciones/${deteccionId}/ejecutar`, { tipo, notas }),
  },

  conciliaciones: {
    list:        (empresaId) => get(`/api/v1/empresas/${empresaId}/conciliaciones`),
    accionables: (empresaId) => get(`/api/v1/empresas/${empresaId}/conciliaciones/accionables`),
  },

  cfdi: {
    emitidos:  (empresaId, periodo) => get(`/api/v1/empresas/${empresaId}/emitidos?periodo=${periodo}`),
    recibidos: (empresaId, periodo) => get(`/api/v1/empresas/${empresaId}/recibidos?periodo=${periodo}`),
    upload:    (empresaId, files, periodo) => {
      const form = new FormData();
      files.forEach(f => form.append("archivos", f));
      form.append("periodo", periodo);
      return req("POST", `/api/v1/empresas/${empresaId}/cfdi/upload`, form, { form: true });
    },
  },

  banco: {
    upload: (empresaId, file, banco, periodo) => {
      const form = new FormData();
      form.append("archivo", file);
      form.append("banco", banco);
      form.append("periodo", periodo);
      return req("POST", `/api/v1/empresas/${empresaId}/banco/upload`, form, { form: true });
    },
  },

  scoring: {
    get:      (empresaId, periodo) => get(`/api/v1/empresas/${empresaId}/scoring${periodo ? `?periodo=${periodo}` : ""}`),
    historial: (empresaId)         => get(`/api/v1/empresas/${empresaId}/scoring/historial`),
  },

  reportes: {
    scoring: (empresaId, periodo) => get(`/api/v1/empresas/${empresaId}/reportes/scoring/${periodo}`),
    diot:    (empresaId, periodo) => get(`/api/v1/empresas/${empresaId}/diot/${periodo}`),
  },

  sat: {
    solicitar:   (data)      => post("/api/v1/sat/solicitar", data),
    solicitudes: (empresaId) => get(`/api/v1/sat/solicitudes?empresa_id=${empresaId}`),
    verificar:   (id)        => post(`/api/v1/sat/solicitudes/${id}/verificar`, {}),
    descargar:   (id)        => post(`/api/v1/sat/solicitudes/${id}/descargar`, {}),
    fiel: {
      estado:   (empresaId)           => get(`/api/v1/sat/empresas/${empresaId}/fiel/estado`),
      guardar:  (empresaId, formData) => req("POST", `/api/v1/sat/empresas/${empresaId}/fiel/guardar`, formData, { form: true }),
      eliminar: (empresaId)           => del(`/api/v1/sat/empresas/${empresaId}/fiel`),
      sync:     (empresaId, formData) => req("POST", `/api/v1/sat/empresas/${empresaId}/fiel/sync`, formData, { form: true }),
    },
  },
};
