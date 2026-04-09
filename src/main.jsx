import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import AuditoriaFiscal from "../AuditoriaFiscalDashboard.jsx";

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <AuditoriaFiscal />
  </StrictMode>
);
