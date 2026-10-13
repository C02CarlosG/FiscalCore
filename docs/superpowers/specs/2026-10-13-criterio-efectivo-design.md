# Criterio de efectivo por empresa

Fecha: 2026-10-13. Estado: implementada (rama `feat/criterio-efectivo`). Origen: auditoría de ezaudita
(`comparativo/ezaudita/`, memoria `auditoria-ezaudita-reglas-iva-isr`).

## Objetivo

Que cada empresa elija cómo se trata el pago en efectivo en el IVA acreditable y en las
deducciones de ISR.

## Contexto

- FiscalCore excluye el efectivo (forma de pago `01`) solo si **supera $2,000**
  (LIVA 5-III, LISR 27-III). Es la regla legal vigente y es el valor por defecto.
- ezaudita excluye **todo** pago en efectivo, sin importar el monto. Se verificó en octubre
  de 2026 con COPLASUR: 9 compras en efectivo, todas menores a $2,000 (la mayor, $1,855),
  quedaron fuera; IVA acreditable $510.17 contra ~$2,082.83 con la regla legal.
- El selector de nómina exenta 53 % / 47 % **ya existe** (migración 053, router
  `isr_flujo.py`, `IsrFlujoPantalla.tsx`). Una versión previa de esta spec lo daba por
  faltante; se corrigió al leer la pantalla. No forma parte de este trabajo.

## Alcance

Entra:
1. Criterio por empresa: `legal` (por defecto) o `estricto`.
2. Aplicación en IVA base flujo, ISR base flujo, DIOT, Inicio, Declaraciones y reportes (todos
   consumen `cargar_eventos`, así que heredan el criterio).
3. Insignia visible del criterio activo en IVA flujo e ISR flujo.

No entra:
- Papel de trabajo del cierre (`papel_trabajo.py`): calcula con SQL propio por fecha de emisión, no con
  los motores de flujo, y por eso no sigue este criterio (tampoco coincide hoy con IVA/ISR flujo).
  Alinearlo es trabajo aparte.
- Cédula de IVA antigua (`iva.py`, `deducciones.py`) y tarjeta de efectivo de Validaciones:
  se parametrizan solo si el cambio es de bajo riesgo; si no, siguen con la regla legal y
  la pantalla lo indica.
- Cambios al resto de reglas de exclusión (uso S01/CP01/CN01, REP 1.0).

## Diseño

### Datos
Migración `072_criterio_efectivo.sql`, idempotente:
`ALTER TABLE empresas ADD COLUMN IF NOT EXISTS criterio_efectivo TEXT NOT NULL DEFAULT 'legal'`
con `CHECK (criterio_efectivo IN ('legal','estricto'))` (agregado de forma idempotente).
Se usa 072 porque 071 está reservada en la rama `ui-menu-avatar`. Se registra en `db.py`.

### Un solo punto de verdad
Función pura `umbral_efectivo(criterio) -> Decimal`: `legal` → `2000`, `estricto` → `0`.
Valor desconocido → error, no se asume legal en silencio. Con umbral `0`, la condición
existente "efectivo y monto > umbral" excluye cualquier pago en efectivo mayor a cero; no
hay ramas nuevas en el cálculo.

### Motores
`iva_flujo.py` e `isr_flujo.py` reciben `umbral_efectivo` (por defecto `UMBRAL_EFECTIVO`)
en `eventos_de_documento`, `eventos_de_pago`, `motivo_exclusion`,
`_no_acreditable_por_si_mismo` / `_no_deducible_por_si_mismo` y `_marcas_de_deduccion`.
Los llamadores actuales no cambian de comportamiento. La marca informativa
`efectivo_hasta_umbral` solo se emite si el umbral es mayor que cero.

### Loaders
`iva_flujo_datos.py` e `isr_flujo_datos.py` leen `empresas.criterio_efectivo`, calculan el
umbral y lo pasan a los motores. El criterio se lee una vez por solicitud.

### API
- `GET`/`PUT /api/v1/empresas/{id}/criterio-efectivo` (router propio `criterio_efectivo.py`);
  el `PUT` exige rol administrador de la empresa (o de la plataforma), valida el valor y
  escribe en `auditoria` (valor anterior y nuevo) en la misma transacción que el cambio.
- Las respuestas de `iva-flujo` e `isr-flujo` incluyen `criterio_efectivo`.
- Se documenta en `docs/openapi.yaml` (lo exige `test_openapi_sync.py`).

### Pantalla
- Selector "Criterio de efectivo" en IVA flujo e ISR flujo, junto a los controles del periodo (en `main` no hay pantalla de configuración de empresa), con texto explicativo de cada
  opción (legal: efectivo mayor a $2,000; estricto: todo efectivo).
- IVA flujo e ISR flujo: insignia "Criterio: Estricto" cuando aplica.
- Los CFDI excluidos siguen apareciendo en "No considerados" con el motivo `efectivo`.

## Criterios de aceptación

1. Con `legal`, todas las pruebas actuales pasan sin cambios.
2. Con `estricto`, una compra en efectivo de $1,000 con IVA $137.93 no suma al acreditable
   ni a deducciones y aparece en "No considerados" con motivo `efectivo`; con `legal` sí suma.
3. Caso COPLASUR octubre 2026 (datos sembrados): las 9 compras en efectivo suman IVA
   $1,572.66; `estricto` lo excluye y `legal` lo incluye, y la diferencia entre ambos
   criterios es exactamente esa cifra.
4. Un pago en efectivo de una factura a crédito (REP) sigue la misma regla.
5. Una nota de crédito recibida de un CFDI excluido hereda el motivo
   `original_no_acreditable`, bajo ambos criterios.
6. Cambiar el criterio queda en `auditoria` con usuario, fecha, valor anterior y nuevo; un
   usuario sin rol de administrador recibe 403.
7. La retención de IVA de una compra en efectivo se sigue enterando (LIVA 1-A) bajo ambos
   criterios.

## Verificación

`python -m pytest` completo (unitarias y `-m db`) y `npm test` en verde; agente
`dominio-fiscal` sobre el cambio de cálculo; agente `migration-validator` sobre la 072.
