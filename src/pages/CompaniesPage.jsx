import { useState, useEffect, useRef } from "react";
import { api } from "../lib/api.js";
import { useApp } from "../context/AppContext.jsx";
import { Badge } from "../components/ui/badge.jsx";
import { Button } from "../components/ui/button.jsx";
import { Input } from "../components/ui/input.jsx";
import Icon from "../icons.jsx";

const REGIMENES = [
  { value: "601", label: "601 – General de Ley Personas Morales" },
  { value: "603", label: "603 – Personas Morales con Fines no Lucrativos" },
  { value: "605", label: "605 – Sueldos y Salarios" },
  { value: "606", label: "606 – Arrendamiento" },
  { value: "607", label: "607 – Régimen de Enajenación o Adquisición de Bienes" },
  { value: "608", label: "608 – Demás Ingresos" },
  { value: "610", label: "610 – Residentes en el Extranjero" },
  { value: "611", label: "611 – Ingresos por Dividendos" },
  { value: "612", label: "612 – Personas Físicas con Actividades Empresariales y Profesionales" },
  { value: "614", label: "614 – Ingresos por Intereses" },
  { value: "615", label: "615 – Régimen de los ingresos por obtención de premios" },
  { value: "616", label: "616 – Sin Obligaciones Fiscales" },
  { value: "620", label: "620 – Sociedades Cooperativas de Producción" },
  { value: "621", label: "621 – Incorporación Fiscal" },
  { value: "622", label: "622 – Actividades Agrícolas, Ganaderas, Silvícolas y Pesqueras" },
  { value: "623", label: "623 – Opcional para Grupos de Sociedades" },
  { value: "624", label: "624 – Coordinados" },
  { value: "625", label: "625 – Régimen de las Actividades Empresariales con Ingresos a través de Plataformas Tecnológicas" },
  { value: "626", label: "626 – Régimen Simplificado de Confianza" },
];

const IMPUESTOS = [
  { key: "iva",     label: "IVA" },
  { key: "isr",     label: "ISR" },
  { key: "ieps",    label: "IEPS" },
  { key: "ret_iva", label: "Retención IVA" },
  { key: "ret_isr", label: "Retención ISR" },
  { key: "diot",    label: "DIOT" },
];

function initials(razon = "", rfc = "") {
  return razon.split(" ").filter(w => /^[A-ZÁÉÍÓÚÑ]/.test(w[0] || "")).slice(0, 2).map(w => w[0]).join("") || rfc.slice(0, 2);
}

function emptyForm() {
  return {
    rfc: "", razon_social: "", regimen_fiscal: "", cp_fiscal: "",
    fecha_inicio_periodo: "", fecha_cierre_periodo: "",
  };
}

export default function CompaniesPage() {
  const { companies, setCompanies } = useApp();

  const [selected, setSelected] = useState(null);
  const [addMode, setAddMode] = useState("manual");
  const [form, setForm] = useState(emptyForm());
  const [saving, setSaving] = useState(false);
  const [addError, setAddError] = useState("");
  const [addOk, setAddOk] = useState("");
  const [parsing, setParsing] = useState(false);
  const [parseError, setParseError] = useState("");
  const [parsedFileName, setParsedFileName] = useState("");
  const [impuestos, setImpuestos] = useState([]);
  const [impSaving, setImpSaving] = useState(false);
  const [impError, setImpError] = useState("");
  const [impOk, setImpOk] = useState("");
  const [fiel, setFiel] = useState(null);
  const [fielLoading, setFielLoading] = useState(false);
  const fileInputRef = useRef(null);

  useEffect(() => {
    if (!selected) {
      setFiel(null);
      setImpuestos([]);
      setImpError("");
      setImpOk("");
      return;
    }
    const id = selected.empresa_id || selected.id;
    setImpuestos(Array.isArray(selected.impuestos_declarar) ? selected.impuestos_declarar : []);
    setImpError("");
    setImpOk("");
    setFielLoading(true);
    setFiel(null);
    api.sat.fiel.estado(id)
      .then(res => setFiel(res))
      .catch(() => setFiel({ estado: "sin_fiel" }))
      .finally(() => setFielLoading(false));
  }, [selected]);

  function handleSelectCompany(c) {
    setSelected(c);
    setAddError("");
    setAddOk("");
  }

  function handleFormChange(field, value) {
    setForm(f => ({ ...f, [field]: value }));
    setAddError("");
    setAddOk("");
  }

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

  async function handleSaveEmpresa() {
    setAddError("");
    setAddOk("");
    if (!form.rfc.trim()) { setAddError("El RFC es requerido."); return; }
    if (!form.razon_social.trim()) { setAddError("La razón social es requerida."); return; }
    if (form.fecha_inicio_periodo && form.fecha_cierre_periodo &&
        form.fecha_cierre_periodo < form.fecha_inicio_periodo) {
      setAddError("La fecha de cierre no puede ser anterior a la de inicio.");
      return;
    }
    setSaving(true);
    try {
      const nueva = await api.empresas.add({
        rfc:                  form.rfc.toUpperCase().trim(),
        razon_social:         form.razon_social.trim(),
        regimen_fiscal:       form.regimen_fiscal,
        cp_fiscal:            form.cp_fiscal.trim(),
        fecha_inicio_periodo: form.fecha_inicio_periodo || null,
        fecha_cierre_periodo: form.fecha_cierre_periodo || null,
      });
      const lista = await api.empresas.list();
      setCompanies(lista);
      setForm(emptyForm());
      setParsedFileName("");
      setAddOk(`Empresa ${nueva.rfc || form.rfc} agregada correctamente.`);
    } catch (err) {
      setAddError(err.message || "No se pudo agregar la empresa.");
    } finally {
      setSaving(false);
    }
  }

  function toggleImpuesto(key) {
    setImpuestos(prev =>
      prev.includes(key) ? prev.filter(k => k !== key) : [...prev, key]
    );
    setImpError("");
    setImpOk("");
  }

  async function handleSaveImpuestos() {
    if (!selected) return;
    const id = selected.empresa_id || selected.id;
    setImpSaving(true);
    setImpError("");
    setImpOk("");
    try {
      await api.empresas.updateImpuestos(id, impuestos);
      setImpOk("Impuestos actualizados correctamente.");
      setCompanies(prev => prev.map(c => {
        const cid = c.empresa_id || c.id;
        return cid === id ? { ...c, impuestos_declarar: impuestos } : c;
      }));
    } catch (err) {
      setImpError(err.message || "No se pudo actualizar.");
    } finally {
      setImpSaving(false);
    }
  }

  function fielBadge() {
    if (fielLoading) return <Badge variant="default">Verificando FIEL…</Badge>;
    if (!fiel) return null;
    const e = fiel.estado || fiel.status || "";
    if (e === "activa" || e === "vigente" || e === "active") return <Badge variant="success">FIEL activa</Badge>;
    if (e === "vencida" || e === "expired") return <Badge variant="danger">FIEL vencida</Badge>;
    return <Badge variant="default">Sin FIEL</Badge>;
  }

  const labelStyle = {
    display: "block",
    fontSize: 11,
    fontFamily: "var(--font-mono)",
    textTransform: "uppercase",
    letterSpacing: "0.06em",
    color: "var(--muted-foreground)",
    marginBottom: 5,
  };

  const fieldGroup = { display: "flex", flexDirection: "column", gap: 4 };

  const sectionCard = {
    border: "1px solid var(--border-shadcn)",
    borderRadius: 10,
    padding: "18px 20px",
    display: "flex",
    flexDirection: "column",
    gap: 16,
  };

  const sectionTitle = {
    fontFamily: "Georgia, serif",
    fontWeight: 400,
    fontSize: 17,
    letterSpacing: "-0.015em",
    margin: 0,
  };

  const alertBase = {
    display: "flex",
    alignItems: "center",
    gap: 8,
    padding: "10px 14px",
    borderRadius: 7,
    fontSize: 13,
  };

  return (
    <div style={{ padding: "clamp(20px,2.5vw,36px)", maxWidth: 1060 }}>

      <div style={{ marginBottom: 24 }}>
        <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--muted-foreground)", marginBottom: 4 }}>
          Módulo 1
        </div>
        <h1 style={{ fontFamily: "Georgia, serif", fontWeight: 400, fontSize: "clamp(20px,2.8vw,30px)", letterSpacing: "-0.02em", lineHeight: 1.1, marginBottom: 6 }}>
          Empresas
        </h1>
        <p style={{ color: "var(--muted-foreground)", fontSize: 13 }}>
          {companies.length} contribuyente{companies.length !== 1 ? "s" : ""} registrado{companies.length !== 1 ? "s" : ""} en tu cuenta.
        </p>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "minmax(220px,320px) 1fr", gap: 20, alignItems: "start" }}>

        {/* LEFT: company list */}
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {companies.length === 0 && (
            <div style={{ fontSize: 13, color: "var(--muted-foreground)", padding: "16px 0" }}>
              Sin empresas. Agrega una a la derecha.
            </div>
          )}
          {companies.map(c => {
            const id    = c.empresa_id || c.id;
            const razon = c.razon_social || c.razon || "";
            const color = c.color || "var(--primary)";
            const ini   = initials(razon, c.rfc);
            const isActive = (selected?.empresa_id || selected?.id) === id;

            return (
              <button
                key={id}
                onClick={() => handleSelectCompany(c)}
                style={{
                  display: "flex", alignItems: "center", gap: 12,
                  padding: "12px 14px", borderRadius: 8,
                  border: `1.5px solid ${isActive ? "var(--primary)" : "var(--border-shadcn)"}`,
                  background: isActive ? "color-mix(in oklch, var(--primary), white 94%)" : "var(--card)",
                  cursor: "pointer", textAlign: "left", width: "100%",
                  transition: "border-color 0.15s",
                }}
              >
                <span style={{
                  background: `color-mix(in oklch, ${color}, white 70%)`,
                  color, width: 34, height: 34, fontSize: 12, fontWeight: 600,
                  borderRadius: 8, flexShrink: 0,
                  display: "flex", alignItems: "center", justifyContent: "center",
                }}>
                  {ini}
                </span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 600, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {razon}
                  </div>
                  <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--muted-foreground)", marginTop: 2 }}>
                    {c.rfc}
                  </div>
                  {c.regimen_fiscal && (
                    <div style={{ fontSize: 10, color: "var(--muted-foreground)", marginTop: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {c.regimen_fiscal}
                    </div>
                  )}
                </div>
              </button>
            );
          })}
        </div>

        {/* RIGHT: panels */}
        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>

          {/* Section A: Agregar empresa */}
          <div style={sectionCard}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <h2 style={sectionTitle}>Agregar empresa</h2>
              <div style={{ display: "flex", gap: 6 }}>
                <Button
                  variant={addMode === "manual" ? "primary" : "default"}
                  size="sm"
                  onClick={() => { setAddMode("manual"); setAddError(""); setAddOk(""); }}
                >
                  Manual
                </Button>
                <Button
                  variant={addMode === "constancia" ? "primary" : "default"}
                  size="sm"
                  onClick={() => { setAddMode("constancia"); setAddError(""); setAddOk(""); }}
                >
                  <Icon name="file" size={12} />
                  Constancia SAT
                </Button>
              </div>
            </div>

            {addMode === "constancia" && (
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                <div style={{ fontSize: 12, color: "var(--muted-foreground)" }}>
                  Sube el PDF de tu constancia de situación fiscal. Los datos se auto-rellenarán en el formulario.
                </div>
                <div
                  style={{
                    border: "1.5px dashed var(--border-shadcn)",
                    borderRadius: 8, padding: "20px 16px",
                    display: "flex", flexDirection: "column", alignItems: "center", gap: 10,
                    cursor: "pointer", background: "var(--muted)",
                  }}
                  onClick={() => fileInputRef.current?.click()}
                >
                  <Icon name="upload" size={22} style={{ color: "var(--muted-foreground)" }} />
                  <div style={{ fontSize: 12, color: "var(--muted-foreground)", textAlign: "center" }}>
                    {parsing ? "Leyendo constancia…" : parsedFileName ? parsedFileName : "Haz clic para seleccionar un PDF"}
                  </div>
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".pdf"
                    style={{ display: "none" }}
                    onChange={handleConstanciaFile}
                  />
                </div>
                {parseError && (
                  <div style={{ ...alertBase, background: "var(--danger-bg)", border: "1px solid var(--danger-border)", color: "var(--destructive)" }}>
                    <Icon name="alert" size={14} style={{ flexShrink: 0 }} />
                    {parseError}
                  </div>
                )}
              </div>
            )}

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
              <div style={fieldGroup}>
                <label style={labelStyle}>RFC</label>
                <Input
                  value={form.rfc}
                  placeholder="XAXX010101000"
                  onChange={e => handleFormChange("rfc", e.target.value.toUpperCase())}
                  maxLength={13}
                />
              </div>
              <div style={fieldGroup}>
                <label style={labelStyle}>CP Fiscal</label>
                <Input
                  value={form.cp_fiscal}
                  placeholder="06600"
                  onChange={e => handleFormChange("cp_fiscal", e.target.value)}
                  maxLength={5}
                />
              </div>
              <div style={{ ...fieldGroup, gridColumn: "1 / -1" }}>
                <label style={labelStyle}>Razón Social</label>
                <Input
                  value={form.razon_social}
                  placeholder="EMPRESA EJEMPLO S.A. DE C.V."
                  onChange={e => handleFormChange("razon_social", e.target.value)}
                />
              </div>
              <div style={{ ...fieldGroup, gridColumn: "1 / -1" }}>
                <label style={labelStyle}>Régimen Fiscal</label>
                <select
                  value={form.regimen_fiscal}
                  onChange={e => handleFormChange("regimen_fiscal", e.target.value)}
                  style={{
                    height: 32, width: "100%", borderRadius: 4,
                    border: "1px solid var(--input)", background: "var(--card)",
                    padding: "0 10px", fontSize: 12, color: "var(--foreground)",
                    fontFamily: "inherit", outline: "none",
                  }}
                >
                  <option value="">Selecciona régimen…</option>
                  {REGIMENES.map(r => (
                    <option key={r.value} value={r.value}>{r.label}</option>
                  ))}
                </select>
              </div>
              <div style={{ ...labelStyle, gridColumn: "1 / -1", marginBottom: 0, marginTop: 2 }}>
                Periodo de trabajo
              </div>
              <div style={fieldGroup}>
                <label style={labelStyle}>Fecha de inicio</label>
                <Input
                  type="date"
                  value={form.fecha_inicio_periodo}
                  onChange={e => handleFormChange("fecha_inicio_periodo", e.target.value)}
                />
              </div>
              <div style={fieldGroup}>
                <label style={labelStyle}>Fecha de cierre</label>
                <Input
                  type="date"
                  value={form.fecha_cierre_periodo}
                  min={form.fecha_inicio_periodo || undefined}
                  onChange={e => handleFormChange("fecha_cierre_periodo", e.target.value)}
                />
              </div>
            </div>

            {addError && (
              <div style={{ ...alertBase, background: "var(--danger-bg)", border: "1px solid var(--danger-border)", color: "var(--destructive)" }}>
                <Icon name="alert" size={14} style={{ flexShrink: 0 }} />
                {addError}
              </div>
            )}
            {addOk && (
              <div style={{ ...alertBase, background: "#F0FDF4", border: "1px solid #BBF7D0", color: "#15803D" }}>
                <Icon name="check" size={14} style={{ flexShrink: 0 }} />
                {addOk}
              </div>
            )}

            <div style={{ display: "flex", justifyContent: "flex-end" }}>
              <Button variant="primary" size="sm" onClick={handleSaveEmpresa} disabled={saving}>
                {saving ? "Guardando…" : "Guardar empresa"}
              </Button>
            </div>
          </div>

          {/* Section B: Configuración — visible only when a company is selected */}
          {selected && (
            <div style={sectionCard}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10 }}>
                <h2 style={sectionTitle}>Configuración</h2>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{ fontSize: 12, color: "var(--muted-foreground)" }}>
                    {selected.razon_social || selected.razon || selected.rfc}
                  </span>
                  {fielBadge()}
                </div>
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                <div style={{ fontSize: 11, fontFamily: "var(--font-mono)", textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--muted-foreground)" }}>
                  Impuestos a declarar
                </div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 10 }}>
                  {IMPUESTOS.map(({ key, label }) => {
                    const checked = impuestos.includes(key);
                    return (
                      <label
                        key={key}
                        style={{
                          display: "flex", alignItems: "center", gap: 7,
                          padding: "7px 12px", borderRadius: 7, cursor: "pointer",
                          border: `1.5px solid ${checked ? "var(--primary)" : "var(--border-shadcn)"}`,
                          background: checked ? "color-mix(in oklch, var(--primary), white 94%)" : "var(--card)",
                          fontSize: 13, fontWeight: checked ? 600 : 400,
                          transition: "border-color 0.15s, background 0.15s",
                          userSelect: "none",
                        }}
                      >
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={() => toggleImpuesto(key)}
                          style={{ accentColor: "var(--primary)", width: 14, height: 14 }}
                        />
                        {label}
                      </label>
                    );
                  })}
                </div>
              </div>

              {impError && (
                <div style={{ ...alertBase, background: "var(--danger-bg)", border: "1px solid var(--danger-border)", color: "var(--destructive)" }}>
                  <Icon name="alert" size={14} style={{ flexShrink: 0 }} />
                  {impError}
                </div>
              )}
              {impOk && (
                <div style={{ ...alertBase, background: "#F0FDF4", border: "1px solid #BBF7D0", color: "#15803D" }}>
                  <Icon name="check" size={14} style={{ flexShrink: 0 }} />
                  {impOk}
                </div>
              )}

              <div style={{ display: "flex", justifyContent: "flex-end" }}>
                <Button variant="primary" size="sm" onClick={handleSaveImpuestos} disabled={impSaving}>
                  {impSaving ? "Guardando…" : "Guardar impuestos"}
                </Button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
