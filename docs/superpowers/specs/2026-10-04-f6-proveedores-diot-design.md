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

**`proveedores`** (051): un renglón por tercero de la empresa. Su `id` es la llave (el PATCH va por `id`, no por RFC).

| Columna | Notas |
|---|---|
| `empresa_id`, `rfc` | RFC en mayúsculas (CHECK). **Único por empresa salvo el de extranjeros**: varios comparten `XEXX010101000`; `XAXX010101000` no se admite |
| `nombre`, `nombre_editado` | razón social; la alimentación solo la actualiza si `nombre_editado = false` (`PATCH nombre_editado=false` devuelve el proveedor a la alimentación automática) |
| `tipo_tercero` | `04` nacional, `05` extranjero, `15` global (solo por captura manual con un RFC propio). CHECK en la base |
| `tipo_operacion` | `02`, `03`, `06`, `07`, `08`, `85`, `87` (la `87` solo con tercero `15`). Por defecto `85`. CHECK en la base |
| `pais` (CHAR(3), ISO 3166-1 alfa-3), `jurisdiccion_detalle`, `id_fiscal`, `efectos_fiscales` | extranjeros. `id_fiscal` es único por empresa entre extranjeros (`05`) |
| `origen` | `cfdi` (alimentado) o `manual` |

**Catálogos y reglas cruzadas** (`backend/diot_catalogos.py`): el `05` exige `id_fiscal` y `pais`; el `04` exige un RFC válido y no
genérico; la `87` solo aplica al `15`. **Las claves de ambos catálogos deben confirmarse contra el instructivo oficial del SAT**:
el revisor fiscal las tomó de memoria porque el entorno no puede consultarlo. Si difieren se corrigen en `diot_catalogos.py` y en los
CHECK de la 051 (misma lista).

**`diot_terceros_periodo`** (054, F6.2): tipo de tercero y de operación de un proveedor **en un periodo** (única por empresa, periodo
y proveedor; si falta aplica el default del catálogo). **`diot_operaciones_cfdi`** (054): tipo de operación de **un CFDI** en un
periodo, que manda sobre lo anterior; así un mismo tercero se declara con **varias operaciones en el mismo periodo** (sale en un
renglón por operación). *Desviación del plan de la revisión*: la llave `(empresa, periodo, proveedor, tipo_operacion)` no
alcanza para repartir los importes entre operaciones, por eso la asignación es por CFDI.

Todo cambio del catálogo o del periodo queda en `auditoria` en la misma transacción.

## Alimentación del catálogo

`proveedores.sincronizar` (la llama el `GET`, **que por lo tanto escribe**) toma los emisores de los CFDI recibidos vigentes con
`UPPER(TRIM(rfc))`:

- RFC nacional válido → alta como `04`, operación `85`; si ya existe y el contador no editó el nombre, `DO UPDATE` del nombre con el del CFDI más reciente.
- `XEXX010101000` → alta como `05`, marcada **pendiente** (falta ID fiscal y país); una por nombre de emisor, porque son terceros distintos.
- `XAXX010101000` (público en general) → **no es un proveedor**: no entra a la alimentación (cuenta en `omitidos`) y el alta manual se rechaza con 422.
- RFC con formato inválido → no entra y se cuenta en `omitidos`.
- Si agrega algo deja el evento `proveedores_sincronizados` en la auditoría.

Es idempotente y no depende del worker.

## DIOT por flujo (F6.2)

Entrada: los **eventos acreditables** del periodo que ya produce el motor (`iva_flujo_datos.cargar_eventos`), con los mismos
ajustes del contador. Por tercero (`contraparte_rfc`):

- **Valor de actos pagados** por tasa (16 %, 8 %, 0 %, exento, otras, no objeto) = bases de los eventos considerados
  (contado y crédito; las notas de crédito recibidas restan).
- **IVA acreditable** por tasa = el IVA de esos eventos, multiplicado por el factor de prorrateo del periodo.
- **IVA no acreditable**: lo que el motor deja fuera, separado por motivo (efectivo mayor a $2,000, uso sin efectos fiscales)
  más el complemento del prorrateo.
- **Devoluciones, descuentos y bonificaciones**: el valor y el IVA de las notas de crédito recibidas van en **su propia columna**
  (no solo restados), porque la DIOT los declara aparte.
- **Retenciones de IVA** que la empresa le hizo al tercero (`retencion`).
- Los CFDI reasignados a otro periodo o excluidos a mano siguen la regla del motor: no suman en este periodo.

La suma de IVA acreditable de todos los terceros **es** el acreditable de la cédula de IVA del mismo periodo (prueba de
cuadre obligatoria; `cuadre_con_iva` en la respuesta). El comparativo de la cédula contra «IVA devengado (DIOT)» **se
conserva** (lee `cfdi.iva_trasladado`): comparar la DIOT por flujo contra el acreditable del mismo motor siempre daría cero y
perdería su función de control. `GET /diot/{periodo}` (devengado, tipo de operación fijo `03`) queda **obsoleto** y se retira
cuando el frontend migre a `/diot-flujo`.

**Trabajo de F6.2 dentro del motor `iva_flujo`** (no se calcula por fuera de él): la columna «no objeto», el IVA no acreditable
por motivo y el 8 % por región (norte o sur) los tiene que producir el motor, por contraparte. La región no está en los datos hoy:
se resuelve en F6.2 (p. ej. por el domicilio del proveedor o una captura por proveedor) o se quita de la DIOT.

Regiones (zona norte/sur, importaciones) de la plataforma de referencia: solo se muestran cuando el motor distinga tasa
fronteriza (8 %); importaciones quedan fuera de F6 (no hay pedimentos).

## Reglas

- Dinero en `Decimal`, medio hacia arriba, igual que el motor. Nunca `float` en el cálculo.
- Un tercero sin RFC válido o sin tipo de tercero/operación aparece en la DIOT con una advertencia (no se omite).
- Fundamento: la obligación de informar las operaciones con terceros es la de LIVA 32-VIII.
- Endpoints nuevos documentados en `docs/openapi.yaml`; acceso con `validar_acceso_empresa`.

## Decisiones

| ID | Decisión | Alternativa | Estado |
|---|---|---|---|
| D-F6-1 | La DIOT se calcula **desde los eventos del motor**, no con SQL aparte | Reimplementar en SQL | Decidida (evita una segunda cifra de IVA) |
| D-F6-2 | Tipo de tercero/operación por periodo con default en el catálogo | Un solo valor por tercero | Decidida (el SAT los pide por periodo) |
| D-F6-3 | El archivo de carga espera el layout oficial | Construirlo de blogs | Decidida: no se inventa el layout |
| D-F6-5 | El RFC genérico no es único: los extranjeros se distinguen por `id` y por ID fiscal | RFC único por empresa | Decidida (si no, solo cabría un extranjero) |
| D-F6-4 | `GET /diot/{periodo}` (devengado) queda obsoleto; el comparativo de la cédula sigue contra el devengado | Que delegue a la DIOT por flujo | Decidida |
| D-F6-6 | Clasificación por periodo (tercero) y por CFDI (operación); el 8 % por región y las importaciones quedan fuera | Una llave con `tipo_operacion` | Decidida |
