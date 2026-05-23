import { createContext, useContext, useState, useCallback } from "react";

const AppContext = createContext(null);

const MONTH_NAMES = ["Enero","Febrero","Marzo","Abril","Mayo","Junio","Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"];

export const VALID_VIEWS = [
  "dash", "descarga", "xml", "bancos", "concil", "riesgos", "reportes", "empresas", "perfil",
];

export function resolveActiveView(stored) {
  return VALID_VIEWS.includes(stored) ? stored : "dash";
}

export function periodLabel(month) {
  const [y, m] = month.split("-");
  return `${MONTH_NAMES[parseInt(m, 10) - 1]} ${y}`;
}

function suggestedPeriod() {
  const now = new Date();
  const target = now.getDate() < 17
    ? new Date(now.getFullYear(), now.getMonth() - 1, 1)
    : new Date(now.getFullYear(), now.getMonth(), 1);
  const y = target.getFullYear();
  const m = String(target.getMonth() + 1).padStart(2, "0");
  return { month: `${y}-${m}`, label: `${MONTH_NAMES[target.getMonth()]} ${y}` };
}

export function AppProvider({ children }) {
  const [companies, setCompanies] = useState([]);
  const [company, setCompany] = useState(() => {
    try { return JSON.parse(localStorage.getItem("fc_company_data") || "null"); }
    catch { return null; }
  });
  const [workspaceReady, setWorkspaceReady] = useState(() => {
    const flag = localStorage.getItem("fc_ws_ready") === "1";
    let co = null;
    try { co = JSON.parse(localStorage.getItem("fc_company_data") || "null"); } catch {}
    return flag && co != null;
  });
  const [period, setPeriod] = useState(() => {
    try { return JSON.parse(localStorage.getItem("fc_period") || "null") || suggestedPeriod(); }
    catch { return suggestedPeriod(); }
  });
  const [active, setActive] = useState(
    () => resolveActiveView(localStorage.getItem("fc_active"))
  );

  const enterWorkspace = useCallback((co, per) => {
    setCompany(co);
    setPeriod(per);
    setWorkspaceReady(true);
    setActive("dash");
    localStorage.setItem("fc_ws_ready", "1");
    localStorage.setItem("fc_period", JSON.stringify(per));
    localStorage.setItem("fc_company_data", JSON.stringify(co));
    localStorage.setItem("fc_active", "dash");
  }, []);

  const exitWorkspace = useCallback(() => {
    setWorkspaceReady(false);
    localStorage.removeItem("fc_ws_ready");
  }, []);

  const navigate = useCallback((id) => {
    setActive(id);
    localStorage.setItem("fc_active", id);
  }, []);

  return (
    <AppContext.Provider value={{
      companies, setCompanies,
      company, setCompany,
      period, setPeriod,
      workspaceReady,
      active,
      enterWorkspace, exitWorkspace, navigate,
    }}>
      {children}
    </AppContext.Provider>
  );
}

export function useApp() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useApp must be inside AppProvider");
  return ctx;
}
