# M5 — Comparativo contra lo declarado

Carril C. Depende de F5 (IVA por flujo) y F7.1 (ISR por flujo). No usa datos del SAT.

## Qué resuelve
El contador captura lo que **realmente declaró y pagó** en cada periodo (IVA e ISR) y el sistema lo compara con lo que
calculan los motores de flujo, para detectar diferencias antes de que las encuentre el SAT.

## Datos (migración 056, tabla `declaraciones`)
Historial por `(empresa, periodo, impuesto)`: `secuencia` 1 es la normal y 2, 3… las complementarias; la vigente es la última. Una complementaria se **agrega** (no pisa); la normal solo se corrige mientras no haya complementarias (si no, 409); no hay complementaria sin normal. Borrar quita la vigente.

| Campo | IVA | ISR |
|---|---|---|
| `ingresos` | — | ingresos acumulables declarados del mes |
| `deducciones` | — | deducciones autorizadas declaradas del mes |
| `impuesto_trasladado` | IVA trasladado cobrado | — |
| `impuesto_acreditable` | IVA acreditable | — |
| `retenciones` | retenciones de IVA a favor | ISR retenido a favor |
| `retenciones_a_terceros` | IVA retenido a terceros por enterar (`retenciones_a_enterar`) | ISR retenido por enterar (`retenciones_a_cargo.total`) |
| `saldo_a_favor_aplicado` | saldo a favor de periodos anteriores que se acreditó; resta de lo calculado a cargo | — |
| `impuesto_a_cargo` | resultado: a cargo (+) o a favor (−) | pago provisional (+) / a favor (−) |
| `monto_pagado` | pagado con línea de captura | pagado |
| `fecha_presentacion`, `numero_operacion`, `tipo` (normal/complementaria), `notas` | | |

Todos los importes son opcionales: solo se compara lo capturado. Solo `impuesto_a_cargo` admite signo; los demás son ≥ 0 (API y CHECK).

## Comparación (módulo puro `declaraciones.py`)
- Calculado: IVA = `iva_flujo.resumen` (trasladado, acreditable ajustado, retenciones a favor, resultado `iva_por_pagar`);
  ISR = `isr_flujo.resumen` del mes (ingresos, deducciones, retenciones a favor). El **pago provisional del ISR no se
  calcula** (F7.3 espera el Anexo 8): ese renglón se muestra solo como declarado.
- Lo calculado se redondea a peso (medio hacia arriba) antes de comparar. Diferencia = declarado − calculado, `Decimal`.
- Estado por renglón: `cuadra` si |dif| ≤ $1.00 (las declaraciones van en pesos enteros), `diferencia` si no,
  `sin_captura` si no hay declarado, `sin_calculo` si no hay calculado.
- Estado global: `sin_comparar` si no se pudo comparar ningún renglón (nunca «cuadra» por no comparar nada).
- Estado global del impuesto: `sin_declaracion`, `cuadra` o `con_diferencias`; además pendiente de pago = `impuesto_a_cargo` de la vigente menos la suma de `monto_pagado` de **toda la cadena** (≤ $1.00 = 0).

## API
- `GET  /empresas/{id}/declaraciones/{periodo}` → comparativo de IVA e ISR del periodo (`?factor=` prorrateo, como IVA).
- `PUT  /empresas/{id}/declaraciones/{periodo}/{impuesto}` → captura o reemplaza (auditado `declaracion_guardada`).
- `DELETE /empresas/{id}/declaraciones/{periodo}/{impuesto}` → borra (auditado `declaracion_eliminada`).
- `GET  /empresas/{id}/declaraciones?ejercicio=YYYY` → estado de los 12 meses (solo capturas, sin recalcular).

## Fuera de alcance
Leer el acuse PDF/XML de la declaración, comparar contra el SAT y calcular el pago provisional.

## UI (M5.2)
Debe aclarar que en ISR las cifras son **del mes** (no acumuladas) y mostrar el historial (normal y complementarias).
