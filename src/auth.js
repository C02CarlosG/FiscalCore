const KEY_TOKEN = "fc_token";
const KEY_USER  = "fc_user";   // { user_id, nombre, empresas: [] }

export function saveAuth(token, userData) {
  localStorage.setItem(KEY_TOKEN, token);
  localStorage.setItem(KEY_USER,  JSON.stringify(userData));
}

export function getToken() {
  return localStorage.getItem(KEY_TOKEN);
}

export function getUser() {
  const raw = localStorage.getItem(KEY_USER);
  if (!raw) return null;
  try { return JSON.parse(raw); } catch { return null; }
}

export function getEmpresas() {
  return getUser()?.empresas ?? [];
}

// Retorna la empresa activa (primera por defecto, o la que el usuario seleccionó)
export function getEmpresaId() {
  const activa = localStorage.getItem("fc_empresa_activa");
  if (activa) return activa;
  return getEmpresas()[0]?.empresa_id ?? null;
}

export function setEmpresaActiva(empresaId) {
  localStorage.setItem("fc_empresa_activa", empresaId);
}

export function getEmpresaData() {
  const id = getEmpresaId();
  return getEmpresas().find(e => e.empresa_id === id) ?? getEmpresas()[0] ?? null;
}

export function isLoggedIn() {
  const token = getToken();
  if (!token) return false;
  try {
    const payload = JSON.parse(atob(token.split(".")[1]));
    return payload.exp * 1000 > Date.now();
  } catch {
    return false;
  }
}

export function getEmail() {
  return getUser()?.email ?? null;
}

export function addEmpresa(empresa) {
  const user = getUser();
  if (!user) return;
  localStorage.setItem(KEY_USER, JSON.stringify({
    ...user,
    empresas: [...(user.empresas ?? []), empresa],
  }));
}

export function updateProfile(campos) {
  const user = getUser();
  if (!user) return;
  localStorage.setItem(KEY_USER, JSON.stringify({ ...user, ...campos }));
}

export function clearAuth() {
  localStorage.removeItem(KEY_TOKEN);
  localStorage.removeItem(KEY_USER);
  localStorage.removeItem("fc_empresa_activa");
}

// Regla fiscal MX: antes del día 17 → cierre del mes anterior
export function getPeriodoSugerido() {
  const now = new Date();
  const target = now.getDate() < 17
    ? new Date(now.getFullYear(), now.getMonth() - 1, 1)
    : now;
  return `${target.getFullYear()}-${String(target.getMonth() + 1).padStart(2, "0")}`;
}

export function getPeriodoEmpresa(empresaId) {
  if (!empresaId) return getPeriodoSugerido();
  return localStorage.getItem(`fc_periodo_${empresaId}`) ?? getPeriodoSugerido();
}

export function setPeriodoEmpresa(empresaId, periodo) {
  if (!empresaId || !periodo) return;
  localStorage.setItem(`fc_periodo_${empresaId}`, periodo);
}
