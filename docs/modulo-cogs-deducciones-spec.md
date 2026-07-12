# Módulo 4 — COGS / Deducciones · Spec ejecutable (Día 11)

> Estado: **✅ COMPLETO** (Días 11-15, 2026-07-11). Motor puro, endpoint, casos
> borde SQL contra Postgres real y E2E — todos implementados y verificados
> contra el caso Ferretería El Tornillo.
> Objetivo del módulo (MVP): calcular las **deducciones autorizadas** de una persona
> moral sobre CFDIs recibidos y efectivamente pagados (Art. 27 LISR), clasificadas en
> gasto / inversión / costo por `uso_cfdi`.

> ⚠️ **Fuera de alcance de este módulo (MVP):** costeo absorbente completo (LISR
> 39-43, NIF C-4) y depreciación de inversiones (Art. 31-38 LISR) quedan para la
> **fase anual futura**. Este módulo solo calcula el total de **gasto** deducible de
> inmediato; inversión y costo se **identifican** (monto agregado) pero no se
> deducen todavía — evita que se cuenten dos veces sin el cálculo real.

> ⚠️ **Independiente del ISR provisional:** este módulo NO modifica `backend/isr.py`.
> Las deducciones aplican a la **declaración anual**, no al pago provisional mensual
> (Art. 14 LISR no las resta mes a mes — ver nota del doc "4. Módulo de Costos y
> Deducciones (COGS)" en Notion). Es una cédula nueva e independiente.

---

## 1. Reglas fiscales (qué se calcula) — Art. 27 LISR

Una deducción es autorizada cuando el CFDI recibido está **efectivamente pagado**
(regla de flujo de efectivo, igual que el IVA acreditable — Art. 27-III LISR /
Art. 5-V LIVA comparten la misma bancarización):

- **PUE** (tipo I): deducible en `fecha_emision` (el pago se presume inmediato).
- **PPD** (tipo I): deducible cuando hay un pago (REP) con `fecha_pago`; se toma
  proporcional al importe pagado (`monto_cfdi * importe_pagado / total`).
- **Notas de crédito recibidas** (tipo E): restan del monto deducible.
- **Efectivo > $2,000** (`forma_pago == '01'`): **no deducible** (Art. 27-III LISR,
  mismo umbral `UMBRAL_EFECTIVO` ya definido en `backend/iva.py` — se reutiliza, no
  se duplica).
- Se excluyen: CFDIs no vigentes, `es_anticipo_sat = TRUE` (el anticipo se deduce en
  la factura final, no se cuenta dos veces — aprendido de la deuda técnica #2 de
  IVA, aplicado aquí desde el día 1), y CFDIs donde la empresa no es la receptora
  (esos son ventas, no gastos).
- El monto deducible es el **subtotal** (base sin IVA); el IVA se acredita aparte
  en la cédula de IVA (Módulo 3).

### 1.1 Clasificación por `uso_cfdi` (sin migración, sin captura manual)

La tabla `cfdi` no tiene desglose por concepto, solo totales por comprobante. Se
usa el catálogo SAT `c_UsoCFDI` (columna `uso_cfdi`, ya existente) como heurística:

| `uso_cfdi` | Cubeta | Tratamiento MVP |
|---|---|---|
| `G01` (Adquisición de mercancías) | **costo** | Monto identificado, NO se deduce (costeo absorbente = fase anual futura) |
| `I01`-`I08` (catálogo de inversiones) | **inversión** | Monto identificado, NO se deduce (depreciación = fase anual futura) |
| Cualquier otro (`G03`, etc.) | **gasto** | **Se deduce de inmediato** — única cubeta que suma al total deducible del MVP |

Heurística documentada como aproximación: el receptor del CFDI puede capturar
`uso_cfdi` incorrectamente en la práctica (p. ej. "G03" para todo). Refinamiento
(catálogo manual por CFDI) queda como fast-follow si se detectan muchos falsos
positivos/negativos.

### 1.2 Periodo: mes + acumulado del ejercicio

Igual que ISR provisional (para consistencia con el resto de las cédulas del
dashboard), el endpoint recibe un periodo `YYYY-MM` pero devuelve **dos** vistas:

- **`del_mes`**: deducciones pagadas dentro del mes declarado.
- **`acumulado_ejercicio`**: deducciones pagadas desde el 1 de enero hasta el fin
  del mes declarado (útil para proyectar la declaración anual).

A diferencia de ISR, **no hay recursión ni "pagos previos que restar"** — cada
deducción es independiente mes a mes (no hay concepto de "provisional"). El
acumulado es simplemente la misma función pura evaluada con una ventana de fechas
más amplia (ene 1 → fin de mes), no una suma iterativa de meses anteriores.

---

## 2. Caso numérico resuelto a mano (fixture de pruebas)

### Caso A — Ferretería El Tornillo (enero 2026, sintético)

> 🔴 **Caso sintético — PENDIENTE de sustituir por datos reales** cuando estén
> disponibles (mismo patrón que el CU de ISR: la mecánica y los tests no cambian
> al reemplazarlo, solo los montos).

| CFDI | `uso_cfdi` | Método | Subtotal | Cubeta |
|---|---|---|---|---|
| Renta de oficina | G03 | PUE | $20,000 | gasto |
| Honorarios (REP en enero) | G03 | PPD | $15,000 | gasto |
| Nota de crédito recibida (sobre la renta) | G03 (tipo E) | — | −$2,000 | gasto |
| Papelería, pagada en efectivo | G03 | PUE, forma_pago=01 | $3,000 | excluido_efectivo |
| Compra de mercancía | G01 | PUE | $80,000 | costo_identificado |
| Equipo de cómputo | I04 | PUE | $18,000 | inversión_identificada |

```
gasto_enero              = 20,000 + 15,000 − 2,000 = 33,000
costo_identificado_enero = 80,000
inversion_identificada   = 18,000
excluido_efectivo        = 3,000
total_deducible_enero    = 33,000   (solo gasto)
```

### Caso B — Continuidad del acumulado (febrero 2026)

Se agrega en febrero: compra de mercancía G01 $40,000 y servicios G03 $10,000
(PUE, pagado en el mes).

```
gasto_acumulado (ene+feb)  = 33,000 + 10,000 = 43,000
costo_acumulado (ene+feb)  = 80,000 + 40,000 = 120,000
total_deducible_acumulado  = 43,000
```

### Casos borde a cubrir en pruebas (Días 12-14)

- **Nota de crédito recibida** (tipo E): resta de la cubeta correspondiente.
- **CFDI emitido** (la empresa es emisora, no receptora): NO es deducción.
- **PPD sin REP**: NO cuenta hasta que se paga (a diferencia de ISR, aquí SÍ
  importa el flujo de efectivo — igual que IVA acreditable).
- **Efectivo > $2,000**: excluido (bucket `excluido_efectivo`).
- **CFDI cancelado**: excluido.
- **Anticipo SAT** (`es_anticipo_sat`): excluido.
- **`uso_cfdi` nulo o desconocido**: cae en "gasto" por defecto (cubeta más
  conservadora en cuanto a NO sobreestimar costo/inversión sin evidencia).
- **Sin CFDIs en el periodo**: todas las cubetas en 0, sin error.

---

## 3. Modelo de datos y consultas (cómo se calcula)

### 3.1 Fuente de datos

Solo la tabla `cfdi` (dirección por `rfc_receptor` = `empresas.rfc`, la empresa es
la receptora del gasto) + `pagos_cfdi`/`pagos_relaciones` para el flujo PPD/REP,
igual que `_cargar_datos_cedula_iva`. **No se requiere migración**: `uso_cfdi` ya
existe en `cfdi` (migración 001) y no hay parámetros anuales que capturar a mano
(a diferencia de `config_isr_empresa`).

### 3.2 Consulta — CFDIs candidatos del ejercicio a la fecha de corte

Mismo patrón que `_cargar_datos_cedula_iva`: candidatos son PPD (de cualquier
fecha, para cubrir REP pagado dentro de la ventana) o con `fecha_emision` dentro
de la ventana ene 1 → fin del mes declarado. Una sola consulta cubre tanto "del
mes" como "acumulado del ejercicio" (la función pura filtra por rango después).

```sql
SELECT uuid, tipo_comprobante, metodo_pago, estado, es_anticipo_sat, uso_cfdi,
       rfc_emisor, rfc_receptor, forma_pago, fecha_emision, subtotal, total
FROM cfdi
WHERE empresa_id = %s
  AND estado = 'vigente'
  AND (
        metodo_pago = 'PPD'
        OR (fecha_emision >= (%s || '-01-01')::date              -- 1 de enero del ejercicio
            AND fecha_emision  < ((%s || '-01')::date + INTERVAL '1 month'))  -- fin del mes
      )
```

### 3.3 Motor puro (Día 12)

`backend/deducciones.py`, simétrico en estilo a `backend/iva.py` (funciones puras,
`Decimal`, sin tocar DB). Reutiliza `UMBRAL_EFECTIVO` de `iva.py` (no se duplica):

```
deducciones_periodo(cfdis: list[dict], pagos: list[dict], rfc_empresa: str,
                     desde: date, hasta: date) -> dict
    # -> {gasto, inversion_identificada, costo_identificado, excluido_efectivo,
    #     total_deducible}   # total_deducible == gasto en el MVP
```

El endpoint (Día 13) llama esta función dos veces con la misma lista de CFDIs:
una con `desde=mes-01`/`hasta=fin de mes` (del mes), otra con
`desde=ejercicio-01-01`/`hasta=fin de mes` (acumulado).

---

## 4. Contrato del endpoint (Día 13)

`GET /api/v1/empresas/{empresa_id}/deducciones/{periodo}` → router `reportes.py`

Autorización: `validar_acceso_empresa(empresa_id, current_user)` tras validar el
formato de `periodo` (regex `^\d{4}-(0[1-9]|1[0-2])$`, igual que IVA/ISR → 422 si
no cuadra).

Respuesta (montos serializados a float):
```jsonc
{
  "empresa_id": "…", "periodo": "2026-01", "ejercicio": 2026,
  "del_mes": {
    "gasto": 33000.00,
    "inversion_identificada": 18000.00,
    "costo_identificado": 80000.00,
    "excluido_efectivo": 3000.00
  },
  "acumulado_ejercicio": {
    "gasto": 33000.00,
    "inversion_identificada": 18000.00,
    "costo_identificado": 80000.00,
    "excluido_efectivo": 3000.00
  },
  "total_deducible_mes": 33000.00,
  "total_deducible_acumulado": 33000.00
}
```

Errores:
- **403** si el usuario no tiene acceso a la empresa.
- **404** si la empresa no existe.
- **422** si `periodo` no es `YYYY-MM`.

(No hay 404 por "falta configuración" — a diferencia de ISR, este módulo no
depende de un insumo anual capturado a mano.)

---

## 5. Plan de implementación (Días 11-15)

- **Día 11** — Esta spec. Alcance MVP definido, sin migración.
- **Día 12** — `backend/deducciones.py`: función pura `deducciones_periodo(...)`.
  Tests unitarios contra los Casos A/B (gasto 33,000 / acumulado 43,000) y bordes
  (nota de crédito, efectivo, anticipo SAT, PPD sin REP, cancelado).
- **Día 13** — endpoint en `reportes.py` cableado a la función pura + loader de
  CFDIs candidatos. Verificar en `/docs`.
- **Día 14** — `test_deducciones_cargar_datos.py` contra Postgres real (casos
  borde del filtrado SQL, mismo patrón que el Día 9 de ISR) + documentar
  explícitamente el alcance NO cubierto (depreciación, costeo absorbente) en este
  mismo archivo.
- **Día 15** — E2E completo (register → alta empresa → CFDIs → GET) cruzado contra
  el Caso A/B a mano. Cierra Fase A: flujo CFDI → conciliación → IVA → ISR →
  deducciones sobre un caso real.

## 6. Decisiones tomadas en el Día 11

1. **Sin migración** — `uso_cfdi` ya existe en `cfdi` (migración 001); no hay
   parámetros anuales que capturar a mano (a diferencia de ISR).
2. **Clasificación por `uso_cfdi`** (heurística de catálogo SAT: G01→costo,
   I01-I08→inversión, resto→gasto) en vez de catálogo manual — evita carga
   operativa constante, a costo de precisión si el receptor capturó mal el
   `uso_cfdi` (documentado como fast-follow).
3. **Solo "gasto" se deduce en el MVP** — inversión y costo se identifican pero no
   se suman al total deducible, para no sobreestimar sin depreciación/costeo real.
4. **Cédula independiente del ISR provisional** — no modifica `backend/isr.py`;
   las deducciones aplican a la declaración anual, no al pago provisional mensual.
5. **Periodo mensual con acumulado del ejercicio** (mismo patrón que ISR), pero
   sin recursión — el acumulado es la misma función con una ventana de fechas más
   amplia, no una resta de pagos previos.
6. **Reutiliza `UMBRAL_EFECTIVO` de `iva.py`** (Art. 27-III LISR / Art. 5-V LIVA
   comparten el mismo umbral de bancarización) — no se duplica la constante.
7. **Excluye `es_anticipo_sat` desde el día 1** — aprendido de la deuda técnica #2
   de IVA (donde `iva_acreditable()` no lo excluye), aplicado aquí de inmediato.

## 7. Bloqueos pendientes (dependen de Carlos)

- **Caso real de deducciones** de la(s) empresa(s) → reemplaza el Caso A/B
  sintético (Ferretería El Tornillo).
- Confirmar si la heurística por `uso_cfdi` es suficientemente precisa en la
  práctica, o si se necesita el catálogo manual (fast-follow) más adelante.
