# Validación end-to-end SAT FIEL Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Validar que el flujo completo de descarga masiva SAT con FIEL funciona con credenciales reales: solicitar → verificar → descargar → importar CFDIs → pipeline fiscal.

**Architecture:** Protocolo de validación manual via curl. Cada tarea ejecuta un endpoint del API y verifica la respuesta. Los valores obtenidos en cada tarea se guardan como variables de entorno para las tareas siguientes.

**Tech Stack:** curl, Python (json.tool para formateo), bash variables

---

## Variables de sesión

Sustituye estos valores antes de comenzar. Se usarán en todas las tareas:

```bash
export CER_PATH="/ruta/absoluta/al/archivo.cer"
export KEY_PATH="/ruta/absoluta/al/archivo.key"
export KEY_PASS="tu_contraseña_key"
export EMAIL="tu_email@ejemplo.com"
export PASSWORD="tu_password_fiscalcore"
```

---

### Tarea 1: Login — obtener JWT

**Archivos:** ninguno (llamada HTTP)

- [ ] **Paso 1: Ejecutar login**

```bash
curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d "{\"email\": \"$EMAIL\", \"password\": \"$PASSWORD\"}" \
  | python -m json.tool
```

- [ ] **Paso 2: Verificar respuesta**

Esperado: HTTP 200 con `access_token` presente en el JSON.

```json
{
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer"
}
```

Si ves `"detail": "Credenciales inválidas"` → verificar email/password en la DB.

- [ ] **Paso 3: Guardar token como variable**

```bash
export TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d "{\"email\": \"$EMAIL\", \"password\": \"$PASSWORD\"}" \
  | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

echo "TOKEN: $TOKEN"
```

Esperado: imprime el JWT sin errores.

---

### Tarea 2: Obtener empresa_id

**Archivos:** ninguno (llamada HTTP)

- [ ] **Paso 1: Listar empresas del contador**

```bash
curl -s http://localhost:8000/api/v1/empresas \
  -H "Authorization: Bearer $TOKEN" \
  | python -m json.tool
```

Esperado: array con al menos una empresa. Identificar la que tenga el RFC que coincide con la FIEL.

```json
[
    {
        "id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
        "rfc": "RFC_DE_LA_FIEL",
        "razon_social": "NOMBRE EMPRESA SA DE CV",
        ...
    }
]
```

Si la lista está vacía → el contador no tiene empresas vinculadas. Revisar `usuario_empresas` en la DB.  
Si el RFC no aparece → registrar la empresa primero desde la UI con la Constancia PDF.

- [ ] **Paso 2: Guardar empresa_id**

```bash
# Reemplaza RFC_DE_LA_FIEL con el RFC real del certificado
export EMPRESA_ID=$(curl -s http://localhost:8000/api/v1/empresas \
  -H "Authorization: Bearer $TOKEN" \
  | python -c "
import sys, json
empresas = json.load(sys.stdin)
match = [e for e in empresas if e['rfc'] == 'RFC_DE_LA_FIEL']
print(match[0]['id'] if match else 'NO_ENCONTRADO')
")

echo "EMPRESA_ID: $EMPRESA_ID"
```

Esperado: imprime un UUID. Si imprime `NO_ENCONTRADO` → ver diagnóstico del paso anterior.

---

### Tarea 3: Solicitar descarga masiva

**Archivos:** ninguno (llamada HTTP)

- [ ] **Paso 1: Enviar solicitud al SAT**

```bash
curl -s -X POST http://localhost:8000/api/v1/sat/solicitar \
  -H "Authorization: Bearer $TOKEN" \
  -F "empresa_id=$EMPRESA_ID" \
  -F "tipo=emitidos" \
  -F "fecha_inicio=2026-03-01" \
  -F "fecha_fin=2026-03-31" \
  -F "cer_file=@$CER_PATH" \
  -F "key_file=@$KEY_PATH" \
  -F "password=$KEY_PASS" \
  | python -m json.tool
```

- [ ] **Paso 2: Verificar respuesta**

Esperado:
```json
{
    "solicitud_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
    "id_solicitud_sat": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
    "estado": "solicitado",
    "mensaje": "Solicitud enviada al SAT. Usa /verificar para consultar el estado."
}
```

Diagnóstico de fallos:
- HTTP 422 → FIEL inválida. Verificar que `.cer` y `.key` correspondan al mismo certificado y que la contraseña sea correcta.
- HTTP 502 con `"Error SAT: ..."` → el SAT rechazó. Leer el `detail` completo. Causas comunes: RFC no coincide con la FIEL, período fuera de rango permitido (SAT permite hasta 5 años atrás), o servicio SAT caído.
- HTTP 404 → `empresa_id` inválido.

- [ ] **Paso 3: Guardar solicitud_id**

```bash
export SOLICITUD_ID=$(curl -s -X POST http://localhost:8000/api/v1/sat/solicitar \
  -H "Authorization: Bearer $TOKEN" \
  -F "empresa_id=$EMPRESA_ID" \
  -F "tipo=emitidos" \
  -F "fecha_inicio=2026-03-01" \
  -F "fecha_fin=2026-03-31" \
  -F "cer_file=@$CER_PATH" \
  -F "key_file=@$KEY_PATH" \
  -F "password=$KEY_PASS" \
  | python -c "import sys,json; d=json.load(sys.stdin); print(d.get('solicitud_id','ERROR'))")

echo "SOLICITUD_ID: $SOLICITUD_ID"
```

Esperado: imprime un UUID local (no el del SAT).

**Nota:** si ya tienes el `solicitud_id` de una solicitud previa en estado `solicitado` o `en_proceso`, puedes exportarlo directamente sin hacer una nueva solicitud:
```bash
export SOLICITUD_ID="uuid-de-solicitud-previa"
```

---

### Tarea 4: Verificar estado (poll hasta terminado)

**Archivos:** ninguno (llamada HTTP, repetir)

- [ ] **Paso 1: Verificar estado una vez**

```bash
curl -s -X POST "http://localhost:8000/api/v1/sat/solicitudes/$SOLICITUD_ID/verificar" \
  -H "Authorization: Bearer $TOKEN" \
  -F "cer_file=@$CER_PATH" \
  -F "key_file=@$KEY_PATH" \
  -F "password=$KEY_PASS" \
  | python -m json.tool
```

- [ ] **Paso 2: Interpretar respuesta**

Casos posibles:

**En proceso (repetir en ~30s):**
```json
{
    "estado": "en_proceso",
    "num_cfdi": 0,
    "num_paquetes": 0,
    "id_paquetes": []
}
```

**Terminado (continuar a Tarea 5):**
```json
{
    "estado": "terminado",
    "num_cfdi": 47,
    "num_paquetes": 1,
    "id_paquetes": ["xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"]
}
```

**Fallo (diagnosticar):**
```json
{
    "estado": "fallo",
    "mensaje": "..."
}
```

- [ ] **Paso 3: Poll automático hasta terminado (opcional)**

```bash
while true; do
  RESP=$(curl -s -X POST "http://localhost:8000/api/v1/sat/solicitudes/$SOLICITUD_ID/verificar" \
    -H "Authorization: Bearer $TOKEN" \
    -F "cer_file=@$CER_PATH" \
    -F "key_file=@$KEY_PATH" \
    -F "password=$KEY_PASS")
  ESTADO=$(echo $RESP | python -c "import sys,json; print(json.load(sys.stdin).get('estado','?'))")
  echo "$(date +%H:%M:%S) — estado: $ESTADO"
  if [ "$ESTADO" = "terminado" ] || [ "$ESTADO" = "fallo" ]; then
    echo $RESP | python -m json.tool
    break
  fi
  sleep 30
done
```

- [ ] **Paso 4: Guardar id_paquetes**

```bash
export ID_PAQUETES=$(curl -s -X POST "http://localhost:8000/api/v1/sat/solicitudes/$SOLICITUD_ID/verificar" \
  -H "Authorization: Bearer $TOKEN" \
  -F "cer_file=@$CER_PATH" \
  -F "key_file=@$KEY_PATH" \
  -F "password=$KEY_PASS" \
  | python -c "import sys,json; print(json.dumps(json.load(sys.stdin).get('id_paquetes',[])))")

echo "ID_PAQUETES: $ID_PAQUETES"
```

Esperado: array JSON con al menos un string, ej: `["abc-123-..."]`

Diagnóstico si `num_cfdi: 0`:
- El RFC no tiene CFDIs emitidos en marzo 2026 → probar con `tipo=recibidos`
- El período está fuera del rango de datos del SAT

---

### Tarea 5: Descargar paquetes

**Archivos:** ninguno (llamada HTTP — dispara background task)

- [ ] **Paso 1: Lanzar descarga**

```bash
curl -s -X POST "http://localhost:8000/api/v1/sat/solicitudes/$SOLICITUD_ID/descargar" \
  -H "Authorization: Bearer $TOKEN" \
  -F "cer_file=@$CER_PATH" \
  -F "key_file=@$KEY_PATH" \
  -F "password=$KEY_PASS" \
  -F "id_paquetes=$ID_PAQUETES" \
  | python -m json.tool
```

- [ ] **Paso 2: Verificar respuesta**

Esperado:
```json
{
    "mensaje": "Descarga iniciada en background",
    "paquetes": 1,
    "solicitud_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
}
```

Diagnóstico de fallos:
- HTTP 400 con `"id_paquetes debe ser un JSON array"` → el valor de `$ID_PAQUETES` no es válido. Verificar con `echo $ID_PAQUETES`.
- HTTP 422 → FIEL inválida (recargar archivos).
- HTTP 502 → error al descargar el ZIP del SAT.

- [ ] **Paso 3: Esperar que el background task complete**

```bash
sleep 15
echo "Background task debe haber completado"
```

La importación de XMLs corre en background. 15 segundos es suficiente para paquetes pequeños (<100 CFDIs). Para paquetes grandes (>500 CFDIs) esperar hasta 60 segundos.

---

### Tarea 6: Confirmar importación en DB

**Archivos:** ninguno (llamada HTTP)

- [ ] **Paso 1: Listar solicitudes de la empresa**

```bash
curl -s "http://localhost:8000/api/v1/sat/solicitudes?empresa_id=$EMPRESA_ID" \
  -H "Authorization: Bearer $TOKEN" \
  | python -m json.tool
```

- [ ] **Paso 2: Verificar estado final**

Buscar la solicitud con `id == $SOLICITUD_ID`. Esperado:

```json
{
    "id": "xxxxxxxx-...",
    "estado": "descargado",
    "num_cfdi": 47,
    "num_paquetes": 1,
    "paquetes_descargados": 1,
    "cfdi_importados": 47,
    "error_msg": null
}
```

Diagnóstico de fallos:
- `estado: "fallo"` con `error_msg` → leer el mensaje. Causas: XMLs corruptos en el ZIP, error de parseo CFDI, fallo de DB.
- `cfdi_importados: 0` con `estado: "fallo"` → ningún XML pudo parsearse. Revisar logs del uvicorn para ver el error específico.
- `estado: "en_proceso"` → el background task aún no terminó, esperar más tiempo.

- [ ] **Paso 3: Revisar logs del backend si hay fallo**

```bash
# En la terminal donde corre uvicorn, buscar líneas con ERROR o WARNING recientes
# El log de _importar_paquetes_bg imprime:
# "Solicitud {id}: {n} CFDIs importados de {m} paquetes"
# "CFDI {uuid} ignorado — errores: [...]"
# "Error parseando XML del paquete {id}: ..."
```

---

### Tarea 7: Verificar pipeline fiscal post-importación

**Archivos:** ninguno (3 llamadas HTTP)

- [ ] **Paso 1: Verificar dashboard del período**

```bash
curl -s "http://localhost:8000/api/v1/dashboard/$EMPRESA_ID?periodo=2026-03" \
  -H "Authorization: Bearer $TOKEN" \
  | python -m json.tool
```

Esperado: objeto con `score`, `bloqueadores`, `acciones`, `conciliacion`. Los datos deben reflejar los CFDIs importados. Si `score` es 100 y no hay riesgos, es posible que no haya movimientos bancarios cargados para conciliar.

- [ ] **Paso 2: Verificar CFDIs emitidos del período**

```bash
curl -s "http://localhost:8000/api/v1/empresas/$EMPRESA_ID/emitidos?periodo=2026-03" \
  -H "Authorization: Bearer $TOKEN" \
  | python -m json.tool
```

Esperado: objeto con `ingresos` (lista de CFDIs tipo I) y `egresos` (tipo E/NC). El total debe coincidir con `cfdi_importados` de la tarea anterior.

- [ ] **Paso 3: Verificar riesgos detectados**

```bash
curl -s "http://localhost:8000/api/v1/empresas/$EMPRESA_ID/riesgos" \
  -H "Authorization: Bearer $TOKEN" \
  | python -m json.tool
```

Esperado: array de detecciones. Puede estar vacío si todos los CFDIs son válidos y no hay movimientos bancarios para conciliar.

- [ ] **Paso 4: Evaluar resultado global**

El flujo SAT FIEL está validado si se cumplen **todos** estos criterios:

| Criterio | Verificación |
|----------|-------------|
| FIEL cargó correctamente | Paso 3 Tarea 3: `estado: "solicitado"` |
| SAT aceptó la solicitud | `id_solicitud_sat` presente (UUID del SAT) |
| SAT terminó el procesamiento | `estado: "terminado"` + `num_cfdi > 0` |
| ESTADO_MAP funciona | Estado en DB es `"terminado"`, no siempre `"en_proceso"` |
| ZIPs descargados | `paquetes_descargados == num_paquetes` |
| XMLs importados | `cfdi_importados > 0` |
| Pipeline corrió | Dashboard muestra datos del período 2026-03 |
| UI funciona (opcional) | Repetir flujo desde TabSAT en el browser |

---

## Árbol de decisión ante fallos

```
Fallo en Tarea 3 (HTTP 422)
  └─ FIEL inválida: verificar que .cer y .key son del mismo titular
     y que la contraseña corresponde al .key

Fallo en Tarea 3 (HTTP 502)
  └─ SAT rechazó: leer detail. Si es "RFC no autorizado" → el RFC de la
     empresa en DB no coincide con el RFC del certificado

Fallo en Tarea 4 (estado: "fallo")
  └─ Leer "mensaje" en la respuesta. Si es error de autenticación SAT
     → la FIEL puede estar vencida o revocada

Fallo en Tarea 4 (num_cfdi: 0)
  └─ El RFC no tiene emitidos en ese período → probar con tipo=recibidos

Fallo en Tarea 6 (cfdi_importados: 0)
  └─ Ver logs uvicorn. Si "CFDI ignorado — errores: [cuadre matemático]"
     → los XMLs del SAT tienen problemas de validación interna
     → ajustar umbral de errores bloqueantes en _importar_paquetes_bg

Fallo en Tarea 7 (dashboard sin datos)
  └─ El pipeline corrió pero no hay movimientos bancarios → cargar
     estado de cuenta bancario para que la conciliación tenga datos
```
