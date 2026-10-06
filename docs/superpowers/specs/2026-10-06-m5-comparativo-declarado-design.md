# M5 — Comparativo contra lo declarado

Carril C. Depende de F5 (IVA por flujo) y F7.1 (ISR por flujo). No usa datos del SAT.

## Qué resuelve
El contador captura lo que **realmente declaró y pagó** en cada periodo (IVA e ISR) y el sistema lo compara con lo que
calculan los motores de flujo, para detectar diferencias antes de que las encuentre el SAT.

## Datos (migración 056, tabla `declaraciones`)
Una declaración vigente por `(empresa, periodo, impuesto)`; una complementaria la reemplaza (se audita el cambio).

| Campo | IVA | ISR |
|---|---|---|
| `ingresos` | — | ingresos acumulables declarados del mes |
| `deducciones` | — | deducciones autorizadas declaradas del mes |
| `impuesto_trasladado` | IVA trasladado cobrado | — |
| `impuesto_acreditable` | IVA acreditable | — |
| `retenciones` | retenciones de IVA a favor | ISR retenido a favor |
| `impuesto_a_cargo` | resultado: a cargo (+) o a favor (−) | pago provisional (+) / a favor (−) |
| `monto_pagado` | pagado con línea de captura | pagado |
| `fecha_presentacion`, `numero_operacion`, `tipo` (normal/complementaria), `notas` | | |

Todos los importes son opcionales: solo se compara lo capturado.

## Comparación (módulo puro `declaraciones.py`)
- Calculado: IVA = `iva_flujo.resumen` (trasladado, acreditable ajustado, retenciones a favor, resultado `iva_por_pagar`);
  ISR = `isr_flujo.resumen` del mes (ingresos, deducciones, retenciones a favor). El **pago provisional del ISR no se
  calcula** (F7.3 espera el Anexo 8): ese renglón se muestra solo como declarado.
- Diferencia = declarado − calculado, `Decimal`, medio hacia arriba a centavos.
- Estado por renglón: `cuadra` si |dif| ≤ $1.00 (las declaraciones van en pesos enteros), `diferencia` si no,
  `sin_captura` si no hay declarado, `sin_calculo` si no hay calculado.
- Estado global del impuesto: `sin_declaracion`, `cuadra` o `con_diferencias`; además `pendiente_de_pago` si
  `impuesto_a_cargo > 0` y `monto_pagado` es menor por más de $1.00.

## API
- `GET  /empresas/{id}/declaraciones/{periodo}` → comparativo de IVA e ISR del periodo (`?factor=` prorrateo, como IVA).
- `PUT  /empresas/{id}/declaraciones/{periodo}/{impuesto}` → captura o reemplaza (auditado `declaracion_guardada`).
- `DELETE /empresas/{id}/declaraciones/{periodo}/{impuesto}` → borra (auditado `declaracion_eliminada`).
- `GET  /empresas/{id}/declaraciones?ejercicio=YYYY` → estado de los 12 meses (solo capturas, sin recalcular).

## Fuera de alcance
Leer el acuse PDF/XML de la declaración, comparar contra el SAT y calcular el pago provisional.
