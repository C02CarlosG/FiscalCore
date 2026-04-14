import "./index.css";
import { StrictMode, useState } from "react";
import { createRoot } from "react-dom/client";
import { isLoggedIn, saveAuth, clearAuth, getEmpresaId, getEmpresaData, getEmpresas } from "./auth.js";
import LoginPage    from "./LoginPage.jsx";
import RegisterPage from "./RegisterPage.jsx";
import AuditoriaFiscal from "../AuditoriaFiscalDashboard.jsx";

function App() {
  const [view, setView] = useState(isLoggedIn() ? "dashboard" : "login");

  function handleLogin(token, empresaData) {
    saveAuth(token, empresaData);
    setView("dashboard");
  }

  function handleLogout() {
    clearAuth();
    setView("login");
  }

  if (view === "login") {
    return <LoginPage onLogin={handleLogin} onGoRegister={() => setView("register")} />;
  }

  if (view === "register") {
    return <RegisterPage onRegistered={handleLogin} onGoLogin={() => setView("login")} />;
  }

  return (
    <AuditoriaFiscal
      empresaId={getEmpresaId()}
      empresaData={getEmpresaData()}
      empresas={getEmpresas()}
      onLogout={handleLogout}
    />
  );
}

createRoot(document.getElementById("root")).render(
  <StrictMode><App /></StrictMode>
);
