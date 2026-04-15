import { useState, useEffect, useRef } from "react";
import { Button } from "./components/ui/button";
import AgregarEmpresaModal from "./AgregarEmpresaModal.jsx";

const PILLS = [
  { icon: "⚡", label: "Cierre mensual en minutos" },
  { icon: "🛡", label: "Riesgos SAT detectados al instante" },
  { icon: "💰", label: "Flujo de efectivo sin brechas" },
  { icon: "📋", label: "DIOT y declaraciones sin sorpresas" },
];

function LogoMark() {
  return (
    <div className="w-7 h-7 rounded-md bg-primary/20 border border-primary/30 flex items-center justify-center flex-shrink-0">
      <div className="grid grid-cols-2 gap-0.5">
        {[0.9, 0.4, 0.4, 0.9].map((o, i) => (
          <div key={i} className="w-1.5 h-1.5 rounded-sm bg-primary" style={{ opacity: o }} />
        ))}
      </div>
    </div>
  );
}

function AvatarDropdown({ userData, onPerfil, onLogout }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  const nombre = userData?.nombre ?? "Contador";
  const initials = nombre
    .split(" ")
    .slice(0, 2)
    .map(p => p[0] ?? "")
    .join("")
    .toUpperCase() || "?";

  useEffect(() => {
    function handleClick(e) {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen(o => !o)}
        className="flex items-center gap-2.5 px-2.5 py-1.5 rounded-lg border border-border hover:border-primary/40 hover:bg-secondary/30 transition-all duration-150 focus:outline-none"
      >
        {/* Avatar circular */}
        <div className="w-7 h-7 rounded-full bg-primary/20 border border-primary/30 flex items-center justify-center flex-shrink-0">
          <span className="font-mono text-[11px] font-bold text-primary">{initials}</span>
        </div>
        {/* Nombre */}
        <span className="hidden sm:block font-mono text-[11px] text-foreground max-w-[120px] truncate">
          {nombre.split(" ")[0]}
        </span>
        {/* Chevron */}
        <svg
          className={`w-3 h-3 text-muted-foreground transition-transform duration-150 ${open ? "rotate-180" : ""}`}
          viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"
        >
          <path d="M6 9l6 6 6-6"/>
        </svg>
      </button>

      {/* Dropdown */}
      {open && (
        <div className="absolute right-0 top-full mt-1.5 w-52 bg-card border border-border rounded-lg shadow-xl overflow-hidden z-50">
          {/* Cabecera */}
          <div className="px-4 py-3 border-b border-border/60">
            <p className="font-display font-semibold text-sm text-foreground truncate">{nombre}</p>
            <p className="font-mono text-[10px] text-muted-foreground truncate mt-0.5">
              {userData?.email ?? ""}
            </p>
          </div>
          {/* Opciones */}
          <button
            onClick={() => { setOpen(false); onPerfil(); }}
            className="w-full flex items-center gap-2.5 px-4 py-2.5 text-left text-sm text-foreground hover:bg-secondary/40 transition-colors"
          >
            <svg className="w-3.5 h-3.5 text-muted-foreground" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
              <circle cx="12" cy="7" r="4"/>
            </svg>
            Mi perfil
          </button>
          <button
            onClick={() => { setOpen(false); onLogout(); }}
            className="w-full flex items-center gap-2.5 px-4 py-2.5 text-left text-sm text-red-400 hover:bg-red-500/10 transition-colors border-t border-border/40"
          >
            <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
              <polyline points="16,17 21,12 16,7"/>
              <line x1="21" y1="12" x2="9" y2="12"/>
            </svg>
            Cerrar sesión
          </button>
        </div>
      )}
    </div>
  );
}

function EmpresaCard({ empresa, onClick }) {
  const initials = (empresa.rfc ?? "??").slice(0, 2).toUpperCase();
  return (
    <button
      onClick={onClick}
      className="w-full text-left bg-card border border-border rounded-lg p-5 hover:border-primary/40 hover:bg-secondary/20 transition-all duration-200 group focus:outline-none focus:ring-2 focus:ring-primary/30"
    >
      <div className="flex items-start gap-4">
        <div className="w-10 h-10 rounded-lg bg-primary/15 border border-primary/25 flex items-center justify-center flex-shrink-0">
          <span className="font-mono text-xs font-bold text-primary">{initials}</span>
        </div>
        <div className="flex-1 min-w-0">
          <p className="font-display font-semibold text-sm text-foreground leading-snug line-clamp-2 group-hover:text-primary transition-colors">
            {empresa.razon_social ?? empresa.rfc}
          </p>
          <p className="font-mono text-[11px] text-primary mt-1 tracking-wider">{empresa.rfc}</p>
          {empresa.regimen_fiscal && (
            <p className="text-[11px] text-muted-foreground mt-0.5 truncate">{empresa.regimen_fiscal}</p>
          )}
        </div>
        <svg
          className="w-4 h-4 text-muted-foreground group-hover:text-primary group-hover:translate-x-0.5 transition-all duration-200 flex-shrink-0 mt-0.5"
          viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
        >
          <path d="M5 12h14M12 5l7 7-7 7"/>
        </svg>
      </div>
      <div className="mt-3 pt-3 border-t border-border/50">
        <span className="font-mono text-[10px] text-primary/70 group-hover:text-primary transition-colors">
          Ver dashboard →
        </span>
      </div>
    </button>
  );
}

function EmptyState({ onAgregar }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <div className="w-16 h-16 rounded-2xl bg-card border border-border flex items-center justify-center mb-5">
        <svg className="w-8 h-8 text-muted-foreground" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
          <path d="M3 21h18M3 7v1a3 3 0 0 0 6 0V7m0 1a3 3 0 0 0 6 0V7m0 1a3 3 0 0 0 6 0V7H3l2-4h14l2 4"/>
        </svg>
      </div>
      <h3 className="font-display font-semibold text-foreground text-lg mb-2">Sin empresas registradas</h3>
      <p className="text-muted-foreground text-sm max-w-sm mb-6">
        Agrega tu primer cliente usando el botón{" "}
        <span className="text-primary font-medium">"+ Agregar empresa"</span>.
      </p>
      <Button
        onClick={onAgregar}
        className="bg-primary hover:bg-primary/90 text-primary-foreground font-semibold gap-2"
      >
        <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
          <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
        </svg>
        Agregar empresa
      </Button>
    </div>
  );
}

export default function InicioPage({ empresas = [], userData, onSelectEmpresa, onLogout, onEmpresaAgregada, onPerfil }) {
  const [modalOpen, setModalOpen] = useState(false);

  function handleSuccess(empresa) {
    setModalOpen(false);
    onEmpresaAgregada(empresa);
  }

  return (
    <div className="min-h-screen bg-background text-foreground">

      {/* Header */}
      <header className="sticky top-0 z-50 bg-card/95 backdrop-blur-sm border-b border-border">
        <div className="h-px bg-gradient-to-r from-transparent via-primary/50 to-transparent"/>
        <div className="max-w-screen-xl mx-auto px-7 flex items-center gap-4 h-14">

          <div className="flex items-center gap-2.5 flex-shrink-0">
            <LogoMark />
            <div>
              <div className="font-display font-bold text-sm text-foreground tracking-tight">
                Fiscal<span className="text-primary">Core</span>
              </div>
              <div className="font-mono text-[8px] text-muted-foreground tracking-widest uppercase">AUDITORÍA · SAT MX</div>
            </div>
          </div>

          <div className="flex-1"/>

          <div className="flex items-center gap-2">
            {/* Botón principal: agregar empresa */}
            <Button
              onClick={() => setModalOpen(true)}
              className="bg-primary hover:bg-primary/90 text-primary-foreground font-semibold text-sm gap-1.5 h-8 px-3"
            >
              <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
              </svg>
              <span className="hidden sm:inline">Agregar empresa</span>
              <span className="sm:hidden">+ Empresa</span>
            </Button>

            {/* Avatar con dropdown */}
            <AvatarDropdown
              userData={userData}
              onPerfil={onPerfil}
              onLogout={onLogout}
            />
          </div>
        </div>
      </header>

      {/* Contenido */}
      <main className="max-w-screen-xl mx-auto px-7">

        {/* Hero */}
        <section className="pt-10 pb-8">
          <p className="font-mono text-[11px] text-primary tracking-widest uppercase mb-3">
            Bienvenido, {userData?.nombre?.split(" ")[0] ?? "contador"}
          </p>
          <h1 className="font-display font-bold text-3xl text-foreground mb-3 leading-tight">
            Auditoría fiscal preventiva<br/>
            <span className="text-primary">para tu despacho</span>
          </h1>
          <p className="text-muted-foreground text-sm max-w-xl mb-6">
            Concilia CFDIs con estados bancarios, detecta riesgos SAT antes del cierre y gestiona el cumplimiento de todos tus clientes desde un solo lugar.
          </p>
          <div className="flex flex-wrap gap-2">
            {PILLS.map(({ icon, label }) => (
              <div
                key={label}
                className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-primary/10 border border-primary/20 text-sm text-foreground/80"
              >
                <span>{icon}</span>
                <span className="font-mono text-[11px] tracking-wide">{label}</span>
              </div>
            ))}
          </div>
        </section>

        <div className="h-px bg-border mb-6"/>

        {/* Sección de empresas */}
        <section className="pb-16">
          <div className="flex items-center justify-between mb-5">
            <div className="flex items-center gap-3">
              <span className="font-mono text-[11px] text-muted-foreground tracking-widest uppercase">
                Tus empresas
              </span>
              {empresas.length > 0 && (
                <span className="font-mono text-[10px] bg-primary/15 text-primary border border-primary/25 rounded-full px-2 py-0.5">
                  {empresas.length}
                </span>
              )}
            </div>
            {/* Botón secundario visible en la sección */}
            {empresas.length > 0 && (
              <button
                onClick={() => setModalOpen(true)}
                className="flex items-center gap-1.5 font-mono text-[11px] text-primary hover:text-primary/80 transition-colors"
              >
                <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
                </svg>
                Agregar cliente
              </button>
            )}
          </div>

          {empresas.length === 0 ? (
            <EmptyState onAgregar={() => setModalOpen(true)} />
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
              {empresas.map(e => (
                <EmpresaCard
                  key={e.empresa_id}
                  empresa={e}
                  onClick={() => onSelectEmpresa(e.empresa_id)}
                />
              ))}
            </div>
          )}
        </section>
      </main>

      <AgregarEmpresaModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onSuccess={handleSuccess}
      />
    </div>
  );
}
