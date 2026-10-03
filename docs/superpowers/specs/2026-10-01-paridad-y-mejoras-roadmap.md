# Plan maestro — paridad funcional con la plataforma de referencia y mejoras

Fecha: 2026-10-01. Estado: borrador para revisión.

## Contexto

Se analizaron 26 capturas de una plataforma fiscal de referencia (ezaudita, empresa de
prueba COPLASUR) y se compararon con FiscalCore recorriendo sus 9 pantallas con
Playwright. FiscalCore cubre hoy cédula de IVA por flujo, emitidos/recibidos/nómina,
conciliación bancaria, riesgos y scoring, y tiene en el backend (sin pantalla) descarga
masiva SAT, DIOT básica, ISR provisional y deducciones. La referencia muestra mucho más
detalle de CFDI e impuestos; casi todas sus pantallas dependen de datos que FiscalCore
no guarda (impuestos por tasa, conceptos, impuestos de cada pago, nómina).

Este documento define **cómo se va a trabajar**: en qué orden, con qué reglas fiscales,
qué entrega cada fase y cómo se verifica. No es un plan de implementación: cada fase
tendrá su propia spec y su propio plan en `docs/superpowers/`.

"Igual" significa paridad **funcional** (mismos datos, cálculos y flujos). Se conserva
el sistema visual propio de FiscalCore; no se copian marca, logotipo ni textos.

## Decisiones tomadas (por defecto; cambiar aquí antes de empezar la fase que afectan)

| # | Decisión | Valor por defecto | Fase que afecta |
|---|---|---|---|
| D1 | Qué significa "lógica contable" | Reglas fiscales de cálculo (IVA, ISR, DIOT, nómina). Contabilidad electrónica (pólizas, catálogo de cuentas, balanza) queda **fuera** de este plan | Todas |
| D2 | ISR | Se agrega "ISR base flujo" como módulo nuevo; el ISR provisional por coeficiente de utilidad (Art. 14 LISR) se conserva. Cuál aplica lo decide el régimen fiscal de la empresa | F7 |
| D3 | Suscripción y cobro | Última fase; no bloquea nada | M7 |
| D4 | Constancia y opinión de cumplimiento | Primero carga manual del PDF con visor; la descarga automática del portal SAT se evalúa aparte por su fragilidad | F8 |
| D5 | Datos históricos | No se vuelve a descargar del SAT: se reprocesa el `xml_raw` ya guardado | F1 |
| D6 | Preferencias de columnas | Se guardan en el servidor por usuario (no en el navegador) | F3 |
| D7 | Descarga automática de XML | Proceso aparte (`worker`) que usa Postgres como cola; sin Redis ni Celery. Una corrida diaria por empresa, más la carga inicial al guardar la e.firma | F2 |
| D8 | Uso desatendido de la e.firma | La descarga automática se activa por empresa con consentimiento explícito de quien guarda la e.firma; se puede pausar en cualquier momento | F2 |

## Forma de trabajo (igual en todas las fases)

1. **Spec de la fase** en `docs/superpowers/specs/AAAA-MM-DD-<fase>-design.md`: qué
   entra, qué no, reglas fiscales con su fundamento, contrato de API, criterios de
   aceptación con cifras.
2. **Plan de la fase** en `docs/superpowers/plans/AAAA-MM-DD-<fase>.md`: tareas con
   prueba primero (TDD), código y comando de verificación.
3. **Rama por fase** desde `main` (`feat/<fase>`), commits Conventional Commit, un PR
   por fase. Ninguna fase empieza sobre una rama con trabajo sin integrar.
4. **Implementación**: cálculo fiscal en módulos puros sin base de datos (como
   `backend/iva.py`), routers delgados, migración SQL idempotente numerada, endpoint
   documentado en `docs/openapi.yaml` (lo exige `test_openapi_sync.py`).
5. **Verificación antes de cerrar la fase** — las cuatro son obligatorias:
   - `python -m pytest` completo en verde (unitarias y `-m db`), `npm test` en verde.
   - Revisión del agente `dominio-fiscal` sobre todo cambio de cálculo, y del agente
     `migration-validator` sobre toda migración.
   - Cuadre contra la referencia: con los CFDI reales de COPLASUR de 2026, las cifras
     de FiscalCore deben coincidir al centavo con las capturas (ver "Cifras de control").
     Toda diferencia se explica por escrito en el PR; no se ajusta el cálculo para
     "hacerlo coincidir" sin fundamento legal.
   - Comparación visual con Playwright de la pantalla nueva contra su captura.
6. **Definición de terminado**: PR aprobado, integrado a `main`, y este documento
   actualizado (fase marcada como hecha, decisiones nuevas anotadas).

### Cifras de control (COPLASUR, septiembre 2026, tomadas de las capturas)

| Concepto | Importe |
|---|---|
| Ingresos netos del periodo | 21,407,798.40 |
| Ingresos netos acumulados del ejercicio | 216,844,592.64 |
| Gastos y compras netas del periodo | 12,803,855.07 |
| IVA trasladado efectivamente cobrado | 3,190,362.48 |
| — facturas de contado (153 CFDI) | 2,275,262.33 |
| — cobro de facturas a crédito (80 pagos) | 915,100.15 |
| Base de IVA 16 % cobrada | 19,939,765.52 |
| IVA acreditable efectivamente pagado | 2,162,403.41 |
| IVA a cargo | 1,027,959.07 |
| Retenciones de IVA | 3,786.75 |
| Ingresos acumulables (ISR flujo) | 19,939,765.52 |
| Deducciones autorizadas sin inversiones | 16,892,941.73 |
| Nómina: gravada / exenta / exenta deducible (47 %) | 2,145,503.54 / 33,948.64 / 15,955.86 |

Las cifras son del 29 de septiembre de 2026, con el mes aún abierto: el 2 de octubre la
plataforma ya mostraba otras para el mismo mes (IVA trasladado cobrado 3,798,239.51).
Sirven para entender el orden de magnitud; **el cuadre real se hace comparando el mismo
día y con los mismos comprobantes descargados**.

Estas cifras son la prueba de aceptación de las fases F4 a F7. Se usan como referencia,
no como verdad absoluta: si FiscalCore difiere, se investiga cuál de los dos tiene razón.

## Fases

Cada fase entrega software que funciona y se prueba por sí solo. El orden responde a
dependencias: nada de lo visible se puede construir sin F1.

### Bloque A — Paridad

| Fase | Entrega | Depende de | Tamaño |
|---|---|---|---|
| **F0 Preparación** | Trabajo pendiente integrado a `main`; línea base de pruebas en verde; CFDI reales de COPLASUR cargados en local | — | Chico |
| **F1 Detalle fiscal del CFDI** | Impuestos por tasa, conceptos, encabezados faltantes, impuestos de cada pago (REP 2.0) y totales de nómina guardados; reproceso de los XML ya almacenados | F0 | Mediano |
| **F2 Descarga automática de XML** | Descarga desatendida de emitidos y recibidos con la e.firma guardada: carga inicial, corrida diaria incremental y detección de cancelaciones; pantallas de e.firma, historial de descargas y estado de la última descarga en el menú | F1 | Grande |
| **F3 Listado unificado de CFDI** | API paginada con filtros (estado, método, tipo, búsqueda) y totales; pestañas por tipo; fila expandible con conceptos; editor de columnas; exportar a Excel; periodo global con mes actual por defecto | F1 | Grande |
| **F4 Inicio** | Ingresos y gastos netos (periodo y acumulado), gráfica de 12 meses (barras/líneas), tabla de ingresos por mes, tabla anual de IVA con sus tres pestañas | F1 | Mediano |
| **F5 IVA base flujo detallado** | Bases por tasa (16 %, 8 %, 0 %, exento), retenciones, pestañas por origen, lista de CFDI que compone cada cifra, interruptor "no considerar IVA", periodo reasignado, exportación | F1, F3 | Grande |
| **F6 Proveedores y DIOT** | Catálogo de proveedores alimentado de los CFDI recibidos; DIOT por flujo y por tasa, editable, con exportación del archivo de carga | F5 | Grande |
| **F7 ISR base flujo** | Ingresos acumulables cobrados; deducciones (nómina gravada/exenta, compras de contado, pagos, notas de crédito, inversiones); ISR retenido; interruptor "no considerar ISR" | F1, F3 | Grande |
| **F8 Información fiscal** | Constancia de situación fiscal y opinión de cumplimiento: carga, visor y descarga | F0 | Chico |

**Punto de control de paridad** al terminar F8: se repite la comparación con Playwright
de las 26 capturas y se cuadran todas las cifras de control.

### Bloque B — Mejoras

| Fase | Entrega | Depende de |
|---|---|---|
| **M1 Trazabilidad** | Clic en cualquier importe para ver los CFDI que lo componen y la regla aplicada; marca en el listado de los CFDI con riesgo abierto | F3, F5 |
| **M2 Papel de trabajo y cierre** | Un Excel/PDF mensual con IVA, ISR, DIOT, conciliación y riesgos; cierre de periodo con lista de pendientes y bloqueo | F5–F7 |
| **M3 Alertas** | Campana funcional: e.firma por vencer, descarga terminada o fallida, CFDI cancelado después de considerarse, proveedor en lista 69-B (EFOS); validación de estado ante el SAT | F2, F6 |
| **M4 Vista de despacho** | Tablero multiempresa con score y pendientes. Requiere quitar la unicidad global de `cfdi.uuid` (hoy un mismo CFDI no puede existir en dos empresas de la plataforma) | F3 |
| **M5 Comparativo contra lo declarado** | Captura de lo pagado en declaraciones y diferencias contra lo calculado | F5, F7 |
| **M6 Experiencia** | Tablas móviles como tarjetas, ayuda por pantalla, recorrido guiado | F3 |
| **M7 Suscripción** | Planes, límites de RFC y usuarios, cobro | — |

Las correcciones chicas detectadas en la comparación (score del dashboard que no
respeta el periodo, fechas en formato ISO, 8 filas por página, encabezados con
mayúsculas mezcladas, campana sin función, rol "Contador" fijo) entran en F3, que
rehace esos componentes.

## Reglas fiscales por fase

Cada regla se confirma en la spec de su fase con el artículo vigente y se revisa con el
agente `dominio-fiscal`. Aquí se fija el criterio para que todas las fases usen el mismo.

### Comunes (F1 en adelante)

- **Importes**: siempre `Decimal`, nunca `float` en cálculo; redondeo a centavos al
  final, no por renglón.
- **Cifra oficial**: los totales del nodo `Impuestos` del comprobante mandan sobre la
  suma de los conceptos; el desglose por concepto es informativo.
- **Vigencia**: un CFDI cancelado no produce efectos. Si se canceló después de haberse
  considerado en un periodo ya cerrado, no se recalcula en silencio: se genera alerta (M3).
- **Moneda extranjera**: se convierte a pesos con el tipo de cambio del comprobante
  (o del pago, para cobros); se guardan importe original e importe en pesos.
- **Momento del efecto (flujo de efectivo)**:
  - PUE: fecha de emisión.
  - PPD: fecha de pago de cada complemento de pago (REP), por el importe de ese pago.
  - Nota de crédito (egreso): fecha de emisión, disminuye el efecto del periodo.
  - Anticipos: reglas ya implementadas (anticipo, factura con relación 07, egreso de
    aplicación con forma de pago 30); no se cuentan dos veces.
- **IVA de un pago**: se toma de `ImpuestosDR` del REP 2.0. Solo si el REP no lo trae
  (Pagos 1.0) se usa la proporción `importe pagado / total`, y la pantalla lo advierte.

### Descarga automática de XML (F2)

Hoy la descarga existe pero es manual: alguien llama a `/fiel/sync` por mes, y la
verificación corre dentro del proceso web durmiendo hasta 30 minutos (si el servidor se
reinicia, la descarga se pierde). F2 la vuelve desatendida.

- **Qué se descarga**: emitidos y recibidos, todos los tipos de comprobante (ingreso,
  egreso, traslado, nómina y pago), con su XML completo.
- **Cuándo**:
  - Carga inicial al guardar la e.firma: ejercicio en curso y el anterior, mes por mes.
  - Corrida diaria incremental: desde la última descarga exitosa, con un traslape de
    unos días para no perder comprobantes timbrados con retraso.
  - Botón "Actualizar ahora" para forzar una corrida.
- **Cancelaciones**: el servicio solo se consulta hoy con estado "Vigente", así que un
  CFDI cancelado después de descargarse sigue contando. La corrida diaria pide además
  los metadatos del periodo abierto y de los meses recientes y marca `estado =
  'cancelado'` en lo que corresponda. Un cancelado ya considerado en un periodo cerrado
  genera alerta (M3), no un recálculo silencioso.
- **Cómo corre**: un proceso `worker` aparte (segunda línea en `Procfile`) que toma
  trabajos de una tabla en Postgres. Cada solicitud avanza por estados guardados
  (solicitada → en proceso → lista → descargada → importada), de modo que un reinicio
  retoma donde iba. Un candado por empresa evita dos corridas simultáneas.
- **Idempotencia**: importar dos veces el mismo paquete no duplica nada (ya garantizado
  por `cfdi_store` y la migración 027). Cada XML importado pasa por el detalle fiscal
  de F1.
- **Fallas**: reintentos espaciados con tope; al agotarlos la solicitud queda en fallo
  con el mensaje del SAT visible en pantalla. e.firma vencida o revocada pausa la
  automatización de esa empresa y lo avisa.
- **Límites del SAT**: el servicio de descarga masiva limita solicitudes y tamaño de
  resultado. Los límites vigentes se verifican al escribir la spec de F2; el diseño
  parte periodos grandes en ventanas más chicas cuando el SAT rechaza por volumen.
- **Seguridad**: la e.firma sigue cifrada en reposo (`fiel_store`); el worker la
  descifra solo en memoria y solo para empresas con la automatización activada
  (decisión D8). Cada corrida queda en `auditoria` con origen "automático".
- **Ya adelantado (2026-10-01)**: la pantalla "Conexión SAT" (`/empresas/{id}/sat`)
  permite guardar, reemplazar y eliminar la e.firma, pedir la descarga manual por mes y
  ver el historial; al guardar se valida que el certificado sea del RFC de la empresa.
  F2 agrega sobre ella la automatización. El servidor necesita `FIEL_ENCRYPTION_KEY`
  en su entorno; hoy no está documentada en `.env.example`.
- **Cambios de datos previstos**: `sat_solicitudes.usuario_id` deja de ser obligatorio
  (las corridas automáticas no tienen usuario) y se agrega el origen de la solicitud;
  configuración de sincronización por empresa (activa, última corrida exitosa,
  próxima corrida).

### IVA (F4, F5)

- Trasladado efectivamente cobrado y acreditable efectivamente pagado (LIVA 1-B y 5).
- Desglose por tasa: 16 %, 8 % (región fronteriza), 0 % y exento, con su base.
- Acreditable: solo erogaciones deducibles; efectivo mayor a $2,000 se excluye
  (regla ya implementada); factor de prorrateo cuando hay actos exentos (LIVA 5-V).
- Retenciones de IVA: las que le hacen a la empresa disminuyen el IVA a cargo; las que
  la empresa hace a terceros son un entero aparte. Hoy `reportes.py` las deja en cero.
- Exclusión manual ("no considerar IVA") y cambio de periodo: decisiones del contador,
  por CFDI, registradas en `auditoria` con usuario y fecha.

### DIOT (F6)

- Por flujo (lo efectivamente pagado en el mes), por proveedor, tipo de tercero y tipo
  de operación, separando valor de actos por tasa e IVA no acreditable.
- El tipo de operación deja de ser fijo ("03" hoy): sale del catálogo de proveedores y
  es editable por periodo.
- El formato del archivo de carga se verifica contra la versión vigente del SAT al
  escribir la spec de F6; no se asume.

### ISR base flujo (F7)

- Ingresos acumulables al cobro: facturas de contado más cobros documentados con REP.
- Deducciones al pago: compras y gastos de contado, pagos con REP, menos notas de
  crédito recibidas; inversiones aparte (se deducen por depreciación, no al pago).
- Nómina: la parte gravada es deducible al 100 %; la parte exenta para el trabajador
  es deducible solo al 47 % o 53 % (LISR 28-XXX), porcentaje configurable por empresa
  y ejercicio.
- ISR retenido: a favor (el que le retienen a la empresa) y a cargo (el que retiene).
- Aplicabilidad por régimen (decisión D2): se determina en la spec de F7 con el
  catálogo de regímenes; el módulo por coeficiente de utilidad sigue disponible.

### Pendientes de extracción detectados en la revisión fiscal de F1

F1 guarda lo necesario para listar y desglosar; estos datos los necesitan los cálculos
y se extraen en la spec de la fase indicada subiendo `cfdi_store.DETALLE_VERSION` (el
reproceso vuelve a leer el `xml_raw`, sin descargar nada):

| Dato | Para qué | Fase |
|---|---|---|
| `pago20:Totales` e `ImpuestosP` del REP | Cifra oficial en pesos del IVA cobrado por tasa y control de cuadre; `ImpuestosP` cuando un REP trae pagos de meses distintos | F5 |
| `ObjetoImpDR` por documento pagado | Distinguir "no objeto" de "objeto sin desglose" y de un REP sin impuestos | F5 |
| RFC de `ACuentaTerceros` por concepto | Excluir del ingreso y del IVA propios lo cobrado por cuenta de terceros | F5, F7 |
| Nómina por percepción (`TipoPercepcion`, gravado/exento), `FechaPago`, `TipoNomina`, régimen del receptor, otros pagos por tipo (subsidio), separación y jubilación | Base correcta de la nómina exenta deducible (la PTU y los viáticos no entran) y mes de la deducción | F7 |

Criterios que los cálculos deben respetar con lo ya guardado:

- `cfdi_impuestos` no tiene fila para conceptos con `ObjetoImp` 01 o 03; hay que mirar
  `cfdi_conceptos.objeto_imp`.
- En IEPS de cuota la base son unidades (litros), no pesos: no se suma con bases monetarias.
- Los impuestos locales (ISH, ISN) no están en `cfdi_impuestos`; la suma de traslados
  del desglose no iguala el total de traslados del comprobante cuando existen.
- En CFDI 3.3 el desglose sale de los conceptos y puede diferir centavos del total del
  encabezado; manda el encabezado.
- Los importes del desglose van sin signo y en la moneda del comprobante: restar las
  notas de crédito y convertir a pesos le toca al cálculo.
- Una retención leída solo del nodo raíz queda con tasa nula y base 0: no es "tasa 0 %".
- Los impuestos de los pagos (`pagos_relaciones_impuestos`) están a 6 decimales en la
  moneda del documento; a pesos se llega con `equivalencia_dr` y el tipo de cambio del
  pago. `equivalencia_dr` nulo significa que el XML no trae el dato: no asumir 1.

## Riesgos

| Riesgo | Mitigación |
|---|---|
| Los XML reales traen casos que los fixtures no cubren (CFDI 3.3, Pagos 1.0, complementos raros) | F0 carga CFDI reales; F1 marca como "error de reproceso" lo que no pueda leer en vez de detener el lote |
| Cuadrar al centavo con la referencia puede ser imposible si ella aplica criterios distintos | Se documenta la diferencia y su fundamento; el criterio legal manda |
| `cfdi.uuid` único global impide el mismo CFDI en dos empresas | Se corrige en M4; antes no estorba porque se trabaja empresa por empresa |
| Listados grandes (hasta 1 millón de CFDI por RFC en la referencia) | F3 nace con paginación e índices en servidor; se prueba con volumen |
| Descarga automática de constancia/opinión depende del portal del SAT | Decisión D4: carga manual primero |
| El SAT rechaza o limita solicitudes de descarga masiva, o el servicio está caído | Estados persistidos, reintentos espaciados, ventanas más chicas, y la carga manual de XML se conserva como respaldo |
| Usar la e.firma sin intervención humana eleva el impacto de una fuga | Consentimiento por empresa (D8), descifrado solo en el worker, auditoría de cada corrida, opción de pausar y de borrar la e.firma |
| El plan de despliegue actual solo levanta el proceso web | F2 agrega el proceso `worker` al `Procfile` y a `dev.sh`; se confirma que el plan de hospedaje admite un segundo proceso |
| Archivos del backend en CRLF inflan los diffs | Normalizar finales de línea en F0, en un commit aparte |

## Estado

| Fase | Estado | Spec | Plan |
|---|---|---|---|
| F0 | En revisión (PR abierto; falta cargar CFDI reales) | (no requiere) | (lista de verificación abajo) |
| F1 | Implementada, en revisión (PR abierto). Falta el cierre con datos reales: reprocesar los CFDI de COPLASUR y cuadrar el IVA por tasa contra el encabezado | este documento, sección "Fases" y "Reglas comunes" | `docs/superpowers/plans/2026-10-01-fase1-detalle-fiscal-cfdi.md` |
| F2 | Pantalla manual hecha (PR #13); automatización pendiente | — | — |
| F3 | F3.1 (API del listado) integrada; F3.2 (pantalla única de CFDI) implementada, en revisión; F3.3 a F3.5 pendientes | `docs/superpowers/specs/2026-10-02-f3-listado-cfdi-design.md` | `docs/superpowers/plans/2026-10-02-f3-1-api-listado-cfdi.md`; un plan por cada entrega restante |
| F4–F8, M1–M7 | Pendiente | — | — |

### Lista de verificación de F0

- [x] Revisar y commitear el trabajo sin integrar (seguridad, migraciones, parsers,
      persistencia de CFDI y pagos, frontend), en commits separados por tema — rama
      `chore/f0-preparacion`.
- [x] Normalizar finales de línea (CRLF → LF) en un commit aparte, con `.gitattributes`.
- [x] `python -m pytest` completo (389) y `npm test` (115) en verde.
- [x] Guardar el script de comparación con Playwright: `frontend/scripts/capturas.cjs`.
- [ ] Integrar `chore/f0-preparacion` a `main` mediante PR (incluye el commit de
      `chore/dev-sh-stack-completo`).
- [ ] Cargar en local los CFDI de COPLASUR de enero a septiembre de 2026 con la
      descarga manual que ya existe (`/fiel/sync` por mes) o con XML ya descargados.
      Requiere la e.firma de la empresa; nunca se commitean. A partir de F2 esto
      ocurre solo.
