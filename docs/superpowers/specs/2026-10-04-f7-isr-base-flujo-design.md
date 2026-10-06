# F7 — ISR base flujo (diseño)

Carril C. Módulo nuevo `isr_flujo.py` (puro) + `isr_flujo_datos.py` (SQL). **No toca** `iva_flujo`, `isr.py` (coeficiente de
utilidad, Art. 14) ni `deducciones.py`; el motor del IVA se reutiliza solo como referencia de diseño.

## Qué calcula

El **flujo del ejercicio por mes y acumulado**: ingresos cobrados, deducciones pagadas, nómina deducible, retenciones de ISR a
favor y a cargo, y la **utilidad fiscal estimada** (ingresos − deducciones). No calcula todavía el pago provisional (ver F7.3).

| Bloque | Regla |
|---|---|
| **Ingresos acumulables** | Facturas de contado (PUE) en su fecha de emisión + cobros de PPD con REP, proporcionales a lo cobrado (`base × pagado / total`, a pesos con el tipo de cambio del pago). Base = subtotal − descuento. Anticipo SAT cuenta al cobro; su aplicación (Egreso forma 30) resta, como en IVA. El IVA no es ingreso |
| **Devoluciones, descuentos y bonificaciones emitidos** | Egresos emitidos por la empresa: restan de los ingresos (se muestran como renglón propio) |
| **Deducciones** | Compras y gastos recibidos de contado en su fecha + pagos de PPD con REP (mismo cálculo proporcional). Restan las notas de crédito recibidas |
| **No deducible automático** | Efectivo mayor a $2,000 (LISR 27-III); CFDI de uso S01/CP01/CN01; cancelados. Se listan con su motivo |
| **Inversiones** | Usos I01–I08: se identifican y se muestran aparte; **no** suman a la deducción del mes (se deducen por depreciación, fuera de F7) |
| **Nómina** | Se toma de `cfdi_nominas` y `cfdi_nomina_conceptos` (tipo N emitidos por la empresa), por `fecha_pago`. Gravado: 100 % deducible. Exento: `pct_nomina_exenta` (LISR 28-XXX). **Sin PTU (TipoPercepcion 003) ni viáticos (050)** en la base. Los totales de percepciones salen de los renglones, no del encabezado |
| **ISR retenido a favor** | `isr_retenido` de los CFDI emitidos cobrados (proporcional en PPD) |
| **ISR retenido a cargo** | Lo retenido a trabajadores (`total_impuestos_retenidos` de la nómina) y a proveedores (`isr_retenido` de los recibidos pagados) |

La utilidad fiscal estimada y los avisos usan `Decimal` y medio-hacia-arriba; ninguna cifra pasa por `float` hasta el JSON.

## Porcentaje de la nómina exenta

LISR 28-XXX limita la deducción de las prestaciones exentas al 47 % (53 % si la empresa acredita que las prestaciones exentas
no disminuyeron respecto al ejercicio anterior). El porcentaje es **configurable por empresa y ejercicio** (`isr_config_flujo`,
migración 053), con **47 % por defecto** (el caso conservador). El contador lo cambia con una acción auditada.

## Interruptor «no considerar ISR»

Decisión del contador por CFDI y lado (`ingreso` o `deduccion`), guardada en `isr_ajustes` (migración 052) y auditada en la misma
transacción (usuario, fecha y motivo obligatorio), igual que los ajustes de IVA. El CFDI sale de las sumas y aparece como
«no considerado» con motivo `manual`. Es independiente del interruptor del IVA.

## Aplicabilidad por régimen (D2)

El régimen sale de `empresas.regimen_fiscal` (texto libre; se lee el código SAT de tres dígitos si lo trae).

| Régimen (c_RegimenFiscal) | Módulo |
|---|---|
| 601 General de Ley Personas Morales | ISR provisional por **coeficiente de utilidad** (existente, Art. 14). El flujo se muestra solo como referencia: la persona moral acumula al devengo |
| 612 PF con actividades empresariales y profesionales, 606 Arrendamiento | **ISR base flujo** (este módulo) |
| 626 RESICO, 621 Incorporación Fiscal, 625 plataformas, 605 sueldos, otros | **No cubiertos por F7**: el módulo avisa «régimen no soportado» y no calcula |

Un régimen vacío o desconocido muestra el aviso y deja ver el flujo sin conclusiones de pago.

## Entregas

| Entrega | Contenido |
|---|---|
| **F7.1** | Motor puro, carga SQL, migraciones 052 (ajustes) y 053 (porcentaje), endpoints de resumen y ajustes con auditoría, E2E |
| **F7.2** | Pantalla ISR base flujo (dos pestañas: ingresos y deducciones) y exportación a Excel |
| **F7.3** | Pago provisional del 612 (Art. 106) con las tarifas del Anexo 8 de la RMF 2026 (`docs/referencias/anexo-8-rmf-2026-tarifas.*`, verificadas contra el PDF oficial); migración 057 (PTU pagada y pérdidas pendientes); `GET …/isr-flujo/{periodo}/pago-provisional`. 601 remite al cálculo por coeficiente existente; 606 (Art. 116) no se calcula; ejercicios sin tarifa cargada tampoco |

## Endpoints (F7.1)

- `GET /api/v1/empresas/{id}/isr-flujo/{periodo}` — mes y acumulado del ejercicio hasta ese mes, con avisos.
- `GET /api/v1/empresas/{id}/isr-flujo/{periodo}/detalle?lado=&bloque=` — los CFDI que componen cada cifra.
- `GET/PUT /api/v1/empresas/{id}/isr-flujo/config/{ejercicio}` — porcentaje de nómina exenta.
- `GET/PUT/DELETE …/isr-flujo/ajustes` — no considerar ISR (con motivo).

## Decisiones

| ID | Decisión | Alternativa | Estado |
|---|---|---|---|
| D-F7-1 | Módulo separado de `iva_flujo`, mismo patrón (eventos → resumen) | Extender `iva_flujo` | Decidida (lo pidió el plan maestro) |
| D-F7-2 | 47 % por defecto en la nómina exenta | 53 % | Decidida: el 53 % exige acreditar la no disminución |
| D-F7-3 | Las inversiones se identifican y no deducen | Depreciar en F7 | Decidida: fuera de alcance |
| D-F7-4 | El pago provisional espera tarifas verificadas | Cargar tarifas de memoria | Decidida |
| D-F7-5 | Régimen no soportado ⇒ aviso, sin cálculo de pago | Calcular con el régimen general | Decidida |

## Pago provisional (F7.3)

`utilidad_k = máx(0, ingresos acumulados − deducciones acumuladas − PTU pagada − pérdidas pendientes)`; `causado_k` = cuota fija +
(utilidad − límite inferior) × % de la tarifa acumulada del mes *k*; `pago_k = máx(0, causado_k − Σ pagos anteriores − ISR retenido a
favor del mes k)`. Los pagos anteriores restan ya netos de su retención (igual que `isr.py`). Si no se conoce lo realmente enterado
se estima con la misma fórmula y se avisa (`meses_con_pago_estimado`); M5 podrá aportar los pagos reales. Se muestran el renglón de la
tarifa, la fuente y la fecha de consulta. **Fuera de alcance:** Art. 116 (606), estímulos, deducción opcional del 35 %, subsidio.
