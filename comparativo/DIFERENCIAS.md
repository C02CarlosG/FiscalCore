# Comparativo ezaudita vs FiscalCore — Diferencias por pantalla

**Fecha:** 2026-10-08
**Contribuyente:** COPLASUR S.A. DE C.V. (COP941004363)
**Periodos:** ezaudita = Enero 2026, FiscalCore = Octubre 2026 (acumulados del ejercicio comparables)

> **Nota sobre periodos:** ezaudita se revisó en Enero 2026 (con datos reales), FiscalCore en Octubre 2026 (sin datos en el periodo, pero con acumulados del ejercicio). Las cifras del periodo no son directamente comparables; las diferencias estructurales y funcionales sí lo son.

---

## 01 — Dashboard / Inicio

| Aspecto | ezaudita | FiscalCore | Tipo de diferencia |
|---------|----------|------------|-------------------|
| **Nombre** | "Inicio" | "Dashboard" | Diferencia de diseño |
| **KPIs principales** | 2 tarjetas: Ingresos netos + Gastos y compras netas (periodo + acumulado del ejercicio) | 2 tarjetas: Ingresos ejercicio ($101M) + Gastos ejercicio ($59M) | Diferencia de diseño — FiscalCore no muestra el desglose periodo/acumulado como par |
| **Gráfica** | Barras con opción "Cambiar a líneas", eje Y monetario | Gráfica de barras de 12 meses | Diferencia de diseño |
| **Tabla ingresos** | Ingresos nominales por mes: 6 columnas (Cancelados, Vigentes, Ingresos nominales, Descuentos, Ingresos netos) con total anual | Ingresos por mes: muestra total CFDI e importe por mes, 1,686 CFDIs total | Diferencia de diseño — ezaudita incluye cancelados y descuentos |
| **Tabla IVA** | IVA por periodo con 3 pestañas (IVA por periodo, IVA trasladado, IVA acreditable), 4 columnas con retenciones | IVA ejercicio con 3 pestañas, tabla simplificada | Diferencia de diseño |
| **Alertas** | 2 alertas (SAT inactivo, plan de prueba) | 7 advertencias de IVA (inconsistencias) | Función extra FiscalCore (alertas de validación integradas en dashboard) |
| **Scoring / Riesgo** | No existe | 3 tarjetas de scoring + lista de riesgos (todo en 0) | Función extra FiscalCore |
| **Editar widgets** | Botón "Editar widgets" | No visible | Función faltante FiscalCore |
| **Copiar tabla** | Botón "Copiar tabla" | No visible | Función faltante FiscalCore |

---

## 02 — CFDI Emitidos

| Aspecto | ezaudita | FiscalCore | Tipo de diferencia |
|---------|----------|------------|-------------------|
| **Pestañas tipo** | Ingreso (415), Egreso (12), Traslado (22), Nómina (791), Pago (52) | Ingreso, Egreso, Traslado, Nómina, Pago (con conteos) | Paridad funcional |
| **Filtros** | Periodo, Búsqueda (UUID/RFC/receptor), Filtro avanzado (icono), Estado (Vigentes/Cancelados/Todos), Método pago (PUE/PPD/Todos) | Periodo, Búsqueda, Etiquetas, Estado, Forma de pago + Filtro avanzado, Columnas, Columnas de totales | Función extra FiscalCore (filtro de etiquetas, control de columnas, columnas de totales) |
| **Tabla totales** | 13 columnas: desglose retenciones (IVA, IEPS, ISR), traslados (IVA, IEPS, ISR), subtotal, descuento, neto, total | Acumulado: 1,639 CFDIs, $118,243,557.52 — columnas configurables | Diferencia de diseño — ezaudita muestra desglose fiscal inline |
| **Tabla CFDIs** | Serie, Folio, RFC, Receptor, Total, Saldo de factura. Scroll continuo | Columnas configurables. Paginación con control de registros | Diferencia de diseño |
| **Exportar** | Botón "Exportar" | Botón "Exportar a Excel" | Paridad funcional |
| **Editar columnas** | "Editar columnas" | "Columnas" + "Columnas de totales" | Función extra FiscalCore (control separado de columnas de datos y totales) |

---

## 03 — CFDI Detalle (modal)

| Aspecto | ezaudita | FiscalCore | Tipo de diferencia |
|---------|----------|------------|-------------------|
| **Vista** | Modal sobre la lista con datos completos del CFDI | No capturado como pantalla separada (se accede desde la lista) | Diferencia de diseño |
| **Datos visibles** | Emisor, Receptor, UUID, Fecha, Certificado, Conceptos paginados, Totales, Moneda, Forma/Método de pago, Uso CFDI, Etiquetas | Similar — la tabla de CFDIs tiene expansión de detalle | Pendiente de verificación |
| **Descargas** | XML + PDF (botones), "Ver Evidencias" | No verificado en esta sesión | Pendiente de verificación |

---

## 04 — CFDI Recibidos

| Aspecto | ezaudita | FiscalCore | Tipo de diferencia |
|---------|----------|------------|-------------------|
| **Estructura** | Idéntica a Emitidos con "RFC emisor" / "Emisor" | Idéntica a Emitidos con ajuste de perspectiva | Paridad funcional |
| **Pestañas** | Ingreso (201), Egreso (9), Traslado (0), Nómina (0), Pago (61) | Mismos tipos con conteos del acumulado | Paridad funcional |
| **Filtros** | Periodo, Búsqueda, Estado, Método pago | Periodo, Búsqueda, Etiquetas, Estado, Forma de pago + controles de columnas | Función extra FiscalCore |

---

## 05 — Ingesta / Carga de CFDI

| Aspecto | ezaudita | FiscalCore | Tipo de diferencia |
|---------|----------|------------|-------------------|
| **Pantalla dedicada** | No tiene — la carga es vía Sincroniza SAT | Pantalla dedicada "Ingesta" con dos paneles | Función extra FiscalCore |
| **Carga XML** | No tiene carga manual de XML | "Subir CFDI": XML múltiple + periodo | Función extra FiscalCore |
| **Estado de cuenta** | No tiene | "Subir estado de cuenta": XLSX/CSV, banco (dropdown), periodo | Función extra FiscalCore |

---

## 06 — Conciliación bancaria

| Aspecto | ezaudita | FiscalCore | Tipo de diferencia |
|---------|----------|------------|-------------------|
| **Existe** | No tiene módulo de conciliación | "Cruces banco-CFDI" con 5 KPIs: Exactos, Parciales, Sin CFDI, Sin movimiento, % Conciliado | Función extra FiscalCore |

---

## 07 — Cédula de IVA

| Aspecto | ezaudita | FiscalCore | Tipo de diferencia |
|---------|----------|------------|-------------------|
| **Existe** | No tiene como pantalla separada — se calcula dentro de IVA base flujo | Pantalla dedicada con 9 filas de determinación (IVA trasladado → saldo a favor) | Función extra FiscalCore |

---

## 08 — IVA base flujo

| Aspecto | ezaudita | FiscalCore | Tipo de diferencia |
|---------|----------|------------|-------------------|
| **KPIs** | 3 tarjetas: IVA trasladado ($4,088,512.30), IVA acreditable ($3,058,071.54), IVA a cargo ($1,030,440.76) | 9 KPIs en 3 filas: Trasladado, Acreditable, A cargo + Totales, Contado, Crédito + Notas, No considerados, Reasignados | Función extra FiscalCore (más desglose) |
| **Pestañas/detalle** | 6 pestañas: Totales, Contado, Crédito, Notas de crédito, No considerados, Reasignado | No tiene pestañas — los KPIs reemplazan la navegación por pestañas | Diferencia de diseño |
| **Tabla desglose** | ~10 columnas: Base IVA 16%/8%/0%/exento, IVA trasladado por tasa, Retenciones | Tabla de desglose por tasa (parcialmente visible): TASA, BASE, IVA | Diferencia de diseño — ezaudita más granular |
| **Aviso** | "No están considerados CFDIs de pago 1.0" | Sin aviso equivalente | Diferencia de diseño |
| **Exportar** | "Exportar a Excel" | "Exportar" | Paridad funcional |

---

## 09 — ISR base flujo

| Aspecto | ezaudita | FiscalCore | Tipo de diferencia |
|---------|----------|------------|-------------------|
| **KPIs** | 4 valores: Ingresos acumulables ($25.5M), ISR retenido a favor ($0), Deducciones ($24.2M), ISR retenido a cargo ($2,317.69) | Warning "régimen no soportado", Nómina exenta 47%, Utilidad fiscal $0.00 | Diferencia de diseño |
| **Pestañas** | 4: Totales, Contado, Pagos, No considerados | Sin pestañas — tabla directa | Diferencia de diseño |
| **Advertencias** | Aviso "No están considerados CFDIs de pago 1.0" | 4 notas de advertencia: REP sin forma pago (91), Anticipos SAT (43), Compras efectivo ≤$2000 (344), Inversiones I01-I08 (2) | Función extra FiscalCore (advertencias detalladas por tipo de CFDI) |
| **Soporte de régimen** | Funciona para el contribuyente | Muestra "régimen no soportado" | Error FiscalCore (no reconoce el régimen 601) |

---

## 10 — DIOT

| Aspecto | ezaudita | FiscalCore | Tipo de diferencia |
|---------|----------|------------|-------------------|
| **Nombre** | "Generar DIOT" | "DIOT por flujo" | Diferencia de diseño |
| **Pestañas por zona** | 6: Todos, Zona norte, Zona sur, IVA general, Importaciones tangibles, Importaciones intangibles | Sin pestañas por zona | Función faltante FiscalCore |
| **Tabla proveedores** | ~40+ columnas: datos tercero + montos por región + desglose IVA + campos editables | Tabla simple — "No hay compras con efecto en este periodo" | Función faltante FiscalCore (no se ve edición ni desglose por zona) |
| **Edición inline** | Sí — tipo tercero, tipo operación, montos editables, toggle manifiesto | No visible | Función faltante FiscalCore |
| **Agregar proveedor** | Botón "+ Agregar proveedor" | No visible | Función faltante FiscalCore |
| **Exportar** | "Exportar DIOT" (dropdown con formatos) | "Exportar Excel" | Diferencia de diseño |
| **Guardar cambios** | Botón "Guardar Cambios" | No visible | Función faltante FiscalCore |

---

## 11 — EFOS (Lista 69-B)

| Aspecto | ezaudita | FiscalCore | Tipo de diferencia |
|---------|----------|------------|-------------------|
| **Existe** | Sí — pantalla EFOS con cruce automático contra lista 69-B, última actualización 31/ago/2026 | No existe como pantalla | Función faltante FiscalCore |

---

## 12 — Conexión SAT / Sincroniza SAT

| Aspecto | ezaudita | FiscalCore | Tipo de diferencia |
|---------|----------|------------|-------------------|
| **Nombre** | "Sincroniza SAT" | "Conexión SAT" | Diferencia de diseño |
| **e.firma** | Subir .cer + .key + contraseña | Subir .cer + .key + contraseña. Estado: vigente, RFC, fecha expiración, fecha guardado | Función extra FiscalCore (muestra estado detallado de la e.firma) |
| **Descarga masiva** | Disponible (detalles no capturados) | Formulario: periodo + tipo (Emitidos y recibidos). Historial de descargas con estado | Paridad funcional |
| **Historial** | No capturado en detalle | Tabla con: Solicitada, Tipo, Periodo, Estado, CFDI importados | Función extra FiscalCore (historial visible) |

---

## 13 — Información fiscal

| Aspecto | ezaudita | FiscalCore | Tipo de diferencia |
|---------|----------|------------|-------------------|
| **Existe** | No existe como pantalla separada — el régimen se muestra en configuración | Pantalla dedicada: Opinión cumplimiento (PDF), Constancia situación fiscal (PDF), Régimen fiscal, Historial | Función extra FiscalCore |

---

## 14 — Validaciones de CFDI

| Aspecto | ezaudita | FiscalCore | Tipo de diferencia |
|---------|----------|------------|-------------------|
| **Nombre** | "Validaciones" (menú lateral) — no capturado en detalle | "Validaciones de CFDI" | Pendiente — ezaudita tiene el menú pero no fue explorado |
| **Contenido FC** | N/A | Emitidos: 3 reglas (PUE fp99, PUE con complemento, Egresos sin CFDI). Recibidos: 5 reglas (+ Gastos no bancarizados, Gas efectivo). Contadores periodo + acumulado. Botón "Configurar validaciones" | Función extra FiscalCore (reglas configurables) |

---

## 15 — Usuarios

| Aspecto | ezaudita | FiscalCore | Tipo de diferencia |
|---------|----------|------------|-------------------|
| **Existe** | Sí — en Configuración > Usuarios | Pantalla dedicada "Usuarios" | Paridad funcional |
| **Roles** | No capturado en detalle | Administrador, Contador. Invitación por correo | Pendiente de verificación en ezaudita |

---

## 16 — Reiniciar datos

| Aspecto | ezaudita | FiscalCore | Tipo de diferencia |
|---------|----------|------------|-------------------|
| **Existe** | Sí — en Configuración > Reiniciar | Pantalla dedicada "Reiniciar datos" | Paridad funcional |
| **Contenido FC** | No capturado en detalle | Borra CFDI, pagos, movimientos, conciliaciones, ajustes, DIOT. Conserva empresa, usuarios, e.firma, docs fiscales, declaraciones, proveedores, auditoría. Botón "Ver qué se borraría" | Pendiente de verificación |

---

## 17 — Empresas

| Aspecto | ezaudita | FiscalCore | Tipo de diferencia |
|---------|----------|------------|-------------------|
| **Vista** | No capturada como pantalla separada | Lista de empresas con RFC, Razón social, Régimen fiscal. Búsqueda + "+ Nueva empresa". Paginación | Función extra FiscalCore (gestión multi-empresa dedicada) |

---

## 18 — Mi perfil

| Aspecto | ezaudita | FiscalCore | Tipo de diferencia |
|---------|----------|------------|-------------------|
| **Existe** | Sí — Configuración > Perfil de usuario | Pantalla dedicada "Mi perfil" | Paridad funcional |
| **Campos FC** | No capturado en detalle | Nombre, Teléfono, RFC, Despacho, Cédula profesional + Cambio de contraseña | Pendiente de verificación |

---

## 19 — Suscripción

| Aspecto | ezaudita | FiscalCore | Tipo de diferencia |
|---------|----------|------------|-------------------|
| **Existe** | Sí — menú lateral "Suscripción" | Pantalla dedicada "Suscripción" | Paridad funcional |
| **Planes FC** | No capturado en detalle | 4 planes: Prueba ($0/1 RFC), Básico ($499/3 RFC), Despacho ($1,499/15 RFC), Ilimitado ($3,999/sin límite) | Pendiente de verificación |

---

## 20 — Login

| Aspecto | ezaudita | FiscalCore | Tipo de diferencia |
|---------|----------|------------|-------------------|
| **Layout** | No capturado | Dos columnas: hero izquierda (fondo oscuro, "Visibilidad clara para cada obligación") + formulario derecha (Correo + Contraseña) | Pendiente de verificación |
| **Registro** | No capturado | No visible en la pantalla de login | Pendiente de verificación |
| **Recuperar contraseña** | No capturado | No visible en la pantalla de login | Función faltante FiscalCore |

---

## Pantallas en ezaudita sin equivalente en FiscalCore

| # ezaudita | Pantalla | Estado en FiscalCore |
|------------|----------|---------------------|
| 03 | Detalle CFDI (modal) | Existe como expansión en la tabla, no como pantalla dedicada |
| 09 | EFOS (Lista 69-B) | **No existe** |
| — | Exportaciones | No verificado como pantalla separada |
| — | Soporte | No existe en FiscalCore |
| — | Notificaciones (Configuración) | No existe en FiscalCore |

## Pantallas en FiscalCore sin equivalente en ezaudita

| # FC | Pantalla | Notas |
|------|----------|-------|
| 04 | Ingesta (carga manual XML + estados de cuenta) | ezaudita solo descarga del SAT |
| 05 | Conciliación bancaria (Cruces banco-CFDI) | No existe en ezaudita |
| 06 | Cédula de IVA (determinación mensual) | ezaudita calcula dentro de IVA base flujo |
| 11 | Información fiscal (Opinión, Constancia, Régimen) | No existe en ezaudita |
| 12 | Validaciones de CFDI (reglas configurables) | ezaudita tiene "Validaciones" en menú pero no fue explorado |

---

## Resumen de conteo de diferencias

| Tipo | Cantidad |
|------|----------|
| Función extra FiscalCore | 15 |
| Función faltante FiscalCore | 8 |
| Diferencia de diseño | 14 |
| Error FiscalCore | 1 |
| Paridad funcional | 8 |
| Pendiente de verificación | 7 |
