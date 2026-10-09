# M2 — Papel de trabajo y cierre contable

**Fecha:** 2026-10-09  
**Carril:** C (Cálculos fiscales)  
**Depende de:** F4 (Inicio), F5 (IVA), F6 (DIOT), F7 (ISR), Conciliación y Scoring (existentes)

## Entrega

**M2.1: Papel de trabajo mensual (Excel)** — Descarga de un XLSX con resumen ejecutivo (ingresos, gastos, IVA, ISR, DIOT, conciliación) y hojas de detalle por módulo, cifras de control e indicadores de riesgo.

**M2.2: Cierre de período** — Bloqueo de cambios después del cierre, lista de validaciones y riesgos pendientes, marca en auditoría de quién cerró y cuándo.

**M2.3: Reapertura** — Solo admin puede reabrir un período cerrado; deja marca de auditoría.

## Alcance

### Excel mensual (M2.1)

**Usuarios:** admin, contador. **Endpoint:** `GET /api/v1/empresas/{id}/papel-trabajo/{periodo}`; devuelve XLSX descargable.

**Estructura del XLSX:**

1. **Portada** — Logo FiscalCore, empresa (RFC, razón social, régimen), período (mes/año), fecha de descarga, usuario que descargó.

2. **Resumen ejecutivo (Cierre)** — Una sola hoja:
   - Ingresos netos del mes (F4)
   - Ingresos netos acumulados del ejercicio (F4)
   - Gastos y compras netos del mes (F4)
   - Gastos y compras netos acumulados (F4)
   - IVA trasladado cobrado (F5)
   - IVA acreditable pagado (F5)
   - IVA a cargo o a favor (F5)
   - Retenciones de IVA (F5)
   - Ingresos acumulables (ISR, F7)
   - Deducciones autorizadas (F7)
   - ISR base calculado (F7)
   - DIOT: total por pagar (F6)
   - Conciliación: saldo en bancos vs. registrado
   - Riesgos abiertos: conteo por tipo (score, validaciones, CFDI cancelados después de la fecha de cierre)

   Todas las celdas son formato `General` con número fijo (no fórmulas dinámicas: valores de la fecha de descarga, no de hoy).

3. **IVA (F5)** — Copia de la pantalla del módulo:
   - Bases por tasa (16 %, 8 %, 0 %, exento)
   - Retenciones
   - Cifra de control (total del CFDI vs. suma de conceptos)
   - Listado de CFDI: UUID, fecha, contraparte, base, IVA, retención, marca si no se considera, motivo del ajuste.

4. **ISR (F7)** — Similar a IVA:
   - Ingresos cobrados (contado + REP)
   - Deducciones (nómina, compras, pagos, notas, inversiones por bloque)
   - ISR base calculado
   - Porcentaje de nómina exenta configurado
   - Listado de CFDI/nómina: UUID, fecha, tipo (ingreso/deducción), monto, bloque, marca.

5. **DIOT (F6)** — Tabla de terceros:
   - RFC, nombre, tipo de tercero, tipo de operación
   - Base por tasa (16 %, 8 %, 0 %)
   - IVA acreditable y no acreditable
   - Retenciones
   - Cada fila = un proveedor/acreedor; se resumen los meses.

6. **Conciliación bancaria** — Tabla con:
   - Fecha de movimiento
   - Descripción
   - Monto en el banco
   - CFDI relacionados (si están conciliados)
   - Cuadre: suma del banco vs. suma de CFDI conciliados.

7. **Riesgos y validaciones** — Lista sin paginación:
   - Tipo (score bajo, CFDI cancelado, documento sin bancarizar, uso de CFDI inválido, etc.)
   - CFDI o RFC afectado
   - Descripción de la regla
   - Bloquea cierre (Sí/No)
   - Acción recomendada.

**Formato:**
- Colores por módulo (gris para IVA, azul para ISR, verde para DIOT, naranja para riesgos)
- Encabezados con negrita y fondo
- Números con formato de moneda (2 decimales)
- Fechas como DD/MM/AAAA
- Una fila vacía entre bloques para legibilidad

**Plantilla:**
- Se reutiliza `openpyxl` (ya en requirements)
- Estilos base en un módulo `backend/papel_trabajo.py` (estilos, paleta de colores)
- Las hojas se montan desde módulos existentes (`iva.py`, `isr_flujo.py`, `diot.py`, etc.)

### Cierre de período (M2.2, M2.3)

**Tabla nueva:** `periodos_cerrados` (empresa_id, periodo, cerrado_por [user_id], fecha_cierre, validaciones_pasadas [JSON], reabierto_por [user_id], fecha_reapertura).

**Validaciones que bloquean cierre:**

- [ ] Al menos 1 CFDI de ingreso del mes
- [ ] Ingresos ≥ $1.00 (no período vacío)
- [ ] Sin CFDI cancelados después de la fecha de inicio del período (indica error de carga o fraude)
- [ ] Bancarización: ≥ 90 % de ingresos con movimiento bancario registrado (flag, no bloquea; es recomendación)
- [ ] Sin scoring bajo: ≤ 3 CFDI con score ≤ 30 (flag, no bloquea)
- [ ] Nómina: si hay nóminas, sin empleados sin cumplimiento de retenciones (flag, no bloquea)

**Endpoints:**

- `POST /api/v1/empresas/{id}/periodos/{periodo}/cerrar` — Valida todas las condiciones; si no bloquean, marca periodo como cerrado. Audita con usuario, fecha, validaciones que pasaron.
  - Respuesta 403 si hay validación bloqueante no pasada; lista cuál.
  - Respuesta 200 si logra cerrar.

- `GET /api/v1/empresas/{id}/periodos/{periodo}/estado-cierre` — Devuelve {cerrado: bool, cerrado_por: usuario, fecha_cierre: timestamp, validaciones: [{nombre, pasó: bool, bloquea: bool}], reabierto: bool}.

- `DELETE /api/v1/empresas/{id}/periodos/{periodo}/cierre` (solo admin) — Reabre; audita.

- `GET /api/v1/empresas/{id}/periodos/{periodo}/validaciones` — Lista todas las validaciones sin intentar cerrar (para la UI).

**En la UI:**

1. Pantalla nueva: `/empresas/{id}/cierre-periodo` — Selector de período (default: mes actual). Botón "Descargar papel de trabajo"; botón "Ver validaciones y cerrar" que abre un diálogo modal con:
   - Cada validación: ✓ o ✗, nombre, instrucción para corregirla.
   - Botón "Cerrar período" (deshabilitado si hay bloqueante sin pasar).
   - Al cerrar: mensaje "Período cerrado. Ya no se pueden editar CFDI de este mes."

2. En la barra del período global (ya existe selector), después de elegir un período cerrado:
   - Badge "CERRADO" en rojo junto al mes.
   - Todas las acciones de edición de CFDI (excluir, reasignar) de ese mes devuelven 422 "Período cerrado; reabre para cambios" (solo muestra para admin un botón "Reabrir").

**Auditoría:**

Cada cierre y reapertura se registra en `auditoria` con origen "cierre", tipo "periodo_cerrado" o "periodo_reabierto", y los detalles en JSON (validaciones pasadas, usuario, etc.).

## Decisiones

| # | Decisión | Valor | Fundamento |
|---|---|---|---|
| D-M2-1 | Período a cerrar | Mes calendario (desde el 1 del mes hasta 23:59:59 del último día) | Simplifica conciliación y coincide con obligaciones fiscales mensuales |
| D-M2-2 | Bloqueo tras cierre | Duro (error 422): no permite cambios; solo admin reabre | Evita cambios accidentales tras cierre; auditoría clara |
| D-M2-3 | Validaciones bloqueantes | Ingresos > $0, sin cancelados posteriores, ≥ 1 CFDI | Detiene cierres vacíos o sospechosos; el resto son recomendaciones |
| D-M2-4 | Descarga del papel | XLSX, descargable desde UI; PDF es futuro (bibliotecas generan PDFs mal a veces) | XLSX es portable, editable, fácil de revisar; el usuario puede imprimir a PDF |

## Reglas fiscales

- **Cifras de control:** Ingresos y gastos del papel provienen de F4 (flujo de efectivo), no del encabezado del CFDI. Coinciden con la sumatoria de CFDI considerados (sin ajustes manuales).
- **Período:** De 00:00:00 del primer día del mes a 23:59:59 del último día. Un CFDI de enero, aunque se pague el 5 de febrero, cuenta en enero (emisión).
- **Nómina:** En el ISR, las fechas de pago definen el mes de deducción, no la emisión. Una nómina emitida en enero pero pagada en febrero resta de febrero.
- **Cierre irreversible para la contabilidad:** Una vez cerrado, el período no se puede recalcular sin intervención de admin. Esto respeta el principio de que los registros contables son de historial.

## Tamaño estimado

- **Backend:** módulo `paper_trabajo.py` (generador del XLSX) + endpoints + migración + tests: ~500 líneas.
- **Frontend:** pantalla `CierrePeriodo.tsx` + componentes de validaciones: ~800 líneas.
- **Migraciones:** 1 (periodos_cerrados, índices).
- **Tiempo:** 3–4 días de desarrollo + testing.

## Dependencias de otros carriles

Ninguna. M2 solo lee de F4–F7 y del scoring/conciliación existentes.

## Verificación

1. `python -m pytest backend/tests/test_papel_trabajo.py` — Pruebas del generador XLSX.
2. `npm test frontend/components/cierre-periodo/` — Pruebas de la UI.
3. Descargar un papel de trabajo real y verificar:
   - Cifras coinciden con pantalla
   - Formato legible (sin errores de estilos)
   - Todas las hojas están presentes
4. Intentar cerrar un período sin validar; debe rechazar con mensaje claro.
5. Cerrar un período; intentar editar un CFDI; debe devolver error y mostrar botón de reapertura (para admin).
