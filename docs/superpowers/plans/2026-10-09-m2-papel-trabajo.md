# M2 — Plan de implementación

**Entrega:** Papel de trabajo mensual (Excel) + Cierre de período (UI + endpoints)

**Duración estimada:** 3–4 días

---

## Fase 1: Estructura y migración (Backend)

### 1.1. Migración: `periodos_cerrados`

**Archivo:** `database/migrations/070_periodos_cerrados.sql`

```sql
CREATE TABLE periodos_cerrados (
  id SERIAL PRIMARY KEY,
  empresa_id UUID NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
  periodo CHAR(7) NOT NULL,  -- AAAA-MM
  cerrado_por UUID NOT NULL REFERENCES usuarios(id),
  fecha_cierre TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
  validaciones_pasadas JSONB,  -- {"ingresos_presentes": true, "sin_cancelados": true, ...}
  reabierto_por UUID,
  fecha_reapertura TIMESTAMP WITH TIME ZONE,
  UNIQUE(empresa_id, periodo)
);

CREATE INDEX idx_periodos_cerrados_empresa ON periodos_cerrados(empresa_id);
CREATE INDEX idx_periodos_cerrados_periodo ON periodos_cerrados(periodo);
```

**Prueba idempotencia:** `SELECT to_regclass('public.periodos_cerrados')` antes de la creación.

---

## Fase 2: Backend — Módulos

### 2.1. Módulo: `backend/papel_trabajo.py`

**Responsabilidad:** Generar el XLSX con todas las hojas.

**Funciones principales:**

```python
def generar_papel_trabajo(empresa_id: UUID, periodo: str) -> BytesIO:
    """
    Genera XLSX con resumen, IVA, ISR, DIOT, conciliación, riesgos.
    Retorna el archivo listo para descargar.
    """
    # 1. Carga datos de F4, F5, F7, F6, scoring, conciliación
    # 2. Crea un Workbook con openpyxl
    # 3. Monta cada hoja (portada, resumen, iva, isr, diot, conc, riesgos)
    # 4. Retorna BytesIO

def validaciones_cierre(empresa_id: UUID, periodo: str) -> dict:
    """
    Devuelve {
      'validaciones': [
        {'nombre': 'Ingresos presentes', 'pasó': True, 'bloquea': True, 'mensaje': '...'},
        ...
      ],
      'puede_cerrar': True/False
    }
    """
```

**Estilos (módulo `backend/estilos_excel.py`):**

```python
# Colores por módulo
COLORES = {
    'iva': 'D9E8F5',      # Azul claro
    'isr': 'E8F5E9',      # Verde claro
    'diot': 'FFF3E0',     # Naranja claro
    'riesgos': 'FFEBEE',  # Rojo claro
    'encabezado': '1F497D',  # Azul oscuro (texto)
}

def estiloEncabezado():
    return Font(bold=True, color=COLORES['encabezado'])
```

### 2.2. Módulo: `backend/cierre.py`

**Responsabilidad:** Lógica de validación y cierre de períodos.

```python
def validaciones_bloqueantes(empresa_id: UUID, periodo: str) -> list[dict]:
    """
    Ejecuta todas las validaciones. Retorna lista con estado.
    """
    cur = get_db_cursor()
    empresa = cur.query_one("SELECT * FROM empresas WHERE id = %s", (empresa_id,))
    
    validaciones = []
    
    # V1: Ingresos > 0
    ingresos = cur.query_one(
        "SELECT SUM(monto) FROM iva WHERE empresa_id = %s AND periodo = %s AND lado = 'propio' AND tipo = 'trasladado'",
        (empresa_id, periodo)
    )
    validaciones.append({
        'nombre': 'Ingresos presentes',
        'pasó': ingresos['sum'] > 0,
        'bloquea': True,
        'mensaje': 'El período debe tener al menos 1 CFDI de ingreso'
    })
    
    # V2: Sin CFDI cancelados posteriores
    # ...
    
    return validaciones

def puede_cerrar(empresa_id: UUID, periodo: str) -> bool:
    """True si todas las validaciones bloqueantes pasaron."""
    return all(v['bloquea'] == False or v['pasó'] for v in validaciones_bloqueantes(...))

def cerrar_periodo(empresa_id: UUID, periodo: str, usuario_id: UUID) -> None:
    """Inserta registro en periodos_cerrados. Lanza excepción si no puede cerrar."""
    if not puede_cerrar(empresa_id, periodo):
        raise PeriodoNoPuedeCerrar("Validaciones bloqueantes sin pasar")
    
    cur = get_db_cursor()
    cur.execute(
        "INSERT INTO periodos_cerrados (empresa_id, periodo, cerrado_por) VALUES (%s, %s, %s)",
        (empresa_id, periodo, usuario_id)
    )
```

### 2.3. Endpoints: `backend/routers/cierre.py` (nuevo)

```python
@router.get("/empresas/{id}/periodos/{periodo}/papel-trabajo")
def descargar_papel_trabajo(id: UUID, periodo: str):
    """Descarga el XLSX del mes."""
    xlsx = generar_papel_trabajo(id, periodo)
    return FileResponse(
        BytesIO(xlsx),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=f"papel-trabajo-{id}-{periodo}.xlsx"
    )

@router.get("/empresas/{id}/periodos/{periodo}/validaciones")
def listar_validaciones(id: UUID, periodo: str):
    """Lista validaciones sin intentar cerrar."""
    return validaciones_cierre(id, periodo)

@router.post("/empresas/{id}/periodos/{periodo}/cerrar")
def cerrar_periodo(id: UUID, periodo: str, current_user: dict):
    """Intenta cerrar; 403 si hay bloqueante sin pasar; 200 si logra."""
    try:
        cerrar_periodo(id, periodo, current_user['user_id'])
        return {"mensaje": "Período cerrado"}
    except PeriodoNoPuedeCerrar as e:
        raise HTTPException(403, detail=str(e))

@router.delete("/empresas/{id}/periodos/{periodo}/cierre")
def reabrir_periodo(id: UUID, periodo: str, current_user: dict):
    """Solo admin. Reabre."""
    if current_user.get('rol') != 'admin':
        raise HTTPException(403, "Solo admin puede reabrir")
    cur = get_db_cursor()
    cur.execute(
        "UPDATE periodos_cerrados SET reabierto_por = %s, fecha_reapertura = now() WHERE empresa_id = %s AND periodo = %s",
        (current_user['user_id'], id, periodo)
    )
    return {"mensaje": "Período reabierto"}

@router.get("/empresas/{id}/periodos/{periodo}/estado-cierre")
def estado_cierre(id: UUID, periodo: str):
    """Estado: cerrado sí/no, por quién, cuándo."""
    cur = get_db_cursor()
    row = cur.query_one(
        "SELECT * FROM periodos_cerrados WHERE empresa_id = %s AND periodo = %s",
        (id, periodo)
    )
    if not row:
        return {"cerrado": False}
    return {
        "cerrado": True,
        "cerrado_por": row['cerrado_por'],
        "fecha_cierre": row['fecha_cierre'].isoformat(),
        "reabierto": row['reabierto_por'] is not None
    }
```

### 2.4. Validación de cambios post-cierre

**En routers/iva.py, routers/isr_flujo.py, etc.:**

Antes de cualquier `PUT` o `DELETE` de ajustes, validar:

```python
def periodo_esta_cerrado(empresa_id: UUID, periodo: str) -> bool:
    cur = get_db_cursor()
    return bool(cur.query_one(
        "SELECT id FROM periodos_cerrados WHERE empresa_id = %s AND periodo = %s AND reabierto_por IS NULL",
        (empresa_id, periodo)
    ))

# En cada endpoint PUT/DELETE:
if periodo_esta_cerrado(empresa_id, periodo):
    raise HTTPException(422, detail="Período cerrado; reabre para cambios")
```

---

## Fase 3: Frontend

### 3.1. Pantalla: `frontend/app/(app)/empresas/[empresaId]/cierre-periodo/page.tsx`

```typescript
"use client";

export default function CierrePeriodoPage() {
  const { empresaId } = useParams<{ empresaId: string }>();
  const [periodo, setPeriodo] = usePeriodoGlobal(empresaId);
  
  return (
    <PageHeader title="Cierre de período" />
    <CierrePeriodo empresaId={empresaId} periodo={periodo} />
  );
}
```

### 3.2. Componente: `frontend/components/cierre-periodo/CierrePeriodo.tsx`

```typescript
export function CierrePeriodo({ empresaId, periodo }: Props) {
  const { data: validaciones } = useQuery([...], () => listarValidaciones(...));
  const { data: estado } = useQuery([...], () => estadoCierre(...));
  const { mutate: descargar } = useMutation(() => descargarPapelTrabajo(...));
  const { mutate: cerrar } = useMutation(() => cerrarPeriodo(...));
  
  return (
    <div>
      <Button onClick={() => descargar()}>Descargar Papel de Trabajo</Button>
      
      {!estado?.cerrado ? (
        <ModalValidacionesYCierre
          validaciones={validaciones}
          onCerrar={() => cerrar()}
        />
      ) : (
        <Alert>Período cerrado por {estado.cerrado_por} el {estado.fecha_cierre}</Alert>
      )}
    </div>
  );
}
```

### 3.3. Componente: `frontend/components/cierre-periodo/ModalValidacionesYCierre.tsx`

Lista las validaciones con ✓/✗, nombres y mensajes. Botón "Cerrar período" deshabilitado si hay bloqueante sin pasar.

### 3.4. Hook: `frontend/hooks/useCierre.ts`

```typescript
export function useCierre(empresaId: string, periodo: string) {
  const { data: validaciones } = useQuery([...], apiClient.get(`/...`));
  const { data: estado } = useQuery([...], apiClient.get(`/...`));
  const cerrar = useMutation(() => apiClient.post(`/...`));
  const reabrir = useMutation(() => apiClient.delete(`/...`));
  const descargar = async () => {
    const resp = await apiClient.get(`/...`, { responseType: 'blob' });
    guardarArchivo(resp.data, `papel-trabajo-${periodo}.xlsx`);
  };
  return { validaciones, estado, cerrar, reabrir, descargar };
}
```

---

## Fase 4: Tests

### 4.1. Backend: `backend/tests/test_papel_trabajo.py`

```python
def test_genera_xlsx_con_todas_las_hojas():
    """El XLSX tiene portada, resumen, iva, isr, diot, conciliación, riesgos."""
    xlsx = generar_papel_trabajo(empresa_id, "2026-10")
    wb = openpyxl.load_workbook(BytesIO(xlsx))
    assert "Resumen" in wb.sheetnames
    assert "IVA" in wb.sheetnames
    assert "ISR" in wb.sheetnames
    assert "DIOT" in wb.sheetnames

def test_validacion_ingresos_cero_bloquea():
    """Sin ingresos, puede_cerrar() = False."""
    result = puede_cerrar(empresa_sin_ingresos, "2026-10")
    assert result == False

def test_cerrar_periodo_exitoso():
    """Cierre exitoso inserta registro en periodos_cerrados."""
    cerrar_periodo(empresa_con_ingresos, "2026-10", usuario_id)
    assert periodos_cerrados.count(...) == 1

def test_cambio_post_cierre_devuelve_422():
    """Intentar ajustar un CFDI de período cerrado → 422."""
    cerrar_periodo(...)
    result = client.put(f"/iva-flujo/ajustes", {uuid: "...", periodo: "2026-10"})
    assert result.status_code == 422
```

### 4.2. Frontend: `frontend/components/cierre-periodo/CierrePeriodo.test.tsx`

```typescript
describe("CierrePeriodo", () => {
  it("muestra botón para descargar papel de trabajo", () => {
    render(<CierrePeriodo ... />);
    expect(screen.getByText("Descargar Papel de Trabajo")).toBeInTheDocument();
  });

  it("desactiva botón de cierre si hay validación bloqueante sin pasar", () => {
    render(<CierrePeriodo validaciones={[{ bloquea: true, pasó: false }]} />);
    expect(screen.getByRole("button", { name: /cerrar/i })).toBeDisabled();
  });
});
```

---

## Checklist

- [ ] Migración 070 escrita e idempotente
- [ ] Módulo `papel_trabajo.py` con `generar_papel_trabajo()` y `validaciones_cierre()`
- [ ] Módulo `cierre.py` con lógica de cierre
- [ ] Router `cierre.py` con 5 endpoints
- [ ] Validación de período cerrado en todos los ajustes (IVA, ISR, DIOT)
- [ ] Pantalla CierrePeriodo + Modal + Hook
- [ ] Tests backend (4+ casos)
- [ ] Tests frontend (2+ casos)
- [ ] `python -m pytest` en verde
- [ ] `npm test` en verde
- [ ] PR creado; merge a `main`

---

## Notas

- El Excel usa `openpyxl` (ya en `requirements.txt`)
- Auditoría de cierre va en tabla `auditoria` con tipo `periodo_cerrado`
- Reapertura: solo admin, deja marca con `reabierto_por` y `fecha_reapertura`
- Números en Excel: formato `.2f` (moneda), no fórmulas (son "fotos" de la fecha de descarga)
