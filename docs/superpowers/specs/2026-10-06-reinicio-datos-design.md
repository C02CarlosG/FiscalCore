# Reiniciar datos de una empresa

Fecha: 2026-10-06. Carril D. Estado: en implementación.
Plan maestro: `2026-10-01-paridad-y-mejoras-roadmap.md` (referencia «Configuración →
Reiniciar»). Diseño aprobado por la coordinación el 2026-10-06, con estos ajustes: solo
el alcance «todo», no borrar solicitudes SAT en curso y pausar la sincronización, lista
exacta de tablas en esta spec y en «Pedidos entre carriles», y 409 si la empresa es muy
grande.

## Objetivo

Que el administrador de una empresa borre sus datos operativos (los que se vuelven a
descargar del SAT o a cargar) para empezar de cero, sin perder la empresa, sus usuarios,
su e.firma, su configuración, sus documentos ni la auditoría. Es destructivo: exige
doble confirmación, re-autenticación y queda auditado.

## Alcance

Entra: alcance «todo» de una empresa. No entra: «solo un ejercicio» (una entrega
posterior: los REP y los anticipos cruzan años y un borrado parcial puede dejar datos
inconsistentes), ni el borrado en segundo plano de empresas grandes.

## Qué se borra (tablas de main al 2026-10-06, en este orden)

| # | Tabla | Filtro | Por qué en este orden |
|---|---|---|---|
| 1 | `recomendaciones` | `empresa_id` | Depende de `detecciones` |
| 2 | `detecciones` | `empresa_id` | Referencia `conciliaciones`, `cfdi` y `movimientos_bancarios` sin cascada |
| 3 | `conciliaciones` | `empresa_id` | Referencia `cfdi` y `movimientos_bancarios` sin cascada |
| 4 | `scoring_fiscal` | `empresa_id` | Calculado de los CFDI |
| 5 | `periodos_procesados` | `empresa_id` | Marcas de proceso: sin borrarlas no se reprocesaría |
| 6 | `iva_ajustes`, `isr_ajustes` | `empresa_id` | Ajustes sobre CFDI que ya no existirán |
| 7 | `diot_operaciones_cfdi`, `diot_terceros_periodo` | `empresa_id` | Clasificación DIOT por CFDI y por periodo |
| 8 | `movimientos_bancarios` | `empresa_id` | Referencia `cfdi` sin cascada |
| 9 | `pagos_cfdi` | `empresa_id` | Cascada: `pagos_impuestos`, `pagos_relaciones`, `pagos_relaciones_impuestos` |
| 10 | `cfdi` | `empresa_id` | Cascada: `cfdi_conceptos`, `cfdi_impuestos`, `cfdi_nominas` (y `cfdi_nomina_conceptos`), `cfdi_pagos_totales` |
| 11 | `sat_solicitudes` | `empresa_id` y `estado IN ('fallo', 'descargado')` | Las terminadas; las en curso se conservan |

Además, en la misma transacción, `sat_sync_config` de la empresa queda `activa = false`
y `estado = 'pausada'`, para que el worker no vuelva a insertar datos a medio borrado.
La respuesta lo informa; se reactiva desde la pantalla del SAT (carril B).

## Qué se conserva

`empresas`, `usuario_empresas`, `invitaciones_empresa`, `empresas_fiel`,
`sat_sync_config` (pausada), `config_isr_empresa`, `isr_config_flujo`,
`validaciones_cfdi_config`, `categorias_movimiento`, `reglas_categorizacion`,
`proveedores`, `declaraciones` (capturadas a mano), `documentos_fiscales`, las
solicitudes SAT en curso (`pendiente`, `solicitado`, `en_proceso`, `terminado`), la
suscripción y **toda la auditoría**. Las solicitudes en curso pueden traer CFDI después
del reinicio: es lo esperado (son la nueva descarga).

Si un carril agrega una tabla con datos por empresa, decide si entra en la lista y
avisa al carril D (pedido en el plan maestro).

## Reglas

| Regla | Cómo se aplica |
|---|---|
| Quién | Solo el administrador de la empresa (rol U1, con la regla del primer vinculado) o el administrador de la plataforma. Un contador recibe 403. Sin acceso a la empresa, la misma respuesta que el resto de la API (403/404) |
| Tamaño | Con más de 50,000 CFDI responde 409: «demasiado grande, se hará en segundo plano en una entrega futura» (evita un timeout a medio borrado) |
| Paso 1: previsualizar | Devuelve los conteos por tabla, la frase de confirmación `REINICIAR <RFC>` y un token aleatorio (`secrets.token_urlsafe(32)`) que vale 10 minutos. El token se guarda solo como SHA-256 |
| Paso 2: confirmar | Exige el token (vigente, sin usar, del mismo usuario y empresa), la frase exacta y la contraseña actual. Cualquier falla: 400/403 sin borrar nada. Límite de 5 intentos por minuto por usuario |
| Ejecución | Una sola transacción: `SELECT … FOR UPDATE` de la empresa y del token, borrado en el orden de la tabla, pausa de la sincronización y marca del token como usado. Si algo falla, no se borra nada. Dos confirmaciones simultáneas con el mismo token: una se ejecuta y la otra recibe 409 |
| Auditoría | `empresa.reiniciar_previsualizar` y `empresa.reiniciar` (conteos borrados, sincronización pausada, `via_admin_plataforma` si aplica). `reinicios_empresa` guarda el historial |

## Datos

Migración `067_reinicios_empresa.sql` (idempotente): `reinicios_empresa (id, empresa_id,
usuario_id, token_sha256 único, alcance 'todo', conteos JSONB, expira_en, usado_en,
borrados JSONB, created_at)`.

## API

| Método y ruta | Qué hace |
|---|---|
| `POST /api/v1/reinicio/empresas/{id}/previsualizar` `{alcance: "todo"}` | `{conteos, total_cfdi, frase, token, expira_en}`; 403 contador, 409 demasiado grande, 422 alcance |
| `POST /api/v1/reinicio/empresas/{id}/confirmar` `{token, frase, contrasena}` | `{borrados, sincronizacion_pausada}`; 400 frase o token inválido o vencido, 403 contraseña o permiso, 409 ya usado o en curso, 429 |

## Pantalla

En la empresa, «Reiniciar datos» (solo administradores): paso 1 con los conteos; paso 2
con la advertencia, la frase a teclear y la contraseña. El botón se habilita solo con la
frase exacta. Al terminar: «Datos reiniciados» con los conteos y el aviso de que la
sincronización quedó pausada.

## Criterios de aceptación

1. Un contador recibe 403 en los dos pasos.
2. Con token vencido, usado, de otro usuario, frase o contraseña incorrecta no se borra
   nada.
3. El reinicio borra exactamente las tablas de la lista para esa empresa; otra empresa no
   cambia; la e.firma, la configuración, los documentos, las declaraciones, los
   proveedores, las solicitudes en curso y la auditoría se conservan; la sincronización
   queda pausada.
4. Con más de 50,000 CFDI, 409 sin token.
5. Dos confirmaciones simultáneas: una 200 y otra 409.
