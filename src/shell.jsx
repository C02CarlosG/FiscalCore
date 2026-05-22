import { useState, useRef, useEffect } from "react";
import Icon from "./icons.jsx";
import { Button } from "./components/ui/button.jsx";
import { Separator } from "./components/ui/separator.jsx";
import { useAuth } from "./context/AuthContext.jsx";
import { useApp } from "./context/AppContext.jsx";
import DashboardPage from "./pages/DashboardPage.jsx";
import CompaniesPage from "./pages/CompaniesPage.jsx";
import DownloadPage from "./pages/DownloadPage.jsx";
import CfdiPage from "./pages/CfdiPage.jsx";
import BankPage from "./pages/BankPage.jsx";
import ReconciliationPage from "./pages/ReconciliationPage.jsx";
import ReportsPage from "./pages/ReportsPage.jsx";
import ProfilePage from "./pages/ProfilePage.jsx";
import RisksPage from "./pages/RisksPage.jsx";

const NAV_MAIN = [
  { id: "dash",     label: "Resumen",           icon: "dash"     },
  { id: "descarga", label: "Descarga SAT",       icon: "download" },
  { id: "xml",      label: "CFDI / XML",         icon: "file"     },
  { id: "bancos",   label: "Estados de cuenta",  icon: "bank"     },
  { id: "concil",   label: "Conciliación",       icon: "link"     },
  { id: "riesgos",  label: "Riesgos",            icon: "alert"    },
  { id: "reportes", label: "Reportes",           icon: "report"   },
];

const NAV_CONFIG = [
  { id: "empresas", label: "Empresas",           icon: "building" },
  { id: "perfil",   label: "Perfil",             icon: "user"     },
];

function initials(razon = "", rfc = "") {
  const r = razon || "";
  const c = rfc || "";
  return r.split(" ").filter(w => /^[A-ZÁÉÍÓÚÑ]/.test(w[0] || "")).slice(0, 2).map(w => w[0]).join("") || c.slice(0, 2);
}

export default function Shell() {
  const { user, logout } = useAuth();
  const { company, companies, setCompany, period, exitWorkspace, active, navigate } = useApp();

  const page = {
    dash:     <DashboardPage />,
    descarga: <DownloadPage />,
    xml:      <CfdiPage />,
    bancos:   <BankPage />,
    concil:   <ReconciliationPage />,
    riesgos:  <RisksPage />,
    reportes: <ReportsPage />,
    empresas: <CompaniesPage />,
    perfil:   <ProfilePage />,
  }[active] || <DashboardPage />;

  return (
    <div style={{ display: "flex", height: "100vh", overflow: "hidden", background: "var(--background)" }}>
      <Sidebar
        active={active} navigate={navigate}
        company={company} companies={companies} setCompany={setCompany}
        user={user} logout={logout} exitWorkspace={exitWorkspace}
      />
      <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>
        <Topbar period={period} exitWorkspace={exitWorkspace} />
        <main style={{ flex: 1, overflow: "auto" }}>
          {page}
        </main>
      </div>
    </div>
  );
}

function Sidebar({ active, navigate, company, companies, setCompany, user, logout, exitWorkspace }) {
  return (
    <aside style={{
      width: 224, flexShrink: 0,
      borderRight: "1px solid var(--border-shadcn)",
      background: "var(--card)",
      display: "flex", flexDirection: "column",
    }}>
      <div style={{ padding: "14px 16px", borderBottom: "1px solid var(--border-shadcn)" }}>
        <div className="flex items-center gap-2">
          <div style={{
            width: 24, height: 24, borderRadius: 6,
            background: "var(--primary)", display: "grid", placeItems: "center",
            color: "var(--primary-foreground)", fontWeight: 700,
            fontFamily: "var(--font-mono)", fontSize: 11,
          }}>FC</div>
          <span style={{ fontWeight: 650, fontSize: 14, letterSpacing: "-0.01em" }}>FiscalCore</span>
        </div>
      </div>

      {company && (
        <div style={{ padding: "10px 12px", borderBottom: "1px solid var(--border-shadcn)" }}>
          <CompanyPicker
            company={company} companies={companies}
            onChange={setCompany} onChangeWorkspace={exitWorkspace}
          />
        </div>
      )}

      <nav style={{ flex: 1, padding: "6px 8px", overflowY: "auto" }}>
        <div style={{ fontSize: 10, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--muted-foreground)", padding: "6px 8px 4px" }}>
          Flujo de auditoría
        </div>
        {NAV_MAIN.map(item => (
          <NavItem key={item.id} item={item} isActive={active === item.id} onClick={() => navigate(item.id)} />
        ))}
        <div style={{ fontSize: 10, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--muted-foreground)", padding: "14px 8px 4px" }}>
          Configuración
        </div>
        {NAV_CONFIG.map(item => (
          <NavItem key={item.id} item={item} isActive={active === item.id} onClick={() => navigate(item.id)} />
        ))}
      </nav>

      <div style={{ padding: "10px 12px", borderTop: "1px solid var(--border-shadcn)" }}>
        <div className="flex items-center gap-2">
          <div style={{
            width: 28, height: 28, borderRadius: 999, flexShrink: 0,
            background: "var(--muted)", display: "grid", placeItems: "center",
            fontSize: 11, fontWeight: 600, color: "var(--muted-foreground)",
          }}>
            {(user?.nombre || user?.email || "U").slice(0, 1).toUpperCase()}
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 12, fontWeight: 500, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {user?.nombre || user?.email || "Usuario"}
            </div>
            <div style={{ fontSize: 10, color: "var(--muted-foreground)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {user?.nombre_despacho || "Despacho contable"}
            </div>
          </div>
          <Button variant="ghost" size="sm" onClick={logout} title="Cerrar sesión" style={{ padding: "0 4px", flexShrink: 0 }}>
            <Icon name="logout" size={13} />
          </Button>
        </div>
      </div>
    </aside>
  );
}

function NavItem({ item, isActive, onClick }) {
  const [hovered, setHovered] = useState(false);
  return (
    <button
      onClick={onClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        width: "100%", textAlign: "left",
        display: "flex", alignItems: "center", gap: 8,
        padding: "6px 8px", borderRadius: 5, marginBottom: 1,
        fontSize: 13, fontFamily: "inherit",
        color: isActive ? "var(--primary)" : "var(--foreground)",
        background: isActive
          ? "color-mix(in oklch, var(--primary), white 88%)"
          : hovered ? "var(--muted)" : "transparent",
        fontWeight: isActive ? 600 : 400,
        border: "none", cursor: "pointer",
        transition: "background 0.1s, color 0.1s",
      }}
    >
      <Icon name={item.icon} size={15} style={{ flexShrink: 0, opacity: isActive ? 1 : 0.65 }} />
      {item.label}
    </button>
  );
}

function CompanyPicker({ company, companies, onChange, onChangeWorkspace }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    const h = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, []);

  const razon = company.razon || company.razon_social || "";
  const color = company.color || "var(--primary)";
  const ini = initials(razon, company.rfc);

  return (
    <div ref={ref} style={{ position: "relative" }}>
      <button
        onClick={() => setOpen(!open)}
        style={{
          width: "100%", textAlign: "left", padding: "7px 8px",
          border: "1px solid var(--border-shadcn)", borderRadius: 7,
          background: "var(--background)", cursor: "pointer",
          display: "flex", alignItems: "center", gap: 8, fontFamily: "inherit",
        }}
      >
        <span className="avatar" style={{ background: `color-mix(in oklch, ${color}, white 75%)`, color, width: 26, height: 26, fontSize: 10, borderRadius: 6, flexShrink: 0 }}>{ini}</span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 12, fontWeight: 600, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{razon}</div>
          <div className="mono" style={{ fontSize: 10, color: "var(--muted-foreground)" }}>{company.rfc}</div>
        </div>
        <Icon name="chevronDown" size={12} style={{ color: "var(--muted-foreground)", flexShrink: 0 }} />
      </button>

      {open && (
        <div style={{
          position: "absolute", top: "calc(100% + 4px)", left: 0, right: 0,
          background: "var(--popover)", border: "1px solid var(--border-shadcn)",
          borderRadius: 8, boxShadow: "var(--shadow-md)", zIndex: 50, padding: 4,
        }}>
          {companies.map(c => {
            const cr = c.razon || c.razon_social || "";
            const cc = c.color || "var(--primary)";
            const ci = initials(cr, c.rfc);
            const isSelected = (c.id && c.id === company.id) || (c.empresa_id && c.empresa_id === company.empresa_id);
            return (
              <button
                key={c.id || c.empresa_id}
                onClick={() => { onChange(c); setOpen(false); }}
                style={{
                  width: "100%", textAlign: "left", padding: "6px 8px", borderRadius: 5,
                  display: "flex", alignItems: "center", gap: 8,
                  background: isSelected ? "var(--muted)" : "transparent",
                  border: "none", cursor: "pointer", fontFamily: "inherit",
                }}
              >
                <span className="avatar" style={{ background: `color-mix(in oklch, ${cc}, white 75%)`, color: cc, width: 22, height: 22, fontSize: 9, borderRadius: 4, flexShrink: 0 }}>{ci}</span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 12, fontWeight: 500, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{cr}</div>
                  <div className="mono" style={{ fontSize: 10, color: "var(--muted-foreground)" }}>{c.rfc}</div>
                </div>
                {isSelected && <Icon name="check" size={12} style={{ color: "var(--primary)", flexShrink: 0 }} />}
              </button>
            );
          })}
          <Separator className="my-1" />
          <button
            onClick={() => { onChangeWorkspace(); setOpen(false); }}
            style={{
              width: "100%", textAlign: "left", padding: "6px 8px", borderRadius: 5,
              display: "flex", alignItems: "center", gap: 8, background: "transparent",
              border: "none", cursor: "pointer", fontFamily: "inherit",
              fontSize: 12, color: "var(--primary)",
            }}
          >
            <Icon name="arrowRight" size={12} /> Cambiar empresa / período
          </button>
        </div>
      )}
    </div>
  );
}

function Topbar({ period, exitWorkspace }) {
  const [hovered, setHovered] = useState(false);
  return (
    <header style={{
      height: 48, flexShrink: 0,
      borderBottom: "1px solid var(--border-shadcn)",
      background: "var(--card)",
      display: "flex", alignItems: "center",
      padding: "0 20px", gap: 8,
    }}>
      <div style={{ flex: 1 }} />
      <button
        onClick={exitWorkspace}
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        style={{
          display: "inline-flex", alignItems: "center", gap: 6,
          padding: "4px 10px", borderRadius: 5,
          border: "1px solid var(--border-shadcn)",
          background: hovered ? "var(--muted)" : "var(--background)",
          cursor: "pointer", fontFamily: "inherit",
          fontSize: 12, color: "var(--foreground)",
          transition: "background 0.1s",
        }}
        title="Cambiar empresa o período"
      >
        <Icon name="calendar" size={12} style={{ color: "var(--muted-foreground)" }} />
        {period?.label || "Sin período"}
        <Icon name="chevronDown" size={11} style={{ color: "var(--muted-foreground)" }} />
      </button>
      <Button variant="ghost" size="sm" title="Buscar (⌘K)"><Icon name="search" size={14} /></Button>
      <Button variant="ghost" size="sm" title="Notificaciones"><Icon name="bell" size={14} /></Button>
    </header>
  );
}
