# Validación end-to-end — Módulo SAT FIEL (Descarga Masiva)

**Fecha:** 2026-04-18  
**Alcance:** Protocolo de validación manual via curl del flujo completo de descarga de CFDIs usando e.firma (FIEL)  
**Período de prueba:** 2026-03-01 → 2026-03-31  
**Tipo:** emitidos (primera prueba)

---

## Contexto

El módulo SAT FIEL fue implementado y corregido (3 bugs: ESTADO_MAP con claves enteras en lugar de strings, UI sin botones Verificar/Descargar, estado final incorrecto cuando cfdi_importados=0). Esta validación confirma que el flujo completo funciona con credenciales reales antes del deploy a Railway.

---

## Prerrequisitos

- Backend corriendo en `http://localhost:8000`
- PostgreSQL accesible (Docker o proceso local)
- Archivos `.cer` y `.key` de la FIEL del contribuyente disponibles localmente
- Contraseña del archivo `.key`
- Una empresa registrada en el sistema cuyo RFC coincida con el RFC del certificado FIEL

---

## Flujo de validación — 6 pasos

### Paso 1 — Login

```bash
curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "TU_EMAIL", "password": "TU_PASSWORD"}' \
  | python -m json.tool
```

Guardar el valor de `access_token` como `TOKEN`.

**Criterio de éxito:** respuesta con `access_token` presente.  
**Señal de fallo:** 401 o error de credenciales.

---

### Paso 2 — Obtener empresa_id

```bash
curl -s http://localhost:8000/api/v1/empresas \
  -H "Authorization: Bearer TOKEN" \
  | python -m json.tool
```

Identificar la empresa cuyo RFC coincide con la FIEL. Guardar su `id` como `EMPRESA_ID`.

**Criterio de éxito:** la empresa aparece en la lista con el RFC correcto.  
**Señal de fallo:** lista vacía o RFC no coincide — registrar la empresa primero.

---

### Paso 3 — Solicitar descarga masiva

```bash
curl -s -X POST http://localhost:8000/api/v1/sat/solicitar \
  -H "Authorization: Bearer TOKEN" \
  -F "empresa_id=EMPRESA_ID" \
  -F "tipo=emitidos" \
  -F "fecha_inicio=2026-03-01" \
  -F "fecha_fin=2026-03-31" \
  -F "cer_file=@/ruta/al/archivo.cer" \
  -F "key_file=@/ruta/al/archivo.key" \
  -F "password=CONTRASEÑA_KEY" \
  | python -m json.tool
```

Guardar `solicitud_id` de la respuesta como `SOLICITUD_ID`.

**Criterio de éxito:** `estado: "solicitado"` + `id_solicitud_sat` con UUID del SAT.  
**Señal de fallo:**
- 422 → FIEL inválida (certificado, llave o contraseña incorrectos)
- 502 → SAT rechazó la solicitud (revisar `detail` para el mensaje del SAT)

---

### Paso 4 — Verificar estado (repetir hasta terminado)

```bash
curl -s -X POST http://localhost:8000/api/v1/sat/solicitudes/SOLICITUD_ID/verificar \
  -H "Authorization: Bearer TOKEN" \
  -F "cer_file=@/ruta/al/archivo.cer" \
  -F "key_file=@/ruta/al/archivo.key" \
  -F "password=CONTRASEÑA_KEY" \
  | python -m json.tool
```

Repetir cada ~30 segundos hasta que `estado` sea `"terminado"`.

**Criterio de éxito:** `estado: "terminado"` + `num_cfdi > 0` + `id_paquetes` con al menos un elemento.  
**Señal de fallo:**
- `estado: "fallo"` → SAT rechazó; revisar `mensaje`
- `num_cfdi: 0` → el período no tiene CFDIs para ese RFC

---

### Paso 5 — Descargar paquetes

Usar los `id_paquetes` obtenidos en el paso 4:

```bash
curl -s -X POST http://localhost:8000/api/v1/sat/solicitudes/SOLICITUD_ID/descargar \
  -H "Authorization: Bearer TOKEN" \
  -F "cer_file=@/ruta/al/archivo.cer" \
  -F "key_file=@/ruta/al/archivo.key" \
  -F "password=CONTRASEÑA_KEY" \
  -F 'id_paquetes=["ID_PAQUETE_1","ID_PAQUETE_2"]' \
  | python -m json.tool
```

**Criterio de éxito:** `"Descarga iniciada en background"` con `paquetes > 0`.  
**Señal de fallo:** 400 (id_paquetes malformado) o 502 (error SAT al descargar).

---

### Paso 6 — Confirmar importación

Esperar ~10 segundos para que el background task complete, luego:

```bash
curl -s "http://localhost:8000/api/v1/sat/solicitudes?empresa_id=EMPRESA_ID" \
  -H "Authorization: Bearer TOKEN" \
  | python -m json.tool
```

**Criterio de éxito:** la solicitud aparece con `estado: "descargado"` y `cfdi_importados > 0`.  
**Señal de fallo:** `estado: "fallo"` con `error_msg` o `cfdi_importados: 0`.

---

## Verificación post-importación (pipeline fiscal)

Confirmar que conciliación, riesgos y scoring corrieron:

```bash
# Dashboard del período
curl -s "http://localhost:8000/api/v1/dashboard/EMPRESA_ID?periodo=2026-03" \
  -H "Authorization: Bearer TOKEN" | python -m json.tool

# CFDIs emitidos del período
curl -s "http://localhost:8000/api/v1/empresas/EMPRESA_ID/emitidos?periodo=2026-03" \
  -H "Authorization: Bearer TOKEN" | python -m json.tool

# Riesgos detectados
curl -s "http://localhost:8000/api/v1/empresas/EMPRESA_ID/riesgos" \
  -H "Authorization: Bearer TOKEN" | python -m json.tool
```

**Criterio de éxito global:** dashboard muestra CFDIs del período 2026-03 con score calculado y riesgos detectados basados en datos reales.

---

## Criterios de éxito consolidados

| Paso | Indicador |
|------|-----------|
| Login | `access_token` presente |
| Empresas | RFC de la FIEL coincide con empresa registrada |
| Solicitar | `id_solicitud_sat` UUID del SAT |
| Verificar | `estado: "terminado"` + `num_cfdi > 0` |
| Descargar | Descarga iniciada en background |
| Listar | `estado: "descargado"` + `cfdi_importados > 0` |
| Pipeline | Dashboard con datos reales del período |
