// src/main.jsx
import "./index.css";
import { StrictMode, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  isLoggedIn, saveAuth, clearAuth,
  getEmpresaId, getEmpresaData, getEmpresas, getUser,
  setEmpresaActiva, addEmpresa, updateProfile,
  getPeriodoEmpresa, setPeriodoEmpresa,
} from "./auth.js";
import { API_URL, authHeaders } from "./lib/constants.js";
import LoginPage           from "./LoginPage.jsx";
import RegisterPage        from "./RegisterPage.jsx";
import InicioPage          from "./InicioPage.jsx";
import PerfilPage          from "./PerfilPage.jsx";
import SelectorPeriodoPage from "./SelectorPeriodoPage.jsx";
import AuditoriaFiscal     from "./AuditoriaFiscalDashboard.jsx";

function App() {
  const [view, setView]             = useState(isLoggedIn() ? "inicio" : "login");
  const [empresasVersion, setEmpresasVersion] = useState(0);
  const [userData, setUserData]     = useState(getUser);
  const [pendingEmpresaId, setPendingEmpresaId] = useState(null);
  const [initialTab, setInitialTab] = useState(null);

  function handleLogin(token, data) {
    saveAuth(token, data);
    setUserData(data);
    setView("inicio");
  }

  function handleLogout() {
    clearAuth();
    setUserData(null);
    setInitialTab(null);
    setPendingEmpresaId(null);
    setView("login");
  }

  async function handleSelectEmpresa(empresaId) {
    setEmpresaActiva(empresaId);
    setPendingEmpresaId(empresaId);

    // Verificar si el período por defecto ya tiene datos
    const periodo = getPeriodoEmpresa(empresaId);
    try {
      const res = await fetch(
        `${API_URL}/api/v1/empresas/${empresaId}/periodos`,
        { headers: authHeaders() }
      );
      if (res.ok) {
        const data = await res.json();
        const periodosConDatos = data
          .map(p => typeof p === "string" ? p : p.periodo)
          .filter(Boolean);
        if (periodosConDatos.includes(periodo)) {
          // Ya hay datos para el período por defecto → ir directo al dashboard
          setInitialTab(null);
          setView("dashboard");
          return;
        }
      }
    } catch (_) {
      // Si falla la consulta, ir al selector para que el usuario decida
    }

    // No hay datos → mostrar selector de período
    setView("periodo_selector");
  }

  function handleContinuarDesdeSelector(periodo, source) {
    const empresaId = pendingEmpresaId ?? getEmpresaId();
    setPeriodoEmpresa(empresaId, periodo);
    const tabMap = { sat: "sat", upload: "ingesta", existing: null };
    setInitialTab(tabMap[source] ?? null);
    setView("dashboard");
  }

  function handleEmpresaAgregada(empresa) {
    addEmpresa(empresa);
    setEmpresasVersion(v => v + 1);
    setUserData(u => u ? { ...u, empresas: [...(u.empresas ?? []), empresa] } : u);
    // Nueva empresa → ir al selector de período
    setEmpresaActiva(empresa.empresa_id);
    setPendingEmpresaId(empresa.empresa_id);
    setView("periodo_selector");
  }

  function handlePerfilActualizado(campos) {
    updateProfile(campos);
    setUserData(u => u ? { ...u, ...campos } : u);
  }

  if (view === "login") {
    return <LoginPage onLogin={handleLogin} onGoRegister={() => setView("register")} />;
  }

  if (view === "register") {
    return <RegisterPage onRegistered={handleLogin} onGoLogin={() => setView("login")} />;
  }

  if (view === "perfil") {
    return (
      <PerfilPage
        userData={userData}
        onVolver={() => setView("inicio")}
        onPerfilActualizado={handlePerfilActualizado}
      />
    );
  }

  if (view === "inicio") {
    return (
      <InicioPage
        key={empresasVersion}
        empresas={userData?.empresas ?? getEmpresas()}
        userData={userData}
        onSelectEmpresa={handleSelectEmpresa}
        onLogout={handleLogout}
        onEmpresaAgregada={handleEmpresaAgregada}
        onPerfil={() => setView("perfil")}
      />
    );
  }

  if (view === "periodo_selector") {
    const empresaId = pendingEmpresaId ?? getEmpresaId();
    const empresaData = (userData?.empresas ?? getEmpresas())
      .find(e => (e.empresa_id ?? e.id) === empresaId) ?? getEmpresaData();
    return (
      <SelectorPeriodoPage
        empresaId={empresaId}
        empresaData={empresaData}
        onContinuar={handleContinuarDesdeSelector}
        onVolver={() => setView("inicio")}
      />
    );
  }

  return (
    <AuditoriaFiscal
      key={`${getEmpresaId()}-${initialTab}`}
      empresaId={getEmpresaId()}
      empresaData={getEmpresaData()}
      empresas={getEmpresas()}
      onLogout={handleLogout}
      onVolverInicio={() => setView("inicio")}
      initialTab={initialTab}
    />
  );
}

createRoot(document.getElementById("root")).render(
  <StrictMode><App /></StrictMode>
);
