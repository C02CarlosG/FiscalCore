# F4 — Inicio — Diseño

Fecha: 2026-10-04. Carril C (cálculos fiscales). Depende de F1 (detalle fiscal, integrada).
Plan maestro: `2026-10-01-paridad-y-mejoras-roadmap.md`. Comportamiento de referencia: `2026-10-01-referencia-plataforma.md`.

## Objetivo

Que al entrar a una empresa el contador vea, sin abrir ninguna otra pantalla, **cuánto facturó y cuánto gastó** en el periodo y en el ejercicio, cómo evolucionó en los últimos 12 meses y **cómo va el IVA del año mes por mes**. Es la pantalla de entrada: financiera primero, riesgos después.

## Alcance

**Entra**
- Dos endpoints de lectura: `GET /empresas/{id}/inicio/resumen` e `…/inicio/iva-anual`.
- En la pantalla `/empresas/{id}/dashboard` (es el Inicio; la ruta y la etiqueta del menú no cambian en esta entrega): ingresos y gastos netos del periodo y del ejercicio; gráfica de barras de 12 meses; tabla de ingresos por mes; tabla anual de IVA con tres pestañas. Los bloques de riesgos y score que ya existen se conservan debajo.

**No entra**
- IVA por tasa (16 %, 8 %, 0 %, exento), retenciones de IVA, interruptor "no considerar IVA" y periodo reasignado: F5.
- Ingresos acumulables y deducciones de ISR: F7.
- Cambiar la etiqueta del menú a "Inicio": `Sidebar.tsx` es archivo compartido y el cambio no urge.
- Biblioteca de gráficas: la gráfica es SVG propio (sin dependencias nuevas).

## Reglas fiscales y de cálculo

### Ingresos netos (por fecha de emisión)

El Inicio muestra lo **facturado** (devengado), no lo cobrado: la cifra de referencia de ingresos netos del periodo (21,407,798.40) es distinta de la base de IVA cobrada (19,939,765.52), así que son dos conceptos. Lo cobrado vive en F5 y F7.

Ingresos del mes = Σ (subtotal − descuento) de los CFDI **emitidos por la empresa** de tipo Ingreso (I), menos Σ (subtotal − descuento) de sus **notas de crédito** (Egreso, E), con fecha de emisión en el mes.

- Solo `estado = 'vigente'`: un cancelado no produce efectos.
- Se excluyen los anticipos SAT (`es_anticipo_sat`), igual que la cédula de IVA: el anticipo no se cuenta dos veces cuando llega la factura que lo aplica.
- Sin IVA: la base es subtotal menos descuento.
- Moneda extranjera: importe × tipo de cambio del comprobante (`tipo_cambio` vacío o 0 = 1), según la regla común del plan maestro.
- Los CFDI de traslado (T), nómina (N) y pago (P) no son ingreso.

### Gastos netos

Gastos del mes = Σ (subtotal − descuento) de los CFDI **recibidos** de tipo I, menos las notas de crédito recibidas (E), con las mismas exclusiones y conversión.

La **nómina** (CFDI tipo N emitidos por la empresa) se reporta aparte en `gastos.nomina` y **no** se suma a `gastos.neto`. Ver decisión D-F4-1.

### Periodo y ejercicio

- **Periodo**: el mes elegido (`YYYY-MM`).
- **Acumulado**: enero del ejercicio del periodo hasta el mes elegido, inclusive. El ejercicio es el año calendario.
- **Serie de 12 meses**: los 12 meses que terminan en el periodo elegido (puede cruzar de ejercicio); los meses sin CFDI salen con ceros, no se omiten.

### IVA anual (por flujo de efectivo)

Para cada mes del ejercicio se reutilizan **tal cual** `iva.iva_trasladado` e `iva.iva_acreditable` (LIVA 1-B y 5), de modo que el Inicio nunca contradice a la cédula de IVA del mismo mes. Tres pestañas:

1. **Trasladado cobrado**: PUE, PPD cobrado (con el IVA proporcional al pago), notas de crédito y total.
2. **Acreditable pagado**: PUE, PPD pagado, notas de crédito, efectivo mayor a $2,000 excluido y bruto.
3. **Resultado**: trasladado − acreditable − IVA retenido = IVA a cargo o saldo a favor del mes, y su acumulado.

Hasta que F5 incorpore las retenciones, el IVA retenido es 0 y el factor de prorrateo es 1 (igual que la cédula); la pantalla lo avisa con una nota. Los meses posteriores al periodo elegido salen vacíos.

## Contrato de API

Ambos requieren acceso a la empresa (403 si no) y no escriben en `auditoria` (son lectura de pantalla, igual que el dashboard). Los importes viajan como número con dos decimales; sin dato, `0` (no hay "sin dato": un mes sin CFDI sí vale cero).

### `GET /api/v1/empresas/{empresa_id}/inicio/resumen?periodo=YYYY-MM`

```json
{
  "empresa_id": "…", "periodo": "2026-09", "ejercicio": 2026,
  "ingresos": {
    "periodo":   {"facturado": 0, "notas_credito": 0, "neto": 0, "cfdi": 0},
    "acumulado": {"facturado": 0, "notas_credito": 0, "neto": 0, "cfdi": 0}
  },
  "gastos": {
    "periodo":   {"facturado": 0, "notas_credito": 0, "neto": 0, "cfdi": 0, "nomina": 0},
    "acumulado": {"facturado": 0, "notas_credito": 0, "neto": 0, "cfdi": 0, "nomina": 0}
  },
  "meses": [
    {"periodo": "2025-10", "ingresos": {"facturado": 0, "notas_credito": 0, "neto": 0, "cfdi": 0}, "gastos": {"neto": 0}}
  ]
}
```
`meses` trae siempre 12 elementos, del más antiguo al más reciente. 422 si `periodo` no es `YYYY-MM` válido (año 2000–2099, mes 01–12).

### `GET /api/v1/empresas/{empresa_id}/inicio/iva-anual?ejercicio=2026&periodo=2026-09`

```json
{
  "empresa_id": "…", "ejercicio": 2026, "factor_prorrateo": 1, "iva_retenido_incluido": false,
  "meses": [
    {"periodo": "2026-01",
     "trasladado": {"pue": 0, "ppd": 0, "notas_credito": 0, "total": 0},
     "acreditable": {"pue": 0, "ppd": 0, "notas_credito": 0, "excluido_efectivo": 0, "bruto": 0, "ajustado": 0},
     "resultado": {"iva_retenido": 0, "iva_por_pagar": 0, "saldo_a_cargo": 0, "saldo_a_favor": 0}}
  ],
  "totales": {"trasladado": 0, "acreditable": 0, "iva_retenido": 0, "iva_por_pagar": 0}
}
```
`meses` trae los 12 meses del ejercicio; los posteriores a `periodo` (si se manda) llevan ceros. `ejercicio` debe estar entre 2000 y 2099.

## Pantalla

1. **Indicadores** (4 tarjetas): Ingresos netos del periodo, Ingresos netos del ejercicio, Gastos netos del periodo, Gastos netos del ejercicio. Debajo de gastos, la nómina del periodo como dato secundario.
2. **Gráfica de 12 meses**: barras agrupadas de ingresos y gastos netos por mes, con el mes elegido resaltado, etiquetas de mes abreviadas, leyenda y una tabla alternativa accesible (la gráfica es decorativa para lector de pantalla; los datos están en la tabla de abajo).
3. **Ingresos por mes**: tabla de los 12 meses con facturado, notas de crédito, neto y número de CFDI, y renglón de total.
4. **IVA del ejercicio**: pestañas Trasladado cobrado / Acreditable pagado / Resultado; 12 renglones y total; nota sobre retenciones y prorrateo.
5. Estados de carga, error con reintento y vacío (empresa sin CFDI: ceros y un aviso que remite a Ingesta y a Conexión SAT).
6. El periodo es el global (`usePeriodoGlobal`); cambiarlo recalcula todo.

## Decisiones

| # | Decisión | Valor por defecto | Cómo se cambia |
|---|---|---|---|
| D-F4-1 | La nómina no se suma a "Gastos netos"; se muestra aparte | Sin nómina en gastos | Al cuadrar con la referencia (12,803,855.07), si ella incluye nómina, se suma en el módulo `inicio.py` (un solo lugar) |
| D-F4-2 | Las tres pestañas del IVA anual son Trasladado / Acreditable / Resultado | Inferidas del plan maestro ("tres pestañas") | Ajustar los nombres y columnas al ver la pantalla de referencia; el contrato ya separa los tres bloques |
| D-F4-3 | Ingresos y gastos son devengados (fecha de emisión) | Devengado | Un interruptor "flujo" se evalúa en F5/F7, que ya calculan cobrado y pagado |
| D-F4-4 | Los anticipos SAT se excluyen de ingresos y gastos | Excluidos (igual que el IVA) | Se revisa con F5, que define el tratamiento completo de anticipos por tasa |

## Cálculo y rendimiento

- Ingresos y gastos se agregan **en SQL** (`GROUP BY` mes, dirección y tipo, sobre un solo recorrido del ejercicio más los 12 meses de la serie), no en Python: una empresa puede tener cientos de miles de CFDI. Las reglas de inclusión (vigente, sin anticipo, dirección, tipo, conversión) quedan en esa consulta y se prueban contra Postgres; la composición (neto, acumulado, ventana de 12 meses) está en `backend/inicio.py`, funciones puras sin base de datos.
- El IVA anual carga los CFDI del ejercicio y los PPD pendientes, y llama a las funciones de `iva.py` mes por mes. Con 200,000 CFDI son 12 pasadas en memoria; se mide en la prueba de volumen y, si pasa de 3 s, se agrega pre-agregación por mes en F5 (que ya reescribe este cálculo por tasa).
- Sin migraciones: los índices `idx_cfdi_emp_emisor_fecha` e `idx_cfdi_emp_receptor_fecha` (migración 030) cubren las consultas.

## Criterios de aceptación

Con la empresa de prueba de la E2E (CFDI sembrados, todos en MXN salvo uno en USD a 20):

1. Ingresos netos del periodo = Σ(I emitidos vigentes) − Σ(E emitidos vigentes), sin anticipos, sin IVA, con USD convertido; un CFDI cancelado o un anticipo no cambia la cifra.
2. El acumulado de septiembre es igual a la suma de ene–sep de la serie; el de enero es igual al del periodo.
3. `meses` siempre tiene 12 elementos consecutivos terminando en el periodo, también al cruzar de año.
4. Para cada mes, `trasladado.total` y `acreditable.bruto` del IVA anual son **idénticos** a los de `GET /cedula-iva/{periodo}` del mismo mes.
5. Resultado del mes = trasladado − acreditable ajustado − retenido, con saldo a cargo y a favor exclusivos.
6. Un usuario sin acceso a la empresa recibe 403; un periodo mal formado, 422.
7. La pantalla muestra los importes con formato de moneda, los meses vacíos con ceros y la nota de retenciones; recargar con otro periodo en la URL reproduce la misma vista.
8. **Cuadre contra la referencia** (cifras de control del plan maestro): requiere los CFDI reales de COPLASUR en local; se hace en el cierre de F0/F1 (carril B) y cualquier diferencia se explica en el PR, sin ajustar el cálculo sin fundamento legal.
