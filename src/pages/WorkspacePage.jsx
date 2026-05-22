import { useState, useEffect, useRef } from "react";
import Icon from "../icons.jsx";
import { Button } from "../components/ui/button.jsx";
import { Input } from "../components/ui/input.jsx";
import { Separator } from "../components/ui/separator.jsx";
import { Badge } from "../components/ui/badge.jsx";
import { api } from "../lib/api.js";
import { useAuth } from "../context/AuthContext.jsx";
import { useApp, periodLabel } from "../context/AppContext.jsx";

const REGIMENES = [
  { value: "601", label: "601 – General de Ley Personas Morales" },
  { value: "603", label: "603 – Personas Morales con Fines no Lucrativos" },
  { value: "605", label: "605 – Sueldos y Salarios" },
  { value: "606", label: "606 – Arrendamiento" },
  { value: "612", label: "612 – Personas Físicas con Actividades Empresariales y Profesionales" },
  { value: "616", label: "616 – Sin Obligaciones Fiscales" },
  { value: "621", label: "621 – Incorporación Fiscal" },
  { value: "626", label: "626 – Régimen Simplificado de Confianza" },
];

function emptyForm() {
  return { rfc: "", razon_social: "", regimen_fiscal: "", cp_fiscal: "" };
}

const MONTH_NAMES = ["Enero","Febrero","Marzo","Abril","Mayo","Junio","Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"];

function initials(razon = "", rfc = "") {
  return razon.split(" ").filter(w => /^[A-ZÁÉÍÓÚÑ]/.test(w[0] || "")).slice(0, 2).map(w => w[0]).join("") || rfc.slice(0, 2);
}

export default function WorkspacePage() {
  const { logout } = useAuth();
  const { companies, setCompanies, enterWorkspace } = useApp();

  const [loading, setLoading]   = useState(true);
  const [err, setErr]           = useState("");
  const [query, setQuery]       = useState("");
  const [selId, setSelId]       = useState(null);

  const [form, setForm]         = useState(emptyForm());
  const [saving, setSaving]     = useState(false);
  const [addError, setAddError] = useState("");
  const [addOk, setAddOk]       = useState("");
  const [parsing, setParsing]   = useState(false);
  const [parseError, setParseError] = useState("");
  const [parsedFileName, setParsedFileName] = useState("");
  const [addMode, setAddMode]   = useState("manual");
  const fileInputRef            = useRef(null);

  const [month, setMonth]       = useState(() => {
    const now = new Date();
    const target = now.getDate() < 17
      ? new Date(now.getFullYear(), now.getMonth() - 1, 1)
      : new Date(now.getFullYear(), now.getMonth(), 1);
    return `${target.getFullYear()}-${String(target.getMonth() + 1).padStart(2, "0")}`;
  });

  useEffect(() => {
    api.empresas.list()
      .then(data => {
        const list = Array.isArray(data) ? data : (data.empresas || []);
        const withColor = list.map((c, i) => ({
          ...c,
          color: c.color || `oklch(0.65 0.15 ${[262, 160, 30, 300, 200][i % 5]})`,
        }));
        setCompanies(withColor);
        setSelId(withColor[0]?.empresa_id || withColor[0]?.id || null);
      })
      .catch(() => setErr("No se pudieron cargar las empresas."))
      .finally(() => setLoading(false));
  }, []);

  const filtered = companies.filter(c => {
    const q = query.trim().toLowerCase();
    const razon = (c.razon_social || c.razon || "").toLowerCase();
    return !q || razon.includes(q) || c.rfc.toLowerCase().includes(q);
  });

  const selected = companies.find(c => (c.empresa_id || c.id) === selId);

  const [y, m] = month.split("-");
  const label = `${MONTH_NAMES[parseInt(m, 10) - 1]} ${y}`;

  const goNext = () => {
    if (!selected) return;
    enterWorkspace(selected, { month, label });
  };

  async function handleConstanciaFile(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    setParsing(true);
    setParseError("");
    setParsedFileName(file.name);
    try {
      const res = await api.constancia.parsear(file);
      setForm({
        rfc:            (res.rfc || "").toUpperCase(),
        razon_social:   res.razon_social || "",
        regimen_fiscal: res.regimen_fiscal || res.regimen || "",
        cp_fiscal:      res.cp_fiscal || res.codigo_postal || "",
      });
      setAddMode("manual");
    } catch (err) {
      setParseError(err.message || "No se pudo leer la constancia.");
    } finally {
      setParsing(false);
    }
  }

  async function handleSaveFirstEmpresa() {
    setAddError("");
    setAddOk("");
    if (!form.rfc.trim())         { setAddError("El RFC es requerido."); return; }
    if (!form.razon_social.trim()) { setAddError("La razón social es requerida."); return; }
    setSaving(true);
    try {
      await api.empresas.add({
        rfc:            form.rfc.toUpperCase().trim(),
        razon_social:   form.razon_social.trim(),
        regimen_fiscal: form.regimen_fiscal,
        cp_fiscal:      form.cp_fiscal.trim(),
      });
      const lista = await api.empresas.list();
      const withColor = (Array.isArray(lista) ? lista : (lista.empresas || [])).map((c, i) => ({
        ...c,
        color: c.color || `oklch(0.65 0.15 ${[262, 160, 30, 300, 200][i % 5]})`,
      }));
      setCompanies(withColor);
      setSelId(withColor[0]?.empresa_id || withColor[0]?.id || null);
    } catch (err) {
      setAddError(err.message || "No se pudo agregar la empresa.");
    } finally {
      setSaving(false);
    }
  }

  const topbar = (
    <div style={{ padding: "12px 24px", display: "flex", alignItems: "center", gap: 12, borderBottom: "1px solid var(--border-shadcn)", background: "var(--card)" }}>
      <div style={{ width: 24, height: 24, borderRadius: 6, background: "var(--primary)", display: "grid", placeItems: "center", color: "var(--primary-foreground)", fontWeight: 700, fontFamily: "var(--font-mono)", fontSize: 11 }}>FC</div>
      <span style={{ fontWeight: 650, fontSize: 14, letterSpacing: "-0.01em" }}>FiscalCore</span>
      <div style={{ flex: 1 }} />
      <Button variant="ghost" size="sm" onClick={logout}><Icon name="logout" size={13} /> Salir</Button>
    </div>
  );

  /* ── Estado de carga ── */
  if (loading) {
    return (
      <div style={{ minHeight: "100vh", background: "var(--muted)", display: "flex", flexDirection: "column" }}>
        {topbar}
        <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", color: "var(--muted-foreground)", fontSize: 13 }}>
          Cargando…
        </div>
      </div>
    );
  }

  /* ── Sin empresas: formulario de registro ── */
  if (!err && companies.length === 0) {
    const fg = { display: "flex", flexDirection: "column", gap: 4 };
    const lbl = { display: "block", fontSize: 11, fontFamily: "var(--font-mono)", textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--muted-foreground)", marginBottom: 5 };
    return (
      <div style={{ minHeight: "100vh", background: "var(--muted)", display: "flex", flexDirection: "column" }}>
        {topbar}
        <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", padding: "clamp(24px,4vw,48px)" }}>
          <div style={{ width: "100%", maxWidth: 480, background: "var(--card)", borderRadius: 12, border: "1px solid var(--border-shadcn)", padding: "clamp(24px,3vw,40px)", display: "flex", flexDirection: "column", gap: 20 }}>

            <div>
              <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--muted-foreground)", marginBottom: 6 }}>Bienvenido</div>
              <h1 style={{ fontFamily: "Georgia, serif", fontWeight: 400, fontSize: "clamp(22px,3vw,28px)", letterSpacing: "-0.02em", lineHeight: 1.15, marginBottom: 6 }}>
                Registra tu primera empresa
              </h1>
              <p style={{ color: "var(--muted-foreground)", fontSize: 13 }}>
                Agrega un contribuyente para comenzar a usar la plataforma.
              </p>
            </div>

            <div style={{ display: "flex", gap: 6 }}>
              <Button variant={addMode === "manual" ? "primary" : "default"} size="sm" onClick={() => { setAddMode("manual"); setAddError(""); }}>
                Manual
              </Button>
              <Button variant={addMode === "constancia" ? "primary" : "default"} size="sm" onClick={() => { setAddMode("constancia"); setAddError(""); }}>
                <Icon name="file" size={12} /> Constancia SAT
              </Button>
            </div>

            {addMode === "constancia" && (
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                <div style={{ fontSize: 12, color: "var(--muted-foreground)" }}>
                  Sube el PDF de tu constancia de situación fiscal para auto-rellenar los datos.
                </div>
                <div
                  style={{ border: "1.5px dashed var(--border-shadcn)", borderRadius: 8, padding: "20px 16px", display: "flex", flexDirection: "column", alignItems: "center", gap: 8, cursor: "pointer", background: "var(--muted)" }}
                  onClick={() => fileInputRef.current?.click()}
                >
                  <Icon name="upload" size={22} style={{ color: "var(--muted-foreground)" }} />
                  <div style={{ fontSize: 12, color: "var(--muted-foreground)", textAlign: "center" }}>
                    {parsing ? "Leyendo constancia…" : parsedFileName || "Haz clic para seleccionar un PDF"}
                  </div>
                  <input ref={fileInputRef} type="file" accept=".pdf" style={{ display: "none" }} onChange={handleConstanciaFile} />
                </div>
                {parseError && (
                  <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "10px 14px", borderRadius: 7, fontSize: 13, background: "var(--danger-bg)", border: "1px solid var(--danger-border)", color: "var(--destructive)" }}>
                    <Icon name="alert" size={14} style={{ flexShrink: 0 }} /> {parseError}
                  </div>
                )}
              </div>
            )}

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
              <div style={fg}>
                <label style={lbl}>RFC <span style={{ color: "var(--destructive)" }}>*</span></label>
                <Input value={form.rfc} placeholder="XAXX010101000" maxLength={13}
                  onChange={e => { setForm(f => ({ ...f, rfc: e.target.value.toUpperCase() })); setAddError(""); }} />
              </div>
              <div style={fg}>
                <label style={lbl}>CP Fiscal</label>
                <Input value={form.cp_fiscal} placeholder="06600" maxLength={5}
                  onChange={e => { setForm(f => ({ ...f, cp_fiscal: e.target.value })); setAddError(""); }} />
              </div>
              <div style={{ ...fg, gridColumn: "1 / -1" }}>
                <label style={lbl}>Razón Social <span style={{ color: "var(--destructive)" }}>*</span></label>
                <Input value={form.razon_social} placeholder="EMPRESA EJEMPLO S.A. DE C.V."
                  onChange={e => { setForm(f => ({ ...f, razon_social: e.target.value })); setAddError(""); }} />
              </div>
              <div style={{ ...fg, gridColumn: "1 / -1" }}>
                <label style={lbl}>Régimen Fiscal</label>
                <select value={form.regimen_fiscal} onChange={e => setForm(f => ({ ...f, regimen_fiscal: e.target.value }))}
                  style={{ height: 32, width: "100%", borderRadius: 4, border: "1px solid var(--input)", background: "var(--card)", padding: "0 10px", fontSize: 12, color: "var(--foreground)", fontFamily: "inherit", outline: "none" }}>
                  <option value="">Selecciona régimen…</option>
                  {REGIMENES.map(r => <option key={r.value} value={r.value}>{r.label}</option>)}
                </select>
              </div>
            </div>

            {addError && (
              <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "10px 14px", borderRadius: 7, fontSize: 13, background: "var(--danger-bg)", border: "1px solid var(--danger-border)", color: "var(--destructive)" }}>
                <Icon name="alert" size={14} style={{ flexShrink: 0 }} /> {addError}
              </div>
            )}

            <Button variant="primary" size="lg" style={{ width: "100%", justifyContent: "center" }} disabled={saving} onClick={handleSaveFirstEmpresa}>
              {saving ? "Guardando…" : "Registrar empresa"} {!saving && <Icon name="arrowRight" size={14} />}
            </Button>
          </div>
        </div>
      </div>
    );
  }

  /* ── Con empresas: selector + período ── */
  return (
    <div style={{ minHeight: "100vh", background: "var(--muted)", display: "flex", flexDirection: "column" }}>
      {topbar}

      <div style={{ flex: 1, display: "grid", gridTemplateColumns: "minmax(0,1.4fr) minmax(320px,1fr)", gap: 0 }}>
        {/* Left: company list */}
        <div style={{ padding: "clamp(24px,3vw,40px)", overflowY: "auto" }}>
          <div style={{ maxWidth: 720, margin: "0 auto" }}>
            <h1 style={{ fontFamily: "Georgia, serif", fontWeight: 400, fontSize: "clamp(24px,3.2vw,36px)", letterSpacing: "-0.02em", lineHeight: 1.1, marginBottom: 6 }}>
              Selecciona tu empresa
            </h1>
            <p style={{ color: "var(--muted-foreground)", fontSize: 14, marginBottom: 24, maxWidth: 480 }}>
              Elige un contribuyente y el período de trabajo para continuar.
            </p>

            {err && (
              <div className="flex items-center gap-2 p-3 rounded-md bg-[var(--danger-bg)] text-destructive text-[13px]" style={{ marginBottom: 16 }}>
                <Icon name="alert" size={14} /> {err}
              </div>
            )}

            <div className="flex items-center gap-2" style={{ marginBottom: 16 }}>
              <div style={{ position: "relative", flex: 1 }}>
                <Icon name="search" size={14} style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", color: "var(--muted-foreground)" }} />
                <Input value={query} onChange={e => setQuery(e.target.value)} placeholder="Buscar por razón social o RFC…" style={{ paddingLeft: 30 }} />
              </div>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(240px,1fr))", gap: 10 }}>
              {filtered.map(c => {
                const id = c.empresa_id || c.id;
                const razon = c.razon_social || c.razon || "";
                const color = c.color || "var(--primary)";
                const ini = initials(razon, c.rfc);
                const active = selId === id;
                return (
                  <button key={id} onClick={() => setSelId(id)}
                    style={{
                      textAlign: "left", padding: 14, borderRadius: 8, cursor: "pointer",
                      fontFamily: "inherit", display: "flex", flexDirection: "column", gap: 8,
                      border: `1.5px solid ${active ? "var(--primary)" : "var(--border-shadcn)"}`,
                      background: active ? "color-mix(in oklch, var(--primary), white 93%)" : "var(--card)",
                      boxShadow: active ? "0 0 0 3px color-mix(in oklch, var(--primary), transparent 85%)" : "var(--shadow-xs)",
                      transition: "all 0.12s",
                    }}
                  >
                    <div className="flex items-center gap-2.5">
                      <span className="avatar" style={{ background: `color-mix(in oklch, ${color}, white 70%)`, color, width: 34, height: 34, borderRadius: 8, fontSize: 12, fontWeight: 600, flexShrink: 0 }}>{ini}</span>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontSize: 13, fontWeight: 600, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{razon}</div>
                        <div className="mono" style={{ fontSize: 10, color: "var(--muted-foreground)" }}>{c.rfc}</div>
                      </div>
                      {active && <Icon name="check" size={14} style={{ color: "var(--primary)", flexShrink: 0 }} />}
                    </div>
                    <div style={{ fontSize: 10, color: "var(--muted-foreground)" }}>
                      {c.regimen_fiscal || "Sin régimen registrado"}
                    </div>
                  </button>
                );
              })}
              {filtered.length === 0 && (
                <div style={{ padding: 32, textAlign: "center", color: "var(--muted-foreground)", border: "1px dashed var(--border-shadcn)", borderRadius: 8, gridColumn: "1/-1", fontSize: 13 }}>
                  Sin resultados para "{query}".
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Right: period + summary */}
        <div style={{ borderLeft: "1px solid var(--border-shadcn)", background: "var(--card)", padding: "clamp(24px,3vw,40px)", display: "flex", flexDirection: "column", gap: 20 }}>
          <div>
            <h2 style={{ fontFamily: "Georgia, serif", fontWeight: 400, fontSize: 22, letterSpacing: "-0.015em", marginBottom: 4 }}>
              Período de trabajo
            </h2>
            <p style={{ color: "var(--muted-foreground)", fontSize: 13 }}>Se aplicará a todos los módulos.</p>
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="text-[11px] text-muted-foreground font-medium uppercase tracking-wider">Mes</label>
            <Input type="month" value={month} onChange={e => setMonth(e.target.value)} />
          </div>

          <Separator />

          {selected && (
            <div style={{ padding: 14, borderRadius: 8, border: "1px solid var(--border-shadcn)", background: "var(--muted)", display: "flex", flexDirection: "column", gap: 10 }}>
              <div style={{ fontSize: 10, color: "var(--muted-foreground)", fontFamily: "var(--font-mono)", letterSpacing: "0.08em", textTransform: "uppercase" }}>Resumen de selección</div>
              <div className="flex items-center gap-2.5">
                <span className="avatar" style={{
                  background: `color-mix(in oklch, ${selected.color || "var(--primary)"}, white 70%)`,
                  color: selected.color || "var(--primary)",
                  width: 32, height: 32, borderRadius: 8, fontSize: 11, fontWeight: 600, flexShrink: 0,
                }}>{initials(selected.razon_social || selected.razon, selected.rfc)}</span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 600, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{selected.razon_social || selected.razon}</div>
                  <div className="mono" style={{ fontSize: 10, color: "var(--muted-foreground)" }}>{selected.rfc} · {selected.regimen_fiscal || "—"}</div>
                </div>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: 12 }}>
                <span style={{ color: "var(--muted-foreground)" }}>Período</span>
                <span style={{ fontWeight: 600 }}>{label}</span>
              </div>
            </div>
          )}

          <Button variant="primary" size="lg" style={{ width: "100%", justifyContent: "center" }} disabled={!selected} onClick={goNext}>
            Entrar al tablero <Icon name="arrowRight" size={14} />
          </Button>
        </div>
      </div>
    </div>
  );
}
