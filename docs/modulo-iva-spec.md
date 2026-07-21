# Módulo 3 — Cédula de IVA · Spec ejecutable (Día 1)

> Estado: **DISEÑO** — blueprint para implementar en los Días 2-5 del plan.
> Objetivo del módulo: calcular la **cédula mensual de IVA** (trasladado, acreditable, prorrateo y
> resultado del periodo) **en base a flujo de efectivo** (Art. 1-B LIVA), comparable contra el
> preload/DIOT del SAT.

---

## 1. Reglas fiscales (qué se calcula)

### 1.1 IVA trasladado (ventas — la empresa es emisora)
Un CFDI aporta IVA trasladado al periodo cuando **se cobró** en el periodo:

| Método de pago | Condición de causación | Fecha que manda | IVA a sumar |
|---|---|---|---|
| **PUE** (tipo `I`) | `fecha_emision` dentro del periodo | `fecha_emision` | `cfdi.iva_trasladado` completo |
| **PPD** (tipo `I`) | existe REP con `fecha_pago` en el periodo | `pagos_cfdi.fecha_pago` | IVA de la parcialidad (ver §3.2) |

Exclusiones: `estado != 'vigente'` (cancelados/sustituidos fuera), CFDI tipo `P` (no es ingreso),
tipo `E` (nota de crédito / egreso) **resta** de la base, `es_anticipo_sat = TRUE` se maneja con la
lógica de anticipos existente (`emitidos.py:56-129`) para no duplicar IVA (anticipo → factura → aplicación).

### 1.2 IVA acreditable (compras/gastos — la empresa es receptora)
Simétrico al trasladado, pero sobre CFDIs **recibidos efectivamente pagados** en el periodo:

- **PUE recibido** con `fecha_emision` en el periodo → `iva_trasladado` (interpretado como acreditable).
- **PPD recibido** con REP cuyo `fecha_pago` cae en el periodo → IVA de la parcialidad.
- Requisitos de acreditamiento (Art. 5 LIVA): factura a nombre del RFC de la empresa, IVA desglosado,
  gasto estrictamente indispensable, y **pagado por medio bancarizado**. Regla dura para v1:
  `forma_pago = '01'` (efectivo) con total > $2,000 **no es acreditable** → se marca y se excluye.
- El **preload del SAT es solo sugerencia**; el contribuyente determina el monto real (Art. 6 CFF).
  Por eso la cédula se calcula desde los CFDIs propios y **luego** se compara contra el preload/DIOT.

### 1.3 Prorrateo — actividades mixtas (Art. 5-V LIVA)
Cuando hay actos gravados y exentos, el IVA acreditable de gastos que sirven a ambos se limita por el
factor de prorrateo:

```
factor_prorrateo = actos_gravados / (actos_gravados + actos_exentos)

iva_acreditable_ajustado =
      iva_identificable_a_gravado                     (100% acreditable)
    + iva_identificable_a_exento        * 0           (no acreditable)
    + iva_no_identificable  * factor_prorrateo        (proporcional)
```

**v1 (MVP):** soporta el caso común **100% gravado** (`factor = 1.0`, como Copla Sur) y un
`factor_prorrateo` global opcional por empresa/periodo. La clasificación por-CFDI de
gravado/exento/no-identificable queda como mejora posterior (requiere config de conceptos).

### 1.4 Resultado del periodo
```
iva_por_pagar   = total_trasladado - iva_acreditable_ajustado - iva_retenido_a_favor
saldo_a_cargo   = max(iva_por_pagar, 0)
saldo_a_favor   = max(-iva_por_pagar, 0)   # se arrastra al siguiente periodo
```

---

## 2. Casos numéricos resueltos a mano (fixtures de prueba)

### Caso A — Copla Sur, enero 2026 (real, requerimiento SAT)
100% actividad gravada al 16%, sin prorrateo.

| Concepto | Base | IVA |
|---|---|---|
| Actos **cobrados** gravados 16% | $25,553,202.00 | **$4,088,513** trasladado |
| Actos **pagados** gravados 16% | $19,103,728.00 | **$3,056,596** acreditable |
| **IVA por pagar del mes** | | **$1,031,917** a cargo |

Nota: el SAT observó además $727,082 "a favor del contribuyente" de origen no identificado — es una
observación de auditoría, **no** entra en el cálculo de la cédula. Verificación: 25,553,202 × 16% =
4,088,512.32 ≈ 4,088,513 (redondeo a peso de la declaración). *En la cédula sumamos
`cfdi.iva_trasladado` real (con centavos), y el 16%×base es solo sanity check.*

### Caso B — Consultora, un mes (unitario chico)
| Concepto | Ingreso | Egreso | IVA ingreso | IVA gasto |
|---|---|---|---|---|
| Cobro de mediación | 10,000 | | 1,600.00 | |
| Pedido | | 2,000 | | 320.00 |
| Papelería | | 500 | | 80.00 |
| Coffee break | | 500 | | 80.00 |
| Combustible | | 600 | | 96.00 |
| Teléfono | | 500 | | 80.00 |
| Internet | | 500 | | 80.00 |
| **Total** | **10,000** | **4,600** | **1,600.00** | **736.00** |

**IVA por pagar = 1,600 − 736 = $864.00**

### Casos borde a cubrir en pruebas (Día 5)
- Solo PUE (sin PPD): trasladado = SUM de PUE del periodo.
- PPD con REP en el periodo vs REP en periodo distinto (no debe contar).
- CFDI cancelado: excluido.
- Gasto pagado en efectivo > $2,000: no acreditable.
- Actividad mixta con `factor_prorrateo = 0.8`.
- Nota de crédito (tipo E): resta de la base trasladada.

---

## 3. Modelo de datos y consultas (cómo se calcula)

### 3.1 Fuente de datos (sin tablas nuevas para el cálculo)
Todo sale de la tabla única `cfdi` + `pagos_cfdi` + `pagos_relaciones` (ver mapa completo en el
reporte de arquitectura). Dirección del CFDI = comparar `rfc_emisor`/`rfc_receptor` contra
`empresas.rfc`. Columnas clave: `iva_trasladado`, `iva_retenido`, `subtotal`, `total`,
`tipo_comprobante`, `metodo_pago`, `forma_pago`, `estado`, `fecha_emision`, `es_anticipo_sat`.

**Decisión de persistencia: cálculo _on-the-fly_ (sin migración).** Consistente con el endpoint DIOT
y demás reportes, que no persisten resultados. Esto **libera el número de migración `024` para el
Módulo 5 (ISR)**. Persistir un snapshot de la cédula (para histórico/comparación versionada) queda
como mejora opcional posterior.

### 3.2 IVA por parcialidad en PPD (aproximación v1)
`pagos_relaciones` **no** guarda el IVA de la parcialidad (falta parsear
`pago20:ImpuestosDR/TrasladoDR/@ImporteDR`). Para v1 se aproxima proporcionalmente:

```
iva_pagado_parcialidad ≈ cfdi.iva_trasladado * (pagos_relaciones.importe_pagado / cfdi.total)
```

Exacto cuando el CFDI tiene una sola tasa 16% (caso mayoritario). **Fast-follow recomendado:**
extender `_extraer_pagos()` en `cfdi_parser.py` para leer `ImporteDR` y persistir el IVA exacto por
parcialidad (mejora la precisión de PPD multi-tasa).

### 3.3 Consultas (plantilla basada en el DIOT de `reportes.py:164-182`)

**Trasladado PUE** (ventas cobradas al contado, dentro del periodo):
```sql
SELECT SUM(c.subtotal)       AS base,
       SUM(c.iva_trasladado) AS iva
FROM cfdi c
JOIN empresas e ON e.id = c.empresa_id
WHERE c.empresa_id = %s
  AND c.rfc_emisor = e.rfc
  AND c.tipo_comprobante = 'I'
  AND c.metodo_pago = 'PUE'
  AND c.estado = 'vigente'
  AND c.es_anticipo_sat = FALSE
  AND c.fecha_emision >= (%s || '-01')::date
  AND c.fecha_emision  < ((%s || '-01')::date + INTERVAL '1 month')
```

**Trasladado PPD** (ventas cobradas vía REP en el periodo):
```sql
SELECT SUM(c.iva_trasladado * (pr.importe_pagado / NULLIF(c.total,0))) AS iva,
       SUM(pr.importe_pagado)                                          AS cobrado
FROM pagos_cfdi p
JOIN pagos_relaciones pr ON pr.pago_id = p.id
JOIN cfdi c ON c.uuid = pr.cfdi_uuid AND c.empresa_id = p.empresa_id
JOIN empresas e ON e.id = c.empresa_id
WHERE p.empresa_id = %s
  AND c.rfc_emisor = e.rfc
  AND c.metodo_pago = 'PPD'
  AND c.estado = 'vigente'
  AND p.fecha_pago >= (%s || '-01')::date
  AND p.fecha_pago  < ((%s || '-01')::date + INTERVAL '1 month')
```

**Acreditable** = mismas dos consultas invirtiendo `rfc_emisor`→`rfc_receptor`, más el filtro de
exclusión de efectivo (`NOT (forma_pago = '01' AND total > 2000)`).

Periodo: `VARCHAR(7)` formato `'YYYY-MM'`, rango vía `(%s || '-01')::date … + INTERVAL '1 month'`.
Montos con `decimal.Decimal`; conexión con `db.query_all/query_one`; autorización con
`validar_acceso_empresa(empresa_id, current_user)` como primer statement.

---

## 4. Contrato del endpoint (Día 4)

`GET /api/v1/empresas/{empresa_id}/cedula-iva/{periodo}`  → router `reportes.py`

Respuesta (montos serializados con `serializar()`):
```jsonc
{
  "empresa_id": "…", "periodo": "2026-01",
  "trasladado": {
    "pue":  { "base": 0, "iva": 0 },
    "ppd":  { "cobrado": 0, "iva": 0 },
    "notas_credito": { "base": 0, "iva": 0 },   // resta
    "total": 4088513.00
  },
  "acreditable": {
    "pue": { "base": 0, "iva": 0 },
    "ppd": { "pagado": 0, "iva": 0 },
    "excluido_efectivo": { "iva": 0 },          // no acreditable
    "bruto": 3056596.00,
    "factor_prorrateo": 1.0,
    "ajustado": 3056596.00
  },
  "iva_retenido": 0.00,
  "resultado": {
    "iva_por_pagar": 1031917.00,
    "saldo_a_cargo": 1031917.00,
    "saldo_a_favor": 0.00
  },
  "comparativo_sat": {                           // opcional / placeholder v1
    "diot_iva_pagado": 3056596.00,
    "diferencia": 0.00
  }
}
```

Errores: 403 si el usuario no tiene acceso a la empresa; 404 si la empresa no existe; periodo
inválido (no `YYYY-MM`) → 422.

---

## 5. Plan de implementación (Días 2-5)

- **Día 2** — `backend/iva.py`: funciones puras `iva_trasladado(cfdis, pagos, periodo) -> DesgloseTrasladado`.
  Test unitario contra Caso B (trasladado = 1,600) y Caso A (4,088,513).
- **Día 3** — `iva_acreditable(...)` + `aplicar_prorrateo(bruto, factor)`. Test acreditable = 736 / 3,056,596; prorrateo 0.8.
- **Día 4** — endpoint en `reportes.py`, cableado a las funciones puras + comparativo DIOT. Verificar en `/docs`.
- **Día 5** — suite completa de casos borde (§2) + validación E2E con un CFDI real.

## 6. Decisiones tomadas en el Día 1
1. **Sin migración** — cálculo on-the-fly (libera `024` para ISR).
2. **IVA de PPD por aproximación proporcional** en v1; parser exacto (`ImporteDR`) como fast-follow.
3. **Prorrateo global** con `factor` (v1 soporta 100% gravado + factor manual); clasificación por-CFDI, después.
4. **Efectivo > $2,000 no acreditable** como única regla de bancarización dura en v1.
5. Fuente de verdad del cobro/pago: `fecha_emision` para PUE, `pagos_cfdi.fecha_pago` para PPD (no la conciliación bancaria).
