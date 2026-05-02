// src/main.jsx
import "./index.css";
import { StrictMode, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  isLoggedIn, saveAuth, clearAuth,
  getEmpresaId, getEmpresaData, getEmpresas, getUser,
  setEmpresaActiva, addEmpresa, updateProfile,
} from "./auth.js";
import LoginPage       from "./LoginPage.jsx";
import RegisterPage    from "./RegisterPage.jsx";
import InicioPage      from "./InicioPage.jsx";
import PerfilPage      from "./PerfilPage.jsx";
import AuditoriaFiscal from "./AuditoriaFiscalDashboard.jsx";

function App() {
  const [view, setView]             = useState(isLoggedIn() ? "inicio" : "login");
  const [empresasVersion, setEmpresasVersion] = useState(0);
  const [userData, setUserData]     = useState(getUser);

  function handleLogin(token, data) {
    saveAuth(token, data);
    setUserData(data);
    setView("inicio");
  }

  function handleLogout() {
    clearAuth();
    setUserData(null);
    setView("login");
  }

  function handleSelectEmpresa(empresaId) {
    setEmpresaActiva(empresaId);
    setView("dashboard");
  }

  function handleEmpresaAgregada(empresa) {
    addEmpresa(empresa);
    setEmpresasVersion(v => v + 1);
    setUserData(u => u ? { ...u, empresas: [...(u.empresas ?? []), empresa] } : u);
    setEmpresaActiva(empresa.empresa_id);
    setView("dashboard");
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

  return (
    <AuditoriaFiscal
      key={getEmpresaId()}
      empresaId={getEmpresaId()}
      empresaData={getEmpresaData()}
      empresas={getEmpresas()}
      userData={userData}
      onLogout={handleLogout}
      onVolverInicio={() => setView("inicio")}
    />
  );
}

createRoot(document.getElementById("root")).render(
  <StrictMode><App /></StrictMode>
);
