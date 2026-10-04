# F5 — IVA base flujo detallado — Diseño

Fecha: 2026-10-04. Carril C. Depende de F1 (integrada). Plan maestro: `2026-10-01-paridad-y-mejoras-roadmap.md` (secciones "IVA (F4, F5)", "Reglas comunes" y "Criterios que los cálculos deben respetar"). Comportamiento de referencia: `2026-10-01-referencia-plataforma.md`, sección "IVA base flujo".

## Objetivo

Que el contador vea, para un mes, **de dónde sale cada peso del IVA**: trasladado cobrado y acreditable pagado, por tasa (16 %, 8 %, 0 %, exento), con retenciones, separado por origen (contado, cobro/pago de crédito, notas de crédito), con la lista de CFDI que compone cada cifra, y que pueda **no considerar** un CFDI o **reasignarlo a otro periodo** con constancia de quién y por qué. Con esto la cédula de IVA deja de ser una caja negra y se corrigen las tres limitaciones que F4 documentó.

## Entregas

| Entrega | Contenido | Depende de |
|---|---|---|
| **F5.1** | Motor `iva_flujo.py` (por tasa, origen, retenciones, reglas de exclusión), migración 050 (ajustes), endpoints de resumen, detalle y ajustes con auditoría | F1 |
| **F5.2** | Pantalla "IVA base flujo" (tres pestañas, tarjetas por origen, detalle por CFDI, interruptor y periodo reasignado) y exportación a Excel | F5.1, F3.4 |
| **F5.3** | Cédula de IVA y tabla del Inicio pasan al motor nuevo (misma cifra en las tres pantallas) | F5.1 |
| **F5.4** | IVA cobrado vía REP con `pago20:Totales`, `ImpuestosP` y `ObjetoImpDR`: sustituye una sola función | F3.5a (carril A) en `main` |

Esta spec fija las reglas y el contrato de todo F5; el plan de F5.1 está en `docs/superpowers/plans/2026-10-04-f5-1-motor-iva-flujo.md`.

## Alcance

**Entra:** IVA (impuesto `002`) trasladado por emitidos y acreditable por recibidos, tipos I y E, y complementos de pago (P) como evento de cobro/pago; ajustes manuales por CFDI; exportación.

**No entra:** IEPS, ISR e impuestos locales (ISR es F7); DIOT (F6); la lista de proveedores 69-B (M3); el prorrateo por actos exentos con captura de ingresos exentos (se conserva el factor manual de la cédula, `?factor=`, y F5 lo expone en el resumen).

## Reglas fiscales

### Momento del efecto (flujo de efectivo, LIVA 1-B y 5)

| Documento | Efecto | Fecha | Importe |
|---|---|---|---|
| Ingreso/Egreso PUE | Contado | Fecha de emisión | El del CFDI (`cfdi_impuestos`) |
| Ingreso PPD | Cobro/pago de crédito | Fecha de cada pago (REP) | Lo del documento relacionado (`ImpuestosDR`) |
| Egreso (nota de crédito, devolución, descuento) | Nota de crédito | Fecha de emisión | Resta, con su propio desglose |
| Pago (REP) | No es efecto por sí mismo: es la fecha y el importe del cobro de un PPD | — | — |

- **Solo vigentes.** Un CFDI cancelado no produce efectos. Un REP cancelado, tampoco. Un cancelado que ya se consideró en un periodo declarado se avisa en M3; aquí solo se excluye.
- **Dirección.** Trasladado: la empresa es emisora del CFDI original. Acreditable: la empresa es receptora. Para un REP se usa la dirección del documento que paga, no la del REP.
- **Anticipos (corrige a la cédula actual).** El anticipo (A) **sí** causa IVA en su fecha (se cobró); la factura final (B) causa el IVA completo; el egreso que aplica el anticipo (C, forma de pago 30) resta el IVA de A. Neto en el tiempo: A + B − C = B. La cédula actual excluye A y resta C, lo que descuenta el anticipo dos veces; F5.3 lo corrige. C aparece en origen "Notas de crédito" con la marca `aplicacion_anticipo`.
- **Moneda extranjera.** Importes del CFDI × tipo de cambio del comprobante. En un cobro, la conversión usa el tipo de cambio del pago: pesos = (importe del documento ÷ `equivalencia_dr`) × tipo de cambio del pago (1 si el pago es en MXN). Si `equivalencia_dr` es nula y la moneda del documento difiere de la del pago, el renglón se marca `sin_equivalencia` y **no se suma** (no se asume 1).

### Desglose por tasa

Se toma de `cfdi_impuestos` (ámbito traslado, impuesto `002`), una fila por tasa:

- `Tasa 0.16` → 16 %; `Tasa 0.08` → 8 %; `Tasa 0.00` → 0 %; `Exento` → exento (solo base, sin IVA).
- Otras tasas (histórico 11 %, cuotas) caen en `otras` y se muestran aparte; nunca se mezclan en el 16 %.
- **No objeto**: concepto con `ObjetoImp = 01` no deja fila en `cfdi_impuestos`; su base se obtiene de `cfdi_conceptos` (`objeto_imp = '01'`, importe − descuento) y se muestra como base "no objeto", fuera de la base gravada.
- **Cifra oficial.** El IVA total del CFDI es el del encabezado (`cfdi.iva_trasladado`); la suma por tasa lo explica. Si difiere en más de 1 centavo por renglón de tasa (CFDI 3.3, redondeos), el CFDI se marca `descuadre` y se usa el encabezado como total; el desglose queda informativo.
- Egresos y notas de crédito se desglosan igual y restan.

### Retenciones de IVA

- `cfdi_impuestos` ámbito retención, impuesto `002`. Una retención leída solo del nodo raíz tiene base 0 y tasa nula: se suma su importe y **no** se interpreta como tasa 0 %.
- **Emitidos con retención** (el cliente le retiene a la empresa): el IVA retenido disminuye el IVA a cargo del mes en que se cobra. Se muestra en el trasladado como "Retenciones que le hacen a la empresa".
- **Recibidos con retención** (la empresa retiene a su proveedor): es un entero aparte, no reduce el acreditable. Se muestra como "Retenciones que la empresa debe enterar".
- Siguen el mismo momento del efecto que el IVA trasladado/acreditable del CFDI.

### Acreditable: quién se considera y quién no

Se acredita solo la erogación deducible y pagada. No se consideran, con su motivo visible en "No considerados":

| Motivo | Regla |
|---|---|
| `efectivo` | Forma de pago `01` con total mayor a $2,000 (LIVA 5-III; ya implementado) |
| `uso_no_deducible` | Uso de CFDI `S01` (sin efectos fiscales), `CP01` y `CN01`: no son una erogación acreditable |
| `pago_v1` | El REP es versión 1.0 y no trae impuestos del documento: se usa la proporción `importe pagado ÷ total` sobre el desglose del CFDI original y el renglón se marca `aproximado` (regla común del plan maestro). *La referencia, en cambio, no considera los REP 1.0; es una diferencia deliberada que se revisa en el cuadre.* |
| `manual` | El contador lo excluyó (ver ajustes) |

Los CFDI no considerados no suman, pero **se listan** con su motivo.

### Pagos de varios documentos y de varios meses

Un REP trae un nodo de pago por fecha; cada documento relacionado trae su propio desglose (`pagos_relaciones_impuestos`). Cada documento relacionado es un evento independiente con la fecha de **su pago**. Hasta F5.4 no se leen `pago20:Totales` ni `ImpuestosP`, de modo que no hay "control de cuadre" contra la cifra oficial del REP; el motor lo deja como función aislada (`iva_de_pago`) para que F5.4 la sustituya sin tocar el resto.

### Interruptor "no considerar IVA" y periodo reasignado

Decisiones del contador, **por CFDI y dirección**, que se guardan en `iva_ajustes` (migración 050) y quedan en `auditoria` con usuario, fecha y motivo:

- **No considerar**: el CFDI sale de las sumas (queda listado como `manual`). Reversible.
- **Periodo reasignado**: el efecto del CFDI se mueve a otro periodo `YYYY-MM` (por ejemplo, una factura que el proveedor emitió en octubre pero se pagó en septiembre). Aplica a todos sus eventos; en el periodo original aparece en "Periodo reasignado" y no suma; en el destino suma como si hubiera ocurrido ahí.
- Un ajuste es único por (empresa, CFDI, dirección). Reasignar y no considerar son excluyentes.
- Un periodo ya "cerrado" no existe todavía (M2): los ajustes siempre se permiten y siempre se auditan.

## Contrato de API (F5.1)

Todos requieren acceso a la empresa; periodos `YYYY-MM`; importes con dos decimales.

### `GET /api/v1/empresas/{id}/iva-flujo/{periodo}?factor=1`

```json
{
  "periodo": "2026-09", "empresa_id": "…", "factor_prorrateo": 1,
  "trasladado": {
    "origenes": {
      "contado":      {"cfdi": 0, "bases": {"16": 0, "8": 0, "0": 0, "exento": 0, "otras": 0, "no_objeto": 0},
                       "iva": {"16": 0, "8": 0, "otras": 0, "total": 0}, "retenciones": 0, "total": 0},
      "credito":      {"…": "…", "pagos": 0, "documentos": 0},
      "notas_credito": {"…": "…"}
    },
    "total": {"bases": {}, "iva": {}, "retenciones": 0, "total": 0},
    "no_considerados": {"cfdi": 0, "iva": 0}, "reasignados": {"cfdi": 0, "iva": 0}
  },
  "acreditable": {"…": "misma forma, con origen \"credito\" = pago de facturas de crédito, más ajustado = bruto × factor"},
  "retenciones_a_enterar": 0,
  "resultado": {"trasladado": 0, "acreditable": 0, "retenciones_a_favor": 0, "iva_por_pagar": 0, "saldo_a_cargo": 0, "saldo_a_favor": 0},
  "advertencias": [{"codigo": "pago_v1", "mensaje": "…", "cfdi": 2}]
}
```

`resultado.iva_por_pagar = trasladado.total − acreditable.ajustado − retenciones_a_favor`.

### `GET /api/v1/empresas/{id}/iva-flujo/{periodo}/detalle?direccion=trasladado|acreditable&origen=contado|credito|notas_credito|no_considerados|reasignados&pagina=&por_pagina=`

Lista paginada de lo que compone una cifra: UUID, fecha de emisión, **fecha de pago** y UUID del REP (crédito), contraparte, bases por tasa, IVA por tasa, retención, total, marcas (`aproximado`, `descuadre`, `aplicacion_anticipo`, `sin_equivalencia`), motivo si no se considera y el ajuste vigente. Es la lista que abre cada tarjeta y la base de la exportación y de M1 (trazabilidad): cada renglón lleva `uuid` para saltar al visor del CFDI.

### `PUT /api/v1/empresas/{id}/iva-flujo/ajustes` · `DELETE …/ajustes/{direccion}/{uuid}`

`PUT` con `{"uuid", "direccion", "accion": "excluir"|"reasignar", "periodo_destino"?, "motivo"}`; crea o reemplaza el ajuste y deja `auditoria` (`iva_ajuste`). `DELETE` lo retira y también audita. 404 si el CFDI no es de la empresa; 422 con `reasignar` sin `periodo_destino`, con `periodo_destino` igual al periodo de efecto, o con periodo mal formado.

## Pantalla (F5.2)

Tres tarjetas-pestaña, como la referencia: **Trasladado**, **Acreditable** y **A cargo** (la resta). Cada una con las tarjetas por origen (Totales, Contado, Cobro/Pago de crédito con "pagos / documentos", Notas de crédito, No considerados, Periodo reasignado) y, al elegir una, la tabla de detalle con las bases e IVA por tasa. Un interruptor por renglón abre el motivo y llama a `PUT ajustes`. Exportar descarga un `.xlsx` con el detalle de la tarjeta (descarga directa; con volúmenes mayores a 50,000 renglones se pide acotar, como en F3.4). Aviso fijo sobre los REP versión 1.0.

## Decisiones

| # | Decisión | Valor por defecto | Cómo se cambia |
|---|---|---|---|
| D-F5-1 | REP 1.0: se aproxima por proporción y se avisa (el plan maestro lo pide; la referencia los excluye) | Aproximar | Constante `PAGOS_V1_MODO` en `iva_flujo.py` (`"aproximar"` / `"excluir"`) |
| D-F5-2 | El anticipo (A) sí causa IVA y su egreso de aplicación (C) lo resta | A + B − C = B | Se ajusta en un solo lugar del motor |
| D-F5-3 | Usos `S01`, `CP01`, `CN01` no son acreditables | No acreditable | Lista `USOS_NO_ACREDITABLES` |
| D-F5-4 | Tasas distintas de 16, 8, 0 y exento caen en "otras" | Aparte | — |
| D-F5-5 | Los ajustes son por CFDI y dirección, siempre permitidos y auditados | Sin cierre de periodo hasta M2 | M2 agrega el bloqueo |
| D-F5-6 | `no_objeto` se informa como base, nunca suma al IVA ni a la base gravada | Informativo | — |

## Criterios de aceptación (con datos sembrados en la E2E)

1. Un CFDI PUE con renglones al 16 %, 8 %, 0 % y exento aparece en "contado" con cada base e IVA en su columna; la suma por tasa coincide con el IVA del encabezado.
2. Un PPD cobrado en dos pagos de meses distintos suma en cada mes solo el IVA de **su** pago, con la fecha de pago visible; un REP 2.0 usa `ImpuestosDR`; un REP 1.0 usa la proporción y genera la advertencia `pago_v1`.
3. Una nota de crédito resta y se muestra aparte; el egreso de aplicación de anticipo resta el IVA del anticipo y el neto A + B − C es el de B.
4. Un CFDI en USD cobrado en MXN se convierte con `equivalencia_dr` y el tipo de cambio del pago; con `equivalencia_dr` nula y monedas distintas queda `sin_equivalencia` y no suma.
5. Efectivo mayor a $2,000, usos `S01`/`CP01`/`CN01` y cancelados no suman en acreditable; los dos primeros se listan en "No considerados" con su motivo.
6. Excluir un CFDI lo quita de las sumas y lo lista como `manual`; reasignarlo lo mueve al periodo destino; ambos quedan en `auditoria` con usuario y motivo; quitar el ajuste lo devuelve.
7. Las retenciones de IVA que le hacen a la empresa reducen el IVA por pagar; las que la empresa hace no reducen el acreditable.
8. Un periodo sin movimiento devuelve ceros en todas las tarjetas, no error.
9. Usuario sin acceso a la empresa: 403; periodo, origen o dirección inválidos: 422; CFDI ajeno: 404.
10. **Cuadre contra la referencia** (cifras de control: IVA trasladado cobrado 3,190,362.48 = contado 2,275,262.33 + crédito 915,100.15; IVA acreditable pagado 2,162,403.41; IVA a cargo 1,027,959.07; retenciones 3,786.75): requiere los CFDI reales de COPLASUR; se hace en el cierre de F0/F1 (carril B) y toda diferencia se explica por escrito en el PR sin ajustar el cálculo sin fundamento legal.
