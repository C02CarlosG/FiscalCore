# Plan de acción — Cierre de gaps EZAudita vs FiscalCore

Fecha: 2026-10-09
Fuente: `comparativo/DIFERENCIAS.md` (branch `worktree-comparativo-fiscalcore`, commit `a80cf04`)

## Resumen del comparativo

| Tipo | Cantidad |
|---|---|
| Función extra FiscalCore | 15 |
| **Función faltante FiscalCore** | **8** |
| Diferencia de diseño | 14 |
| Error FiscalCore | 1 |
| Paridad funcional | 8 |
| Pendiente de verificación | 7 |

FiscalCore ya supera a EZAudita en 15 funciones (Ingesta, Conciliación bancaria, Cédula de IVA, Scoring/Riesgos, Validaciones configurables, Información fiscal, multi-empresa). El plan se centra en los **8 gaps faltantes + 1 error** que necesitan cerrarse.

---

## Mapa de gaps → estado en el roadmap

| # | Gap | Severidad | ¿Ya está en el roadmap? | Fase/Entrega | Estado actual |
|---|-----|-----------|------------------------|--------------|---------------|
| G1 | **EFOS (Lista 69-B)** — no existe como pantalla | Alta | Sí — M3 Alertas (carril B), la parte de EFOS espera a F6 en `main` | M3 | Pendiente; F6.1 integrada, F6.2 en curso |
| G2 | **DIOT — edición inline** de tipo tercero/operación/montos | Alta | Sí — F6.2/F6.3 (carril C) | F6 | F6.2 en curso |
| G3 | **DIOT — pestañas por zona** (norte, sur, IVA general, importaciones) | Alta | Parcial — F6 tiene la DIOT por flujo pero la spec no detalla pestañas por zona | F6 | Revisar spec |
| G4 | **DIOT — agregar proveedor manual** | Media | Sí — F6 catálogo de proveedores editable | F6 | F6.1 integrada |
| G5 | **DIOT — guardar cambios** por periodo | Media | Sí — F6.2 edición de DIOT | F6 | F6.2 en curso |
| G6 | **ISR — régimen 601 no reconocido** (error activo) | Alta | Sí — F7 define aplicabilidad por régimen | F7 | F7.2 en revisión |
| G7 | **Dashboard — editar widgets** | Baja | No | — | No planeado |
| G8 | **Dashboard — copiar tabla** | Baja | No | — | No planeado |
| G9 | **Recuperar contraseña** en login | Media | Sí — D9 (carril B), antes de producción | Seguridad B | Pendiente |

Extras mencionados en EZAudita sin equivalente:
- **Soporte** — página de contacto/ayuda → prioridad baja, se puede resolver con un enlace
- **Notificaciones (Configuración)** — preferencias de alertas → se integra con M3

---

## Plan de acción por prioridad

### Prioridad 1 — Errores activos (resolver ya)

#### G6: ISR régimen 601 (General de Ley Personas Morales)

- **Problema**: la pantalla de ISR base flujo muestra "El régimen de la empresa no está soportado por este módulo"
- **Causa probable**: el módulo `isr_flujo.py` no incluye el régimen 601 en su lista de regímenes soportados
- **Acción**: verificar en F7.2 (PR en revisión) que el régimen 601 esté en la lista; si no, agregarlo
- **Carril**: C (cálculos)
- **Esfuerzo**: chico (probablemente es agregar "601" a un catálogo)
- **Entrega**: F7.2 (ya en revisión)

---

### Prioridad 2 — Gaps funcionales críticos (paridad fiscal)

#### G1: EFOS (Lista 69-B)

El cruce contra la lista 69-B es **obligatorio** para la debida diligencia fiscal. EZAudita lo tiene como pantalla dedicada con:
- Cruce automático de CFDI recibidos contra la lista 69-B publicada por el SAT
- Filtro por periodo, estado (vigentes/cancelados/todos), tipo de CFDI
- Tabla con totales de impuestos de los CFDI afectados
- Fecha de última actualización de la lista

**Diseño propuesto**:

| Componente | Detalle |
|---|---|
| **Backend** | Nuevo módulo `backend/efos.py`: descarga periódica de la lista 69-B (CSV del SAT), tabla `efos_lista` (RFC, nombre, fecha publicación, supuesto, estado). Cruce con `cfdi` por RFC emisor de recibidos |
| **Router** | `backend/routers/efos.py`: `GET /empresas/{id}/efos` (lista de CFDI recibidos de proveedores en 69-B), `GET /empresas/{id}/efos/resumen` (conteo y montos) |
| **Frontend** | Pantalla `frontend/components/efos/` con tabla paginada, filtros y alerta en dashboard |
| **Migración** | Rango del carril que lo tome (B: `03x`, o nuevo carril) |
| **Dependencia** | F6 en `main` (catálogo de proveedores) — ya casi lista |

- **Carril**: B (M3 Alertas)
- **Esfuerzo**: mediano (2-3 entregas)
- **Prerequisito**: F6 integrada

#### G2 + G3 + G4 + G5: DIOT completa

La DIOT de FiscalCore (F6) está en desarrollo. Los gaps específicos contra EZAudita:

| Sub-gap | Qué falta | Dónde se resuelve |
|---|---|---|
| Edición inline | Editar tipo de tercero, tipo de operación y montos por proveedor-periodo | F6.2 (en curso) — ya contemplado en spec F6 |
| Pestañas por zona | Norte (8%), Sur (16%), IVA general, Importaciones tangibles/intangibles | **Agregar a F6.2 o F6.3** — la spec actual no las detalla |
| Agregar proveedor manual | Botón para agregar un proveedor que no viene de CFDI | F6.1 (catálogo) ya tiene la base; falta el botón en la pantalla |
| Guardar cambios | Persistir ediciones del periodo | F6.2 (en curso) — las tablas `diot_terceros_periodo` y `diot_operaciones_cfdi` ya existen |
| Exportar DIOT (archivo SAT) | Archivo en formato de carga del SAT, no solo Excel | F6.3 — pendiente del layout oficial |

- **Carril**: C (cálculos)
- **Esfuerzo**: las pestañas por zona son el cambio más grande; el resto ya está en la spec
- **Acción inmediata**: revisar la spec de F6 y agregar las pestañas por zona geográfica si no están

---

### Prioridad 3 — Gaps de experiencia (nice-to-have para paridad)

#### G7: Dashboard — editar widgets

EZAudita permite reorganizar/mostrar/ocultar widgets del dashboard.

**Propuesta**: se puede implementar como mejora del dashboard en M6 (Experiencia, carril A). Guardar las preferencias de widgets por usuario en la tabla `preferencias_usuario` que ya existe.

- **Carril**: A (M6)
- **Esfuerzo**: mediano
- **Prioridad**: baja — no bloquea funcionalidad fiscal

#### G8: Dashboard — copiar tabla

Botón para copiar una tabla al portapapeles (útil para pegar en Excel o un correo).

**Propuesta**: componente reutilizable `CopyTableButton` en `frontend/components/shared/`. Se aplica a todas las tablas, no solo al dashboard.

- **Carril**: cualquiera (componente compartido)
- **Esfuerzo**: chico (1 componente)
- **Prioridad**: baja — se puede incluir en cualquier entrega

#### G9: Recuperar contraseña

Ya está en el roadmap como requisito de D9 (antes de producción). Requiere servicio de envío de correo.

- **Carril**: B (seguridad)
- **Esfuerzo**: mediano (necesita integración con servicio de correo)
- **Prioridad**: alta antes de producción, no bloquea desarrollo

---

## Cronograma propuesto

```
Semana 1-2 (inmediato)
├── G6: Fix régimen 601 en F7.2 ........................ Carril C [en revisión]
├── G2/G5: DIOT edición inline y guardar ............... Carril C · F6.2 [en curso]
└── G3: Revisar spec F6 → agregar pestañas por zona .... Carril C · F6.2/F6.3

Semana 3-4 (después de integrar F6)
├── G1: EFOS Lista 69-B ................................ Carril B · M3
├── G4: Agregar proveedor manual en pantalla ........... Carril C · F6.3
└── G6: Validar fix con datos reales de COPLASUR ....... Carril C

Semana 5-6 (mejoras de experiencia)
├── G8: Copiar tabla (componente compartido) ........... Cualquier carril
├── G7: Editar widgets dashboard ....................... Carril A · M6
└── G9: Recuperar contraseña ........................... Carril B · seguridad
```

---

## Diferencias de diseño (no son gaps)

Las 14 diferencias de diseño **no requieren acción**: FiscalCore tiene su propio sistema visual y en varios casos es superior (más KPIs, filtros de etiquetas, columnas configurables, scoring integrado). Ejemplos:

- Dashboard: "Inicio" vs "Dashboard" → nombre propio, OK
- Gráficas: EZAudita tiene toggle barras/líneas → nice-to-have menor
- Tablas: EZAudita muestra scroll continuo, FiscalCore paginación → mejor para volumen

---

## Verificación pendiente (7 items)

Estos requieren revisar EZAudita con más detalle para confirmar si hay gap real:

1. Detalle CFDI modal — FiscalCore tiene expansión en tabla, verificar si es equivalente
2. Descargas XML + PDF por CFDI — verificar en el visor de FiscalCore
3. Roles de usuario en EZAudita — comparar con los de U1
4. Reiniciar datos — comparar alcance
5. Campos de perfil — comparar con U1
6. Planes de suscripción — comparar precios y límites
7. Login/Registro — comparar flujo

---

## Resumen ejecutivo

| Acción | Esfuerzo | Impacto | Quién |
|--------|----------|---------|-------|
| Fix régimen 601 | Chico | Alto — desbloquea ISR para PM | Carril C (ya en revisión) |
| DIOT completa (edición + zonas) | Grande | Alto — paridad fiscal obligatoria | Carril C (en curso) |
| EFOS 69-B | Mediano | Alto — debida diligencia fiscal | Carril B (espera F6) |
| Recuperar contraseña | Mediano | Alto pre-producción | Carril B |
| Copiar tabla | Chico | Bajo | Cualquiera |
| Editar widgets | Mediano | Bajo | Carril A |

**De los 8 gaps, 6 ya están contemplados en el roadmap actual** (F6, F7, M3, D9). Solo 2 son nuevos (editar widgets y copiar tabla) y son de baja prioridad. El gap más crítico (EFOS) se desbloquea en cuanto F6 se integre a `main`.
