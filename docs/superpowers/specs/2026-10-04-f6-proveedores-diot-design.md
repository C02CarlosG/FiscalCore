# F6 — Proveedores y DIOT (diseño)

Carril C. Se apoya en el motor de IVA por flujo (F5): la DIOT es el acreditable del mes visto **por tercero**.

## Alcance y entregas

| Entrega | Contenido | Depende de |
|---|---|---|
| **F6.1** | Catálogo de proveedores de la empresa: se alimenta de los CFDI recibidos y se edita a mano; tipo de tercero y tipo de operación por defecto | Migración 051 |
| **F6.2** | DIOT por flujo: por tercero, tasa, IVA acreditable y no acreditable, retenciones; tipo de tercero/operación editables **por periodo**; pantalla y Excel | F5 en `main`, F6.1 |
| **F6.3** | Archivo de carga (.txt) de la DIOT | **Layout oficial vigente del SAT (ver "Verificación pendiente")** |

## Verificación pendiente (bloquea solo F6.3)

El archivo de carga cambió en 2025: de 24 a 54 campos, `.txt` UTF-8 separado por `|`, con campos obligatorios, opcionales
y vacíos según el tipo de tercero. **No se asume el orden ni el contenido de los 54 campos.** Las fuentes oficiales son el
«Instructivo para el armado del archivo de carga masiva» y el «Manual técnico para la integración de archivos .txt», ambos
en `sat.gob.mx`, que el entorno de desarrollo tiene bloqueado. F6.3 arranca cuando alguien (a) habilite `www.sat.gob.mx` y
`wwwmat.sat.gob.mx` en el acceso de red del entorno o (b) deje el instructivo en `docs/referencias/`. Mientras tanto F6.1 y F6.2
guardan los datos que el archivo pedirá sin fijar su orden.

Los catálogos de **tipo de tercero** y **tipo de operación** tampoco se asumen: se guardan como texto libre validado por
una lista que vive en `backend/diot_catalogos.py` y se confirma contra el instructivo antes de F6.2. El valor fijo `"03"`
que hoy devuelve `GET /diot/{periodo}` es provisional y se retira cuando exista el catálogo confirmado.

## Modelo de datos (migraciones 051 y 052)

**`proveedores`** (051): un renglón por tercero de la empresa.

| Columna | Notas |
|---|---|
| `empresa_id`, `rfc` | único por empresa; el RFC en mayúsculas |
| `nombre` | razón social; la toma del CFDI más reciente si el contador no la edita |
| `tipo_tercero`, `tipo_operacion` | defaults del tercero; el contador los cambia (ver abajo) |
| `pais`, `id_fiscal` | para extranjeros (sin RFC mexicano) |
| `origen` | `cfdi` (alimentado automáticamente) o `manual` |
| `nombre_editado` | `true` si el contador cambió el nombre: la alimentación ya no lo pisa |

**`diot_terceros_periodo`** (052, F6.2): tipo de tercero y de operación **por periodo** (`empresa_id`, `periodo`, `rfc`), con
auditoría. Si no hay renglón, aplica el default de `proveedores`.

Todo cambio del catálogo o del periodo queda en `auditoria` en la misma transacción (como los ajustes de IVA).

## Alimentación del catálogo

`proveedores.sincronizar(empresa_id)` inserta los emisores de los CFDI recibidos vigentes que aún no están (idempotente,
`INSERT … ON CONFLICT DO NOTHING`) y actualiza el nombre de los que no fueron editados. Se llama al consultar la lista y
desde la DIOT; no depende del worker.

## DIOT por flujo (F6.2)

Entrada: los **eventos acreditables** del periodo que ya produce el motor (`iva_flujo_datos.cargar_eventos`), con los mismos
ajustes del contador. Por tercero (`contraparte_rfc`):

- **Valor de actos pagados** por tasa (16 %, 8 %, 0 %, exento, otras, no objeto) = bases de los eventos considerados
  (contado y crédito; las notas de crédito recibidas restan).
- **IVA acreditable** por tasa = el IVA de esos eventos, multiplicado por el factor de prorrateo del periodo.
- **IVA no acreditable**: lo que el motor deja fuera, separado por motivo (efectivo mayor a $2,000, uso sin efectos fiscales)
  más el complemento del prorrateo.
- **Retenciones de IVA** que la empresa le hizo al tercero (`retencion`).
- Los CFDI reasignados a otro periodo o excluidos a mano siguen la regla del motor: no suman en este periodo.

La suma de IVA acreditable de todos los terceros **es** el acreditable de la cédula de IVA del mismo periodo (prueba de
cuadre obligatoria). El comparativo de la cédula contra "IVA devengado (DIOT)" deja de leer `cfdi.iva_trasladado` y usa
esta DIOT.

Regiones (zona norte/sur, importaciones) de la plataforma de referencia: solo se muestran cuando el motor distinga tasa
fronteriza (8 %); importaciones quedan fuera de F6 (no hay pedimentos).

## Reglas

- Dinero en `Decimal`, medio hacia arriba, igual que el motor. Nunca `float` en el cálculo.
- Un tercero sin RFC válido o sin tipo de tercero/operación aparece en la DIOT con una advertencia (no se omite).
- Endpoints nuevos documentados en `docs/openapi.yaml`; acceso con `validar_acceso_empresa`.

## Decisiones

| ID | Decisión | Alternativa | Estado |
|---|---|---|---|
| D-F6-1 | La DIOT se calcula **desde los eventos del motor**, no con SQL aparte | Reimplementar en SQL | Decidida (evita una segunda cifra de IVA) |
| D-F6-2 | Tipo de tercero/operación por periodo con default en el catálogo | Un solo valor por tercero | Decidida (el SAT los pide por periodo) |
| D-F6-3 | El archivo de carga espera el layout oficial | Construirlo de blogs | Decidida: no se inventa el layout |
| D-F6-4 | `GET /diot/{periodo}` (devengado) se conserva hasta F6.2 y luego delega a la DIOT por flujo | Quitarlo ya | Abierta |
