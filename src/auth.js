const KEY_TOKEN   = "fc_token";
const KEY_EMPRESA = "fc_empresa";

export function saveAuth(token, empresaData) {
  localStorage.setItem(KEY_TOKEN, token);
  localStorage.setItem(KEY_EMPRESA, JSON.stringify(empresaData));
}

export function getToken() {
  return localStorage.getItem(KEY_TOKEN);
}

export function getEmpresaData() {
  const raw = localStorage.getItem(KEY_EMPRESA);
  if (!raw) return null;
  try { return JSON.parse(raw); } catch { return null; }
}

export function getEmpresaId() {
  return getEmpresaData()?.empresa_id ?? null;
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

export function clearAuth() {
  localStorage.removeItem(KEY_TOKEN);
  localStorage.removeItem(KEY_EMPRESA);
}
