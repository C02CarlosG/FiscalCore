import { useState, useEffect, useRef } from "react";
import { setPeriodoEmpresa, getPeriodoSugerido } from "./auth.js";
import AgregarEmpresaModal from "./AgregarEmpresaModal.jsx";
import { API_URL, authHeaders } from "./lib/constants.js";

const AVATAR_PALETTE = [
  { bg: "rgba(6,182,212,0.15)",   text: "#06B6D4",  border: "rgba(6,182,212,0.3)"   },
  { bg: "rgba(99,102,241,0.15)",  text: "#818CF8",  border: "rgba(99,102,241,0.3)"  },
  { bg: "rgba(245,158,11,0.15)",  text: "#F59E0B",  border: "rgba(245,158,11,0.3)"  },
  { bg: "rgba(16,185,129,0.15)",  text: "#10B981",  border: "rgba(16,185,129,0.3)"  },
  { bg: "rgba(244,63,94,0.15)",   text: "#FB7185",  border: "rgba(244,63,94,0.3)"   },
  { bg: "rgba(168,85,247,0.15)",  text: "#C084FC",  border: "rgba(168,85,247,0.3)"  },
];

function getAvatarColor(rfc = "") {
  let h = 0;
  for (let i = 0; i < rfc.length; i++) h = (h * 31 + rfc.charCodeAt(i)) >>> 0;
  return AVATAR_PALETTE[h % AVATAR_PALETTE.length];
}

function getInitials(empresa) {
  const rz = empresa.razon_social ?? "";
  const words = rz.split(" ").filter(w => /^[A-ZÁÉÍÓÚÑ]/i.test(w[0] ?? ""));
  if (words.length >= 2) return (words[0][0] + words[1][0]).toUpperCase();
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
  return (empresa.rfc ?? "??").slice(0, 2).toUpperCase();
}

// RFC 12 chars = Persona Moral, 13 chars = Persona Física
function getTipoPersona(empresa) {
  if (empresa.tipo_persona) return empresa.tipo_persona;
  const rfc = (empresa.rfc ?? "").trim();
  return rfc.length <= 12 ? "Moral" : "Física";
}

function AvatarDropdown({ userData, onPerfil, onLogout }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  const nombre = userData?.nombre ?? "Contador";
  const initials = nombre.split(" ").slice(0, 2).map(p => p[0] ?? "").join("").toUpperCase() || "?";

  useEffect(() => {
    function h(e) { if (ref.current && !ref.current.contains(e.target)) setOpen(false); }
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, []);

  return (
    <div style={{ position: "relative" }} ref={ref}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          display: "flex", alignItems: "center", gap: 8,
          padding: "6px 10px", borderRadius: 8,
          border: "1px solid var(--border)",
          background: "transparent", cursor: "pointer",
          fontFamily: "inherit",
        }}
      >
        <div style={{
          width: 28, height: 28, borderRadius: "50%",
          background: "rgba(6,182,212,0.15)",
          border: "1px solid rgba(6,182,212,0.25)",
          display: "flex", alignItems: "center", justifyContent: "center",
          flexShrink: 0,
        }}>
          <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, fontWeight: 700, color: "var(--primary)" }}>{initials}</span>
        </div>
        <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--foreground)", maxWidth: 120, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {nombre.split(" ")[0]}
        </span>
        <svg style={{ width: 12, height: 12, color: "var(--muted-foreground)", transform: open ? "rotate(180deg)" : "none", transition: "transform 0.15s" }}
          viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
          <path d="M6 9l6 6 6-6"/>
        </svg>
      </button>
      {open && (
        <div style={{
          position: "absolute", right: 0, top: "calc(100% + 6px)",
          width: 208, background: "var(--card)", border: "1px solid var(--border)",
          borderRadius: 8, boxShadow: "var(--shadow-lg)", overflow: "hidden", zIndex: 50,
        }}>
          <div style={{ padding: "12px 16px", borderBottom: "1px solid var(--border)" }}>
            <p style={{ fontWeight: 600, fontSize: 14, color: "var(--foreground)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", margin: 0 }}>{nombre}</p>
            <p style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--muted-foreground)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", marginTop: 2, marginBottom: 0 }}>{userData?.email ?? ""}</p>
          </div>
          <button onClick={() => { setOpen(false); onPerfil(); }} style={{ width: "100%", display: "flex", alignItems: "center", gap: 10, padding: "10px 16px", textAlign: "left", fontSize: 14, color: "var(--foreground)", background: "transparent", border: "none", cursor: "pointer", fontFamily: "inherit" }}>
            <svg style={{ width: 14, height: 14, color: "var(--muted-foreground)" }} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>
            </svg>
            Mi perfil
          </button>
          <button onClick={() => { setOpen(false); onLogout(); }} style={{ width: "100%", display: "flex", alignItems: "center", gap: 10, padding: "10px 16px", textAlign: "left", fontSize: 14, color: "var(--destructive)", background: "transparent", border: "none", borderTop: "1px solid var(--border)", cursor: "pointer", fontFamily: "inherit" }}>
            <svg style={{ width: 14, height: 14 }} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
              <polyline points="16,17 21,12 16,7"/><line x1="21" y1="12" x2="9" y2="12"/>
            </svg>
            Cerrar sesión
          </button>
        </div>
      )}
    </div>
  );
}

export default function InicioPage({ empresas = [], userData, onSelectEmpresa, onLogout, onEmpresaAgregada, onPerfil }) {
  const [modalOpen,    setModalOpen]    = useState(false);
  const [editEmpresa,  setEditEmpresa]  = useState(null);
  const [editForm,     setEditForm]     = useState({});
  const [editSaving,   setEditSaving]   = useState(false);
  const [editError,    setEditError]    = useState("");
  const [empresasList, setEmpresasList] = useState(empresas);
  const [query,        setQuery]        = useState("");

  useEffect(() => { setEmpresasList(empresas); }, [empresas]);

  const filtered = empresasList.filter(e => {
    const q = query.trim().toLowerCase();
    if (!q) return true;
    return (e.razon_social ?? "").toLowerCase().includes(q) ||
           (e.rfc ?? "").toLowerCase().includes(q);
  });

  // Al hacer click en una fila, entramos directo con el período sugerido
  function handleEntrar(empresa) {
    const periodo = getPeriodoSugerido();
    setPeriodoEmpresa(empresa.empresa_id, periodo);
    onSelectEmpresa(empresa.empresa_id);
  }

  function handleSuccess(empresa) {
    setModalOpen(false);
    onEmpresaAgregada(empresa);
  }

  function abrirEdicion(e, empresa) {
    e.stopPropagation();
    setEditEmpresa(empresa);
    setEditForm({
      razon_social:        empresa.razon_social        ?? "",
      representante_legal: empresa.representante_legal ?? "",
      rfc_representante:   empresa.rfc_representante   ?? "",
    });
    setEditError("");
  }

  async function guardarEdicion() {
    if (!editEmpresa) return;
    setEditSaving(true); setEditError("");
    try {
      const res = await fetch(`${API_URL}/api/v1/empresas/${editEmpresa.empresa_id}`, {
        method: "PATCH",
        headers: { ...authHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify(editForm),
      });
      if (!res.ok) { const d = await res.json(); throw new Error(d.detail ?? "Error al guardar"); }
      setEmpresasList(prev =>
        prev.map(e => e.empresa_id === editEmpresa.empresa_id ? { ...e, ...editForm } : e)
      );
      setEditEmpresa(null);
    } catch (err) {
      setEditError(err.message ?? "Error desconocido");
    } finally {
      setEditSaving(false);
    }
  }

  return (
    <div style={{ minHeight: "100vh", background: "var(--background)", color: "var(--foreground)", display: "flex", flexDirection: "column" }}>

      {/* ── Header ── */}
      <header style={{
        flexShrink: 0,
        background: "color-mix(in srgb, var(--card) 95%, transparent)",
        backdropFilter: "blur(8px)",
        borderBottom: "1px solid var(--border)",
        zIndex: 10,
      }}>
        <div style={{ height: 1, background: "linear-gradient(to right, transparent, color-mix(in srgb, var(--primary) 50%, transparent), transparent)" }} />
        <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "0 24px", height: 52 }}>
          {/* Logo */}
          <div style={{ display: "flex", alignItems: "center", gap: 10, flexShrink: 0 }}>
            <div style={{
              width: 32, height: 32, borderRadius: 8,
              background: "rgba(6,182,212,0.13)",
              border: "1px solid rgba(6,182,212,0.28)",
              display: "flex", alignItems: "center", justifyContent: "center",
              fontFamily: "var(--font-mono)", fontWeight: 800, fontSize: 12,
              color: "var(--primary)", letterSpacing: "-0.02em",
            }}>FC</div>
            <div>
              <div style={{ fontFamily: "var(--font-display)", fontWeight: 700, fontSize: 16, color: "var(--foreground)", letterSpacing: "-0.02em", lineHeight: 1 }}>
                Fiscal<span style={{ opacity: 0.45 }}>Core</span>
              </div>
              <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--muted-foreground)", letterSpacing: "0.08em", textTransform: "uppercase", marginTop: 2 }}>AUDITORÍA · SAT MX</div>
            </div>
          </div>

          <div style={{ flex: 1 }} />

          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <button
              onClick={() => setModalOpen(true)}
              style={{
                display: "flex", alignItems: "center", gap: 6,
                fontFamily: "var(--font-mono)", fontSize: 11,
                padding: "5px 14px", height: 32, borderRadius: 7,
                border: "1px solid var(--border)",
                background: "transparent", cursor: "pointer",
                color: "var(--foreground)", fontWeight: 600,
              }}
            >
              <svg style={{ width: 12, height: 12 }} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
              </svg>
              Nueva empresa
            </button>
            <AvatarDropdown userData={userData} onPerfil={onPerfil} onLogout={onLogout} />
          </div>
        </div>
      </header>

      {/* ── Body ── */}
      <div style={{ flex: 1, overflow: "auto", padding: "36px 48px" }}>
        <div style={{ maxWidth: 960, margin: "0 auto" }}>

          {/* Título */}
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 24 }}>
            <h1 style={{
              fontFamily: "var(--font-display)",
              fontWeight: 700, fontSize: 22,
              color: "var(--foreground)",
              letterSpacing: "-0.02em", lineHeight: 1.2,
              margin: 0,
            }}>
              Empresas
            </h1>
            <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--muted-foreground)" }}>
              {empresasList.length} registro{empresasList.length !== 1 ? "s" : ""}
            </span>
          </div>

          {/* Buscador */}
          <div style={{ position: "relative", marginBottom: 16, maxWidth: 400 }}>
            <svg style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", width: 14, height: 14, color: "var(--muted-foreground)" }}
              viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/>
            </svg>
            <input
              value={query}
              onChange={e => setQuery(e.target.value)}
              placeholder="Buscar por razón social o RFC…"
              style={{
                width: "100%", height: 38, paddingLeft: 36, paddingRight: 12,
                borderRadius: 8, fontSize: 14,
                background: "var(--card)", border: "1px solid var(--border)",
                color: "var(--foreground)", outline: "none", fontFamily: "inherit",
                boxSizing: "border-box",
              }}
            />
          </div>

          {/* Tabla */}
          {filtered.length === 0 ? (
            <div style={{
              padding: "56px 24px", textAlign: "center",
              color: "var(--muted-foreground)", fontSize: 14,
              borderRadius: 10, border: "1.5px dashed var(--border)",
            }}>
              {empresasList.length === 0 ? (
                <>
                  <div style={{ fontSize: 32, marginBottom: 12, opacity: 0.3 }}>🏢</div>
                  <div style={{ fontWeight: 600, color: "var(--foreground)", marginBottom: 6, fontSize: 16 }}>Sin empresas registradas</div>
                  <div style={{ marginBottom: 20, fontSize: 13 }}>Agrega tu primer cliente para comenzar.</div>
                  <button onClick={() => setModalOpen(true)} style={{ display: "inline-flex", alignItems: "center", gap: 6, height: 36, padding: "0 20px", borderRadius: 7, fontSize: 13, fontWeight: 600, background: "var(--primary)", color: "var(--primary-foreground)", border: "none", cursor: "pointer", fontFamily: "inherit" }}>
                    <svg style={{ width: 14, height: 14 }} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
                    Agregar empresa
                  </button>
                </>
              ) : (
                <span>Sin resultados para "{query}"</span>
              )}
            </div>
          ) : (
            <div style={{ borderRadius: 10, border: "1px solid var(--border)", overflow: "hidden" }}>
              <table style={{ width: "100%", borderCollapse: "collapse" }}>
                <thead>
                  <tr style={{ background: "color-mix(in srgb, var(--primary) 10%, var(--card))" }}>
                    {[
                      { label: "",             width: 56  },
                      { label: "Razón Social", width: null },
                      { label: "RFC",          width: 160 },
                      { label: "Tipo",         width: 110 },
                      { label: "Acciones",     width: 110 },
                    ].map(({ label, width }, i) => (
                      <th key={i} style={{
                        padding: "11px 16px",
                        textAlign: "left",
                        width: width ?? undefined,
                        fontSize: 11,
                        fontWeight: 700,
                        fontFamily: "var(--font-sans)",
                        letterSpacing: "0.04em",
                        textTransform: "uppercase",
                        color: "var(--muted-foreground)",
                        borderBottom: "1px solid var(--border)",
                        whiteSpace: "nowrap",
                      }}>{label}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((e, idx) => {
                    const color    = getAvatarColor(e.rfc ?? "");
                    const initials = getInitials(e);
                    const tipo     = getTipoPersona(e);
                    return (
                      <tr
                        key={e.empresa_id}
                        style={{
                          cursor: "pointer",
                          background: idx % 2 === 0 ? "var(--card)" : "color-mix(in srgb, var(--muted) 30%, var(--card))",
                          transition: "background 0.1s",
                        }}
                        onMouseEnter={ev => ev.currentTarget.style.background = "color-mix(in srgb, var(--primary) 6%, var(--card))"}
                        onMouseLeave={ev => ev.currentTarget.style.background = idx % 2 === 0 ? "var(--card)" : "color-mix(in srgb, var(--muted) 30%, var(--card))"}
                        onClick={() => handleEntrar(e)}
                      >
                        {/* Avatar */}
                        <td style={{ padding: "10px 12px", width: 44 }}>
                          <div style={{
                            width: 36, height: 36, borderRadius: 8,
                            background: color.bg, color: color.text,
                            border: `1px solid ${color.border}`,
                            display: "flex", alignItems: "center", justifyContent: "center",
                            fontFamily: "var(--font-mono)", fontWeight: 800, fontSize: 11,
                          }}>
                            {initials}
                          </div>
                        </td>
                        {/* Razón social */}
                        <td style={{ padding: "12px 16px" }}>
                          <div style={{ fontWeight: 600, fontSize: 14, color: "var(--foreground)", lineHeight: 1.3 }}>
                            {e.razon_social ?? e.rfc}
                          </div>
                          {e.regimen_fiscal && (
                            <div style={{ fontSize: 11, color: "var(--muted-foreground)", marginTop: 3, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: 340 }}>
                              {e.regimen_fiscal}
                            </div>
                          )}
                        </td>
                        {/* RFC */}
                        <td style={{ padding: "12px 16px" }}>
                          <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: color.text, fontWeight: 600 }}>
                            {e.rfc}
                          </span>
                        </td>
                        {/* Tipo */}
                        <td style={{ padding: "12px 16px" }}>
                          <span style={{
                            display: "inline-block", padding: "3px 10px", borderRadius: 999,
                            fontFamily: "var(--font-sans)", fontSize: 11, fontWeight: 600,
                            border: "1px solid",
                            ...(tipo === "Física"
                              ? { background: "rgba(79,142,247,0.12)", borderColor: "rgba(79,142,247,0.35)", color: "#4f8ef7" }
                              : { background: "rgba(139,124,248,0.12)", borderColor: "rgba(139,124,248,0.35)", color: "#8b7cf8" }
                            ),
                          }}>
                            {tipo}
                          </span>
                        </td>
                        {/* Acciones */}
                        <td style={{ padding: "10px 14px" }} onClick={ev => ev.stopPropagation()}>
                          <button
                            onClick={ev => abrirEdicion(ev, e)}
                            style={{
                              display: "inline-flex", alignItems: "center", gap: 5,
                              padding: "5px 12px", borderRadius: 6, fontSize: 12,
                              fontWeight: 600, background: "transparent",
                              color: "var(--muted-foreground)",
                              border: "1px solid var(--border)",
                              cursor: "pointer", fontFamily: "inherit",
                              transition: "border-color 0.1s, color 0.1s",
                            }}
                            onMouseEnter={ev => { ev.currentTarget.style.color = "var(--foreground)"; ev.currentTarget.style.borderColor = "var(--foreground)"; }}
                            onMouseLeave={ev => { ev.currentTarget.style.color = "var(--muted-foreground)"; ev.currentTarget.style.borderColor = "var(--border)"; }}
                          >
                            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                              <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                              <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                            </svg>
                            Editar
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

        </div>
      </div>

      {/* ── Modal Agregar ── */}
      <AgregarEmpresaModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onSuccess={handleSuccess}
      />

      {/* ── Modal Editar ── */}
      {editEmpresa && (
        <div style={{
          position: "fixed", inset: 0, zIndex: 100,
          background: "rgba(0,0,0,0.6)", backdropFilter: "blur(4px)",
          display: "flex", alignItems: "center", justifyContent: "center",
        }} onClick={() => setEditEmpresa(null)}>
          <div
            onClick={ev => ev.stopPropagation()}
            style={{
              width: 460, background: "var(--card)",
              borderRadius: 14, border: "1px solid var(--border)",
              boxShadow: "0 24px 48px rgba(0,0,0,0.4)",
              overflow: "hidden",
            }}
          >
            <div style={{
              padding: "18px 22px", borderBottom: "1px solid var(--border)",
              background: "color-mix(in srgb, var(--primary) 8%, var(--card))",
              display: "flex", alignItems: "center", justifyContent: "space-between",
            }}>
              <div>
                <h3 style={{ margin: 0, fontSize: 17, fontWeight: 800, color: "var(--foreground)" }}>Editar empresa</h3>
                <p style={{ margin: "3px 0 0", fontSize: 11, fontFamily: "var(--font-mono)", color: "var(--muted-foreground)" }}>{editEmpresa.rfc}</p>
              </div>
              <button onClick={() => setEditEmpresa(null)} style={{ background: "transparent", border: "none", cursor: "pointer", color: "var(--muted-foreground)", fontSize: 20, lineHeight: 1 }}>×</button>
            </div>
            <div style={{ padding: "20px 22px", display: "flex", flexDirection: "column", gap: 14 }}>
              {[
                { id: "razon_social",        label: "Razón Social",          placeholder: "Empresa SA de CV" },
                { id: "representante_legal", label: "Representante Legal",   placeholder: "Juan Pérez García" },
                { id: "rfc_representante",   label: "RFC del Representante", placeholder: "PEGJ800101ABC" },
              ].map(({ id, label, placeholder }) => (
                <div key={id} style={{ display: "flex", flexDirection: "column", gap: 5 }}>
                  <label style={{ fontSize: 10, fontFamily: "var(--font-mono)", fontWeight: 600, letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--muted-foreground)" }}>{label}</label>
                  <input
                    value={editForm[id] ?? ""}
                    onChange={ev => setEditForm(p => ({ ...p, [id]: ev.target.value }))}
                    placeholder={placeholder}
                    style={{
                      padding: "9px 12px", borderRadius: 7, fontSize: 13,
                      background: "var(--background)", border: "1.5px solid var(--border)",
                      color: "var(--foreground)", fontFamily: "var(--font-mono)", outline: "none",
                      transition: "border-color 0.15s",
                    }}
                    onFocus={ev => ev.target.style.borderColor = "var(--primary)"}
                    onBlur={ev => ev.target.style.borderColor = "var(--border)"}
                  />
                </div>
              ))}
              {editError && (
                <div style={{ padding: "9px 12px", borderRadius: 7, background: "rgba(248,113,113,0.08)", border: "1px solid rgba(248,113,113,0.3)", fontSize: 12, color: "#F87171" }}>
                  {editError}
                </div>
              )}
              <div style={{ display: "flex", gap: 10, marginTop: 4 }}>
                <button onClick={() => setEditEmpresa(null)} style={{ flex: 1, padding: "10px", borderRadius: 8, border: "1px solid var(--border)", background: "transparent", color: "var(--muted-foreground)", fontWeight: 600, fontSize: 13, cursor: "pointer", fontFamily: "inherit" }}>
                  Cancelar
                </button>
                <button onClick={guardarEdicion} disabled={editSaving} style={{ flex: 2, padding: "10px", borderRadius: 8, border: "none", background: "var(--primary)", color: "var(--primary-foreground)", fontWeight: 700, fontSize: 13, cursor: "pointer", fontFamily: "inherit", opacity: editSaving ? 0.7 : 1 }}>
                  {editSaving ? "Guardando…" : "Guardar cambios"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
