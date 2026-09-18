# Módulo 5 — Pagos Provisionales de ISR · Spec ejecutable (Día 6)

> Estado: **DISEÑO** — blueprint para implementar en los Días 7-10 del plan.
> Objetivo del módulo: calcular el **pago provisional mensual de ISR** de una **persona moral,
> régimen general** (Art. 14 LISR), en base **DEVENGADO** (ingresos acumulables por `fecha_emision`),
> con acumulación del ejercicio mes a mes.

> ⚠️ **Diferencia crítica con el IVA (no reutilizar su lógica):**
> El ISR se causa por lo **devengado** (se emitió la factura), NO por flujo de efectivo. **No** se usan
> `pagos_cfdi` / REP / `fecha_pago`: los ingresos entran por `cfdi.fecha_emision`. El IVA sí es flujo de
> efectivo; el ISR no. Son motores distintos.

---

## 1. Reglas fiscales (qué se calcula) — Art. 14 LISR

El pago provisional es **acumulado del ejercicio**: cada mes se calcula el ISR del periodo
enero→mes y se le restan los pagos provisionales ya hechos en meses anteriores.

### 1.1 Coeficiente de utilidad (CU) — Art. 14, fracción I
Se determina **una sola vez al año**, con datos del **ejercicio inmediato anterior**:

```
CU = utilidad fiscal del ejercicio anterior / ingresos nominales del ejercicio anterior
```

- Se redondea a **cuatro decimales** (`NUMERIC(6,4)`).
- Si en el ejercicio anterior hubo pérdida (utilidad fiscal ≤ 0), se usa el CU del **último ejercicio
  con coeficiente**, hasta 5 años atrás (regla que en v1 se resuelve capturando el CU a mano).
- **Es un insumo externo**: no se deriva de los CFDIs del periodo. Se persiste en
  `config_isr_empresa` (migración 024).

### 1.2 Ingresos nominales acumulados del ejercicio
Suma de los ingresos acumulables desde enero hasta el mes que se declara:

```
ingresos_nominales_acum(mes) =
    Σ (CFDI tipo I emitidos, vigentes, con fecha_emision en [ene-01 .. fin del mes])
  − Σ (notas de crédito tipo E emitidas, vigentes, en el mismo rango)
```

- **Devengado**: manda `fecha_emision`, NO el cobro. Un PPD sin REP igual acumula ISR.
- Excluye: `estado != 'vigente'`, `es_anticipo_sat = TRUE` (el ingreso se reconoce en la factura final,
  no en el anticipo, para no duplicar), y CFDIs recibidos (no son ingreso propio).
- **Alcance v1:** "ingresos nominales" ≈ ingresos acumulables **sin** el ajuste anual por inflación
  (Art. 14 excluye ese ajuste de los nominales) y **sin** ingresos acumulables que no tengan CFDI
  (intereses devengados a favor, etc.). Estas partidas quedan como fast-follow documentado.

### 1.3 Utilidad fiscal estimada y base del pago
```
utilidad_estimada  = ingresos_nominales_acum × CU
base_gravable      = utilidad_estimada
                     − PTU pagada en el ejercicio          (Art. 14, disminución)
                     − pérdidas fiscales pendientes de aplicar
base_gravable      = max(base_gravable, 0)                 # nunca negativa
```

- `PTU pagada` y `pérdidas_pendientes` son insumos anuales (tabla `config_isr_empresa`).
- En rigor la PTU se disminuye por partes iguales de mayo a diciembre; **v1 (MVP)** aplica el saldo
  capturado tal cual (simplificación documentada; refinamiento por meses = fast-follow).

### 1.4 ISR del periodo y pago del mes
```
isr_acumulado   = base_gravable × tasa_isr                 # tasa_isr = 0.30 (Art. 9 LISR)
pago_del_mes    = isr_acumulado
                  − pagos provisionales anteriores del ejercicio
                  − retenciones de ISR del periodo (cfdi.isr_retenido, p. ej. intereses bancarios)
pago_del_mes    = max(pago_del_mes, 0)                      # si sale negativo, no hay pago (se arrastra)
```

- **Pagos provisionales anteriores**: la suma de los `pago_del_mes` de enero..mes-1 del mismo ejercicio.
  Decisión de diseño (§3.4): se **computan iterativamente** mes a mes (sin tabla persistida en v1).

---

## 2. Casos numéricos resueltos a mano (fixtures de prueba)

> 🔴 **CU asumido = 0.0850 (8.5%)** — **valor de ejemplo, PENDIENTE de sustituir por el CU real** de la
> empresa (bloqueo del plan). La mecánica y los tests no cambian al reemplazarlo; solo los montos.

### Caso A — Persona moral, régimen general (acumulación ene→mar 2026)
CU = 0.0850, tasa = 30%, sin PTU, sin pérdidas, sin retenciones.

| Mes | Ingreso nominal del mes | Nominal **acumulado** | Utilidad estimada (×0.0850) | ISR acumulado (×30%) | Pagos previos | **Pago del mes** |
|---|---|---|---|---|---|---|
| Enero   | 1,000,000 | 1,000,000 | 85,000  | 25,500 | 0      | **25,500** |
| Febrero | 1,200,000 | 2,200,000 | 187,000 | 56,100 | 25,500 | **30,600** |
| Marzo   |   800,000 | 3,000,000 | 255,000 | 76,500 | 56,100 | **20,400** |

Verificación marzo: 3,000,000 × 0.0850 = 255,000; × 30% = 76,500; − (25,500 + 30,600) = **20,400**. ✔

### Caso B — Con retención de ISR (intereses bancarios)
Mismos datos de **enero** (ISR acumulado 25,500) pero con `isr_retenido` del periodo = 1,500:

```
pago_enero = 25,500 − 0 (pagos previos) − 1,500 (retención) = 24,000
```

### Caso C — Con PTU y pérdidas (disminución de la base)
Enero, ingresos nominales acum = 1,000,000, CU 0.0850 → utilidad estimada 85,000.
PTU pagada en el ejercicio = 20,000; pérdidas pendientes = 15,000.

```
base = 85,000 − 20,000 − 15,000 = 50,000
isr_acumulado = 50,000 × 30% = 15,000
pago_enero = 15,000
```

### Casos borde a cubrir en pruebas (Días 9-10)
- **Nota de crédito (tipo E)** emitida: resta del ingreso nominal acumulado.
- **CFDI recibido**: NO es ingreso (no cuenta).
- **PPD sin REP**: SÍ acumula ISR (devengado, a diferencia del IVA).
- **CFDI cancelado**: excluido.
- **Anticipo SAT** (`es_anticipo_sat`): excluido del ingreso nominal.
- **Base negativa** (pérdidas + PTU > utilidad estimada): base = 0, pago = 0.
- **Continuidad del acumulado**: el pago de marzo debe restar exactamente los pagos de ene+feb.
- **Sin CU capturado** para el ejercicio → error 422/404 controlado (no romper con 500).

---

## 3. Modelo de datos y consultas (cómo se calcula)

### 3.1 Fuente de datos
- **Ingresos**: tabla única `cfdi` (dirección por `rfc_emisor` = `empresas.rfc`). Columnas clave:
  `tipo_comprobante` (I / E), `estado`, `es_anticipo_sat`, `fecha_emision`, `subtotal`, `total`,
  `isr_retenido`.
- **Parámetros anuales**: tabla nueva `config_isr_empresa` (migración **024**):
  `coeficiente_utilidad NUMERIC(6,4)`, `perdidas_pendientes NUMERIC(18,2)`,
  `ptu_pagada NUMERIC(18,2)`, `tasa_isr NUMERIC(4,2) DEFAULT 0.30`, `UNIQUE(empresa_id, ejercicio)`.

A diferencia del IVA, el ISR **sí necesita una tabla** porque el CU/PTU/pérdidas no salen de los CFDIs.

### 3.2 Consulta — ingreso nominal acumulado del ejercicio (ene → fin de mes)
```sql
SELECT COALESCE(SUM(
         CASE WHEN c.tipo_comprobante = 'E' THEN -c.subtotal ELSE c.subtotal END
       ), 0) AS ingreso_nominal
FROM cfdi c
JOIN empresas e ON e.id = c.empresa_id
WHERE c.empresa_id = %s
  AND c.rfc_emisor = e.rfc
  AND c.tipo_comprobante IN ('I','E')
  AND c.estado = 'vigente'
  AND c.es_anticipo_sat = FALSE
  AND c.fecha_emision >= (%s || '-01-01')::date                 -- 1 de enero del ejercicio
  AND c.fecha_emision  < ((%s || '-01')::date + INTERVAL '1 month')  -- fin del mes declarado
```
(`%s` = ejercicio 'YYYY' para el inicio; periodo 'YYYY-MM' para el corte superior.)

### 3.3 Consulta — retención de ISR del **mes declarado**
```sql
SELECT COALESCE(SUM(c.isr_retenido), 0) AS isr_retenido
FROM cfdi c
JOIN empresas e ON e.id = c.empresa_id
WHERE c.empresa_id = %s
  AND c.rfc_emisor = e.rfc
  AND c.estado = 'vigente'
  AND c.fecha_emision >= (%s || '-01')::date
  AND c.fecha_emision  < ((%s || '-01')::date + INTERVAL '1 month')
```

### 3.4 Pagos provisionales anteriores — decisión de diseño
**v1: cómputo iterativo, sin tabla de pagos persistida.** El endpoint del mes N calcula internamente
los pagos de los meses 1..N-1 del mismo ejercicio con la misma función pura (recursión/iteración sobre
el ingreso nominal acumulado a cada corte). Ventaja: cero estado que mantener y siempre consistente con
los CFDIs vigentes actuales. Costo: recalcula N cortes por consulta (N ≤ 12, despreciable).
Persistir los pagos declarados (para congelar lo ya presentado ante el SAT) queda como mejora posterior.

### 3.5 Motor puro (Día 7)
`backend/isr.py`, simétrico en estilo a `backend/iva.py` (funciones puras, `Decimal`, sin tocar DB):
```
isr_provisional(ingresos_por_mes: dict[int, Decimal],   # {1: nominal_ene_mes, ...} acumulado a cada corte
                mes: int, cu: Decimal, tasa: Decimal,
                ptu: Decimal, perdidas: Decimal,
                retencion_mes: Decimal) -> dict
    # -> {ingreso_nominal_acum, utilidad_estimada, base_gravable,
    #     isr_acumulado, pagos_previos, retencion, pago_del_mes}
```
Montos con `decimal.Decimal` y `quantize` a centavos; CU/tasa como `Decimal`.

---

## 4. Contrato del endpoint (Día 8)

`GET /api/v1/empresas/{empresa_id}/isr-provisional/{periodo}`  → router `reportes.py`

Autorización: `validar_acceso_empresa(empresa_id, current_user)` como primer statement tras validar el
formato de `periodo` (regex `^\d{4}-(0[1-9]|1[0-2])$`, igual que la cédula de IVA → 422 si no cuadra).

Respuesta (montos serializados a float):
```jsonc
{
  "empresa_id": "…", "periodo": "2026-03", "ejercicio": 2026,
  "coeficiente_utilidad": 0.0850,
  "ingreso_nominal_acumulado": 3000000.00,
  "utilidad_estimada": 255000.00,
  "deducciones_base": { "ptu_pagada": 0.00, "perdidas_pendientes": 0.00 },
  "base_gravable": 255000.00,
  "tasa_isr": 0.30,
  "isr_acumulado": 76500.00,
  "pagos_provisionales_anteriores": 56100.00,
  "isr_retenido": 0.00,
  "resultado": {
    "pago_del_mes": 20400.00
  }
}
```

Errores:
- **403** si el usuario no tiene acceso a la empresa.
- **404** si la empresa no existe **o** no hay `config_isr_empresa` para el ejercicio (falta el CU).
- **422** si `periodo` no es `YYYY-MM`.

---

## 5. Plan de implementación (Días 7-10)

- **Día 7** — `backend/isr.py`: función pura `isr_provisional(...)` + acumulación del ejercicio mes a
  mes. Tests unitarios contra los Casos A/B/C (pagos 25,500 / 30,600 / 20,400; retención; PTU+pérdidas).
- **Día 8** — endpoint en `reportes.py` cableado a la función pura + loader de `config_isr_empresa` y
  de ingresos nominales acumulados. Verificar en `/docs`.
- **Día 9** — pruebas con varios meses acumulados; continuidad del acumulado; casos borde (§2).
- **Día 10** — validación E2E contra Postgres real cruzada con el cálculo a mano de un ejercicio.

## 6. Decisiones tomadas en el Día 6
1. **Con migración** — `024_coeficiente_utilidad.sql` (tabla `config_isr_empresa`), porque el CU/PTU/
   pérdidas/tasa NO se derivan de los CFDIs. El **cálculo** sigue siendo on-the-fly.
2. **Base devengado** (por `fecha_emision`), motor separado del de IVA; nada de REP/flujo de efectivo.
3. **Pagos provisionales anteriores: cómputo iterativo** en v1 (sin tabla de pagos persistida).
4. **Ingresos nominales v1** = CFDI I emitidos − notas de crédito, sin ajuste anual por inflación ni
   ingresos acumulables sin CFDI (documentado como fast-follow).
5. **PTU/pérdidas** aplicadas como saldo capturado (sin prorrateo mayo-diciembre en v1).
6. **CU es insumo externo capturado a mano** (bloqueo real del plan): el caso de esta spec usa
   **CU = 0.0850 asumido**, a sustituir por el coeficiente real de la empresa.

## 7. Bloqueos pendientes (dependen de Carlos)
- **Coeficiente de utilidad real** del ejercicio anterior de la(s) empresa(s) → reemplaza el 0.0850.
- Idealmente, **un pago provisional real ya presentado** (con su papel de trabajo) para calibrar el
  fixture del Día 10.
