# FiscalCore — Índice de pantallas capturadas

**Fecha:** 2026-10-08
**URL base:** https://fiscalcore-cpc-arlos.vercel.app
**Empresa:** COPLASUR S.A. DE C.V. (COP941004363)
**Periodo:** 2026-10 (Octubre)

## Pantallas capturadas

| # | Pantalla | Sección | Archivo JSON | Screenshot | Estado |
|---|----------|---------|-------------|------------|--------|
| 01 | Dashboard | FISCAL | `01_dashboard.json` | `01_dashboard.jpg` | OK |
| 02 | CFDI Emitidos | FISCAL | `02_cfdi_emitidos.json` | `02_cfdi_emitidos.jpg` | OK |
| 03 | CFDI Recibidos | FISCAL | `03_cfdi_recibidos.json` | `03_cfdi_recibidos.jpg` | OK |
| 04 | Ingesta | FISCAL | `04_ingesta.json` | `04_ingesta.jpg` | OK |
| 05 | Conciliación (Cruces banco-CFDI) | FISCAL | `05_conciliacion.json` | `05_conciliacion.jpg` | OK |
| 06 | Cédula de IVA | FISCAL | `06_cedula_iva.json` | `06_cedula_iva.jpg` | OK |
| 07 | IVA base flujo | FISCAL | `07_iva_base_flujo.json` | `07_iva_base_flujo.jpg` | OK |
| 08 | ISR base flujo | FISCAL | `08_isr_base_flujo.json` | `08_isr_base_flujo.jpg` | OK |
| 09 | DIOT por flujo | FISCAL | `09_diot_por_flujo.json` | `09_diot_por_flujo.jpg` | OK |
| 10 | Conexión SAT | FISCAL | `10_conexion_sat.json` | `10_conexion_sat.jpg` | OK |
| 11 | Información fiscal | FISCAL | `11_informacion_fiscal.json` | `11_informacion_fiscal.jpg` | OK |
| 12 | Validaciones de CFDI | FISCAL | `12_validaciones.json` | `12_validaciones.jpg` | OK |
| 13 | Usuarios | FISCAL | `13_usuarios.json` | `13_usuarios.jpg` | OK |
| 14 | Reiniciar datos | FISCAL | `14_reiniciar_datos.json` | `14_reiniciar_datos.jpg` | OK |
| 15 | Empresas | WORKSPACE | `15_empresas.json` | `15_empresas.jpg` | OK |
| 16 | Mi perfil | CUENTA | `16_mi_perfil.json` | `16_mi_perfil.jpg` | OK |
| 17 | Suscripción | CUENTA | `17_suscripcion.json` | `17_suscripcion.jpg` | OK |
| 18 | Login | ACCESO | `18_login.json` | `18_login.jpg` | OK |

## Notas

- Todas las pantallas cargaron correctamente; no hubo errores HTTP ni pantallas rotas.
- El periodo Octubre 2026 no tiene datos de CFDI (todos los valores del periodo son $0.00), pero los acumulados del ejercicio muestran datos reales (1,686 emitidos, 853 recibidos).
- La pantalla de ISR base flujo muestra una advertencia: "El régimen de la empresa no está soportado por este módulo."
- La pantalla de DIOT por flujo muestra "No hay compras con efecto en este periodo."
- Las pantallas 12–14 son de configuración específica de la empresa (Validaciones, Usuarios, Reiniciar datos).
- Las pantallas 15–17 son del workspace/cuenta (Empresas, Mi perfil, Suscripción).
- La pantalla 18 es el login (acceso público, no autenticado).

## Pantallas NO encontradas en FiscalCore

Ninguna URL devolvió 404. Todas las secciones del sidebar fueron accesibles.
