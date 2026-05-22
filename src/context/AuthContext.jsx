import { createContext, useContext, useState, useCallback } from "react";

const AuthContext = createContext(null);

function parseJwt(token) {
  try { return JSON.parse(atob(token.split(".")[1])); }
  catch { return null; }
}

function tokenValid(token) {
  if (!token) return false;
  const p = parseJwt(token);
  return p ? p.exp * 1000 > Date.now() : false;
}

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => {
    const t = localStorage.getItem("fc_token");
    return tokenValid(t) ? t : null;
  });
  const [user, setUser] = useState(() => {
    try { return JSON.parse(localStorage.getItem("fc_user") || "null"); }
    catch { return null; }
  });

  const login = useCallback((newToken, userData) => {
    localStorage.setItem("fc_token", newToken);
    localStorage.setItem("fc_user", JSON.stringify(userData));
    setToken(newToken);
    setUser(userData);
  }, []);

  const logout = useCallback(() => {
    ["fc_token", "fc_user", "fc_ws_ready", "fc_active", "fc_company_data", "fc_period"].forEach(k => localStorage.removeItem(k));
    setToken(null);
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ token, user, isLoggedIn: !!token, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be inside AuthProvider");
  return ctx;
}
