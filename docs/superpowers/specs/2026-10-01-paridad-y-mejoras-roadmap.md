# Plan maestro — paridad funcional con la plataforma de referencia y mejoras

Fecha: 2026-10-01. Estado: en ejecución; desde 2026-10-04 en tres carriles paralelos.

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
3. **Rama por entrega** desde `main` actualizado, commits Conventional Commit, un PR
   por entrega. Ninguna entrega empieza sobre una rama con trabajo sin integrar (ni
   propia ni de otra sesión). Las fases se reparten entre **tres sesiones en paralelo**
   con reglas de propiedad de archivos: ver "Trabajo en paralelo (3 sesiones)".
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

### Extracción v2 (F3.5a, migración 040, `DETALLE_VERSION` 2)

Lo que la revisión fiscal de F1 dejó pendiente de extraer **ya se guarda** (el reproceso
relee `xml_raw` de los CFDI con versión menor; no descarga nada del SAT):

| Dato | Dónde queda | Para qué | Fase que lo usa |
|---|---|---|---|
| `pago20:Totales` del REP | `cfdi_pagos_totales` (una fila por REP; NULL = el atributo no viene) | Cifra oficial en pesos del IVA cobrado por tasa y control de cuadre | F5 |
| `ImpuestosP` de cada pago | `pagos_impuestos` (en la moneda del pago, 6 decimales) | Cuando un REP trae pagos de meses distintos | F5 |
| `ObjetoImpDR` por documento pagado | `pagos_relaciones.objeto_imp_dr` | Distinguir "no objeto" de "objeto sin desglose" y de un REP sin impuestos | F5 |
| RFC, nombre y régimen de `ACuentaTerceros` por concepto (**solo CFDI 4.0**) | `cfdi_conceptos.rfc_a_cuenta_terceros` y afines | Excluir del ingreso y del IVA propios lo cobrado por cuenta de terceros | F5, F7 |
| Nómina: `TipoNomina`, `FechaPago`, fechas inicial y final, días pagados, `TipoRegimen`, número de empleado y los totales de percepciones, deducciones y otros pagos | `cfdi_nominas` (un renglón por nodo `Nomina`) | Mes de la deducción y régimen del receptor | F7 |
| Nómina: cada percepción (`TipoPercepcion`, gravado, exento), deducción (`TipoDeduccion`) y otro pago (`TipoOtroPago`, `SubsidioCausado`) | `cfdi_nomina_conceptos`, con el tipo tal cual viene en el XML | Base de la nómina exenta deducible (la PTU y los viáticos no entran) y subsidio causado; qué tipo cuenta como qué lo decide el cálculo | F7 |
| Nómina: separación/indemnización y jubilación/pensión/retiro | columnas `sep_*` y `jub_*` de `cfdi_nominas` | Ingreso acumulable y no acumulable | F7 |
| Nómina: `CompensacionSaldosAFavor` de un otro pago (saldo a favor, año y remanente) | columnas de `cfdi_nomina_conceptos` | Ajuste anual de ISR | F7 |

Lo que **no** se extrae, a propósito: la CURP, el NSS, el banco y la cuenta del trabajador
(dato personal que ningún cálculo usa; ojo: `xml_raw` sigue guardando el XML completo, así
que se trata con el mismo cuidado). Pendiente hasta que un cálculo lo pida: horas extra,
incapacidades (días y tipo), subcontratación y acciones o títulos de nómina.

Avisos para los cálculos que consumen esto:

- `ACuentaTerceros` solo existe en CFDI 4.0. En 3.3 el equivalente es el complemento Terceros
  1.1 (`terceros:PorCuentadeTerceros`), que no se lee: un 3.3 por cuenta de terceros queda
  como propio. Importa solo si se audita 2022 o antes.
- `cfdi_impuestos` y el resumen del comprobante mezclan lo propio con lo de terceros: F5 debe
  separarlos con `cfdi_conceptos.impuestos` y las columnas de terceros.
- En `pagos_impuestos` y `pagos_relaciones_impuestos`, la `base` de una retención no es un
  dato (el XML no la trae; queda 0).
- Dos pagos del mismo REP con la misma fecha y monto comparten fila en `pagos_cfdi`
  (`UNIQUE cfdi_id, fecha_pago, monto`): sus `ImpuestosP` se acumulan, pero sus documentos
  relacionados idénticos colapsan. La solución de fondo (agregar el orden del nodo a la
  llave) queda para F3.5b.
- `ObjetoImpDR` se guarda crudo: el catálogo c_ObjetoImp puede traer códigos nuevos además
  de 01 a 04.

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

## Trabajo en paralelo (3 sesiones)

Desde el 2026-10-04 el trabajo avanza en **sesiones simultáneas** (tres al inicio, cuatro desde que se abrió el carril D). Cada sesión es
dueña de un carril: unas fases, unos archivos y un rango de migraciones. **Ninguna
sesión toma una fase de otro carril**, aunque esté libre: si un carril se queda sin
trabajo desbloqueado, pasa a la siguiente fase de su propia lista o a las mejoras (M)
que tiene asignadas. Así no se repiten fases ni se pisan archivos.

Al iniciar, cada sesión lee esta sección, ubica su carril en la tabla "Estado" y toma
la **primera entrega no hecha** de su lista.

### Carriles

| Carril | Tema | Fases y entregas, en orden | Migraciones |
|---|---|---|---|
| **A — CFDI** | Listado, extracción del XML, visor | F3.5a extracción v2 → F3.5b → F3.6 evidencias y etiquetas → M4 → M1 → M6 (F3.3 y F3.4 integradas con los PR #21 y #24) | `040`–`049` |
| **B — SAT e infraestructura** | Descarga automática, worker, alertas | F2.1 (PR #17) → F2.2 → F2.3 → F2.4 → F2.5 → cierre de F0/F1 con datos reales → M3 | `031`–`039` |
| **C — Cálculos fiscales** | Inicio, IVA, DIOT, ISR, papel de trabajo | F4 → F5 (empieza ya; la parte de REP se completa al integrarse F3.5a) → F6 → F7 → M5 → M2 | `050`–`059` |
| **D — Información fiscal y cuenta** | Constancia y opinión de cumplimiento, suscripción | F8 → V1 Validaciones de CFDI → U1 Usuarios y perfil → M7 | `060`–`069` |

Detalle de las entregas que cambian respecto a las specs de su fase:

- **F3.5a Extracción v2 (carril A, en cuanto termine F3.4)**: sube `cfdi_store.DETALLE_VERSION` a 2 y
  extrae **de una sola vez** todo lo pendiente, no solo lo de F3.5: nómina por
  percepción (`TipoPercepcion`, gravado/exento, `FechaPago`, `TipoNomina`, otros pagos,
  separación y jubilación), `pago20:Totales` e `ImpuestosP`, `ObjetoImpDR` y RFC de
  `ACuentaTerceros` (tabla "Pendientes de extracción" más abajo). Solo backend: parser,
  migración, reproceso y pruebas. Va antes de F3.5b porque desbloquea F5 y F7 del carril C.
- **F3.5b (carril A)**: pestañas y totales de Nómina y Pagos en la pantalla, descarga de
  cancelados y retiro de `/emitidos`, `/recibidos`, `/cfdi/visor` y `/cfdi/nomina`.
- **M1 Trazabilidad (carril A)**: el clic en un importe abre el listado filtrado; el
  carril C expone en sus endpoints los filtros (o la lista de UUID) que componen cada
  cifra, y el carril A construye la navegación y la marca de riesgo en el listado.
- **F3.6 Evidencias y etiquetas (carril A)**: adjuntar evidencias a un CFDI, etiquetas
  por CFDI y casilla de selección para acciones en lote, como en la fila y el visor de la
  referencia (`2026-10-01-referencia-plataforma.md`, "CFDIs emitidos / recibidos").
- **F2.5 (carril B)** incluye el control de descargas **por día de emisión** con los
  conteos "lo que tiene el SAT contra lo descargado", además de la descarga inicial
  (referencia, "Descargas de CFDI").
- **V1 Validaciones de CFDI (carril D)**: tarjetas con conteo del periodo y acumulado,
  separadas en emitidos y recibidos (PUE con forma de pago 99, PUE con REP relacionados,
  egresos sin CFDI relacionados, recibidos no bancarizados) y su configuración. Módulo y
  router nuevos (`validaciones_cfdi.py`); no edita `riesgos.py` (carril C).
- **U1 Usuarios y perfil (carril D)**: perfil del usuario y alta de usuarios por empresa
  con su rol. Puede leer `auth.py` y `empresas.py` (carril B) pero sus cambios los hace
  en módulos propios; si necesita tocar esos archivos, va a "Pedidos entre carriles".
- **M3 Alertas (carril B)**: la parte de EFOS (69-B) espera a que F6 esté en `main`.
- **Cierre de F0 y F1 con datos reales (carril B)**: cargar los CFDI de COPLASUR (lo
  hace la descarga de F2), reprocesar y cuadrar el IVA por tasa contra el encabezado.

### Sesiones asignadas (2026-10-04)

| Carril | Sesión | Qué hace ahora |
|---|---|---|
| A | "F3.2 work" | F3.5a (extracción v2) en una rama nueva desde `main`. F3.4 integrada (PR #24) |
| B | "Cambios en ezaudita" | F2.1 en el PR #17; sigue F2.2 (worker) |
| C | "Acceso al proyecto" | F4 (Inicio). Antes de pasar al carril C dejó F3.3 hecha en el PR #21 |
| D | "Carril D — Información fiscal" (abierta el 2026-10-04) | F8 |

Una sesión nueva que se abra para este plan reemplaza a la de su carril; no se abre una
otra sesión de implementación sin agregar antes un carril aquí.

### Propiedad de archivos

Cada carril solo **modifica** los archivos de su columna; los de otro carril se pueden
**leer e importar**, nunca editar. Archivos nuevos: se crean dentro del área del carril.

| Carril A — CFDI | Carril B — SAT | Carril C — Cálculos |
|---|---|---|
| `backend/cfdi_parser.py`, `cfdi_store.py`, `reproceso.py`, `cfdi_columnas.py`, `cfdi_listado.py`, `catalogos_sat.py` | `backend/sat_fiel.py`, `sat_sync.py`, `worker.py`, `fiel_store.py`, `auditoria.py`; `Procfile`, `dev.sh`, `dev.bat`, `.env.example` | `backend/iva.py`, `isr.py`, `deducciones.py`, `motor_fiscal.py`, módulos nuevos (`diot.py`, `proveedores.py`, `isr_flujo.py`…) |
| `backend/routers/cfdis.py`, `cfdi.py`, `emitidos.py`, `ingesta.py` | `backend/routers/sat.py`, `empresas.py`, `auth.py`, `admin.py` | `backend/routers/reportes.py`, `dashboard.py`, `scoring.py`, `riesgos.py`, `conciliacion.py`, `movimientos.py`, routers nuevos de IVA/DIOT/ISR |
| `frontend/components/cfdi/`, `ingesta/`, `lib/cfdi-url.ts` | `frontend/components/sat/`, `empresas/`, `auth/`, `layout/Header.tsx` (campana), componentes nuevos de alertas e información fiscal | `frontend/components/dashboard/`, `cedula-iva/`, `conciliacion/`, componentes nuevos de IVA, DIOT, ISR |

**Carril D** es dueño de `backend/constancia_parser.py` (se lo cede B), de los módulos y routers nuevos de información fiscal y suscripción, y de `frontend/components/informacion-fiscal/` y `components/suscripcion/` (nuevos). Lee la e.firma y la empresa sin editar los archivos de B.

Si una entrega necesita cambiar un archivo de otro carril (por ejemplo, un filtro nuevo
en `cfdi_listado.py` para F5), **no lo edita**: lo resuelve dentro de su área (una
consulta propia en su módulo) o lo anota en "Pedidos entre carriles" para que el dueño
lo haga en su siguiente entrega.

### Archivos compartidos (solo se agregan líneas)

Estos archivos los tocan los tres carriles. La regla es **agregar al final de su
bloque, sin reordenar, reformatear ni borrar líneas ajenas**; así un conflicto se
resuelve conservando ambos lados.

| Archivo | Regla |
|---|---|
| `backend/db.py` (`init_db`) | Cada carril agrega las llamadas `_run_sql_file` de sus migraciones. Como todas son idempotentes y corren en cada arranque, el orden de integración no importa |
| `database/migrations/` | Solo números del rango del carril. Los huecos en la numeración son normales |
| `backend/main_api.py` | Solo agregar `include_router` de routers nuevos |
| `docs/openapi.yaml` | Agregar rutas y esquemas propios; no editar los de otro carril |
| `backend/schemas.py` | No se agregan modelos aquí: cada carril los pone en su router o en un módulo propio |
| `frontend/components/layout/Sidebar.tsx` | Cada carril agrega sus entradas de menú; el indicador de descarga (F2.5) es de B |
| `frontend/lib/api-client.ts`, `periodo.ts`, `formato.ts`, `components/ui/`, `components/shared/` | Solo agregar funciones o componentes nuevos; no cambiar firmas existentes |
| `backend/tests/conftest.py`, `requirements*.txt`, `frontend/package.json` | Solo agregar; dependencias nuevas en un commit aparte. `package-lock.json` en conflicto se regenera con `npm install`, nunca a mano |
| Este documento | Cada carril edita solo su fila en "Estado", su lista de verificación y "Pedidos entre carriles" |

### Dependencias entre carriles

Una entrega que depende de otro carril **espera a que eso esté en `main`**; nunca se
ramifica desde la rama de otra sesión.

| Entrega | Espera a | Mientras tanto |
|---|---|---|
| C · F5 (IVA por tasa con REP) | A · F3.5a en `main` | C hace F4, que solo depende de F1 |
| C · F7 (ISR, nómina exenta) | A · F3.5a en `main` | C hace F5 y F6 |
| B · M3 (EFOS 69-B) | C · F6 en `main` | B hace las alertas de e.firma, descargas y cancelados |
| A · M1 (trazabilidad) | C · F5 en `main` | A hace M4 |
| B · cierre F0/F1 con datos reales | B · F2.2 (worker) | — |

### Límite de uso de Claude Code

La sesión coordinadora revisa el límite de uso en cada check-in. Si alguna sesión
reporta que el límite está por agotarse (o ya se agotó), ordena a **todas** las sesiones
una pausa: terminan el paso en curso, suben su trabajo (commit y push, sin dejar nada
sin guardar) y se detienen. Al restablecerse el límite, la coordinadora las reanuda
con la entrega en la que iban. Ninguna sesión empieza una entrega nueva durante la
pausa.

### Rutina de cada sesión

1. `git fetch origin main` y crear la rama de la entrega desde `origin/main`.
2. Antes de abrir el PR y antes de integrarlo: traer `main` (merge, no rebase) y correr
   `python -m pytest` y `npm test`.
3. PR con título `<carril>·<entrega>: …` (por ejemplo `A·F3.3: visor del CFDI`).
4. Al integrarse: actualizar la fila del carril en "Estado" en ese mismo PR.

### Pedidos entre carriles

| Fecha | De → para | Qué se necesita | Estado |
|---|---|---|---|
| 2026-10-04 | D → B | Agregar `"informacion-fiscal": "Información fiscal"` al mapa del breadcrumb de `layout/Header.tsx` (hoy muestra "Empresas" en `/empresas/{id}/informacion-fiscal`) y `"informacion-fiscal"` a `SUB_RUTAS` de `layout/EmpresaSwitcher.tsx` (para conservar la pantalla al cambiar de empresa) | Hecho en el PR #30 (F2.3) |
| 2026-10-04 | D → B | U1: (1) `POST /mis-empresas` (`empresas.py`) vincula al creador con `rol = 'administrador'` (hoy usa el valor por defecto; U1 lo compensa al leer). (2) Breadcrumb de `Header.tsx` para `/perfil` ("Mi perfil") y `usuarios` ("Usuarios"); `"usuarios"` en `SUB_RUTAS` de `EmpresaSwitcher.tsx`. (3) Ya no aplica: U1 da acceso por invitación y no crea contraseñas temporales | Pendiente |

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

| Fase | Carril | Estado | Spec | Plan |
|---|---|---|---|---|
| F0 | B | Integrada salvo la carga de CFDI reales (se cierra con F2) | (no requiere) | (lista de verificación abajo) |
| F1 | B (cierre) | Integrada. Falta el cierre con datos reales: reprocesar los CFDI de COPLASUR y cuadrar el IVA por tasa contra el encabezado | este documento, sección "Fases" y "Reglas comunes" | `docs/superpowers/plans/2026-10-01-fase1-detalle-fiscal-cfdi.md` |
| F2 | B | F2.1 (base: migración 031, `sat_sync.py`, reintentos, partición por volumen y por 5002) y F2.2 (worker: `backend/worker.py`, `procesar_empresa`, candado por empresa, carga inicial y corrida diaria) integradas (PR #17); F2.3 (endpoints `sync/estado`, `sync/config`, `sync/ahora`, consentimiento y auditoría; borrar la e.firma desactiva la automatización) integrada (PR #30); F2.4 y F2.5 pendientes. Pendiente de quien tenga acceso: documentar `FIEL_ENCRYPTION_KEY` y `SAT_SYNC_*` en `.env.example` (texto en el plan de F2.2) | `docs/superpowers/specs/2026-10-03-f2-descarga-automatica-design.md` (en PR #17) | un plan por entrega |
| F3 | A | F3.1, F3.2, F3.3 (PR #21), F3.4 (PR #24) y F3.5a extracción v2 (PR #27) integradas; siguen F3.5b (incluye el orden del nodo en la llave de `pagos_cfdi`, migración 041) y F3.6 | `docs/superpowers/specs/2026-10-02-f3-listado-cfdi-design.md` | `2026-10-02-f3-1-api-listado-cfdi.md`, `2026-10-03-f3-2-pantalla-cfdi.md`; un plan por entrega restante |
| F4 | C | Integrada (PR #25); falta cuadrar con los CFDI reales de COPLASUR | `docs/superpowers/specs/2026-10-04-f4-inicio-design.md` | `docs/superpowers/plans/2026-10-04-f4-inicio.md` |
| F5 | C | F5.1 (motor, API y ajustes, PR #29) y F5.2 (pantalla y Excel, PR #32) integradas; F5.3 (cédula e Inicio al motor nuevo) en revisión; luego F5.4 (REP completo) | `docs/superpowers/specs/2026-10-04-f5-iva-base-flujo-design.md` | `docs/superpowers/plans/2026-10-04-f5-1-motor-iva-flujo.md`, `2026-10-04-f5-2-pantalla-iva-flujo.md` |
| F6, F7 | C | Pendiente | — | — |
| F8 | D | Integrada (PR #31); falta probar con PDF reales | `docs/superpowers/specs/2026-10-04-f8-informacion-fiscal-design.md` | `docs/superpowers/plans/2026-10-04-f8-informacion-fiscal.md` |
| M1, M4, M6 | A | Pendiente | — | — |
| M3 | B | Pendiente |
| V1 | D | En curso |
| U1 | D | En revisión (PR D·U1) | `docs/superpowers/specs/2026-10-04-u1-usuarios-perfil-design.md` | `docs/superpowers/plans/2026-10-04-u1-usuarios-perfil.md` |
| M7 | D | Pendiente |
| F3.6 | A | Pendiente (después de F3.5b) | — | — |
| Punto de control de paridad | Coordinación | Pendiente: al terminar F5–F7 se recorre FiscalCore con Playwright contra las capturas y se cuadran las cifras de control | — | — |
| M2, M5 | C | Pendiente | — | — |

### Lista de verificación de F0

- [x] Revisar y commitear el trabajo sin integrar (seguridad, migraciones, parsers,
      persistencia de CFDI y pagos, frontend), en commits separados por tema — rama
      `chore/f0-preparacion`.
- [x] Normalizar finales de línea (CRLF → LF) en un commit aparte, con `.gitattributes`.
- [x] `python -m pytest` completo (389) y `npm test` (115) en verde.
- [x] Guardar el script de comparación con Playwright: `frontend/scripts/capturas.cjs`.
- [x] Integrar `chore/f0-preparacion` a `main` mediante PR (incluye el commit de
      `chore/dev-sh-stack-completo`).
- [ ] Cargar en local los CFDI de COPLASUR de enero a septiembre de 2026 con la
      descarga manual que ya existe (`/fiel/sync` por mes) o con XML ya descargados.
      Requiere la e.firma de la empresa; nunca se commitean. A partir de F2 esto
      ocurre solo.
