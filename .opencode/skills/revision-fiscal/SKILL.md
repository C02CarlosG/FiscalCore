---
name: revision-fiscal
description: Verifica que cambios en backend/ respetan las reglas del dominio fiscal mexicano — Decimal, RFC regex, bcrypt, lógica SAT de anticipos, tolerancias de conciliación
---

# Skill: revision-fiscal

Revisor automático de dominio fiscal. Invocar después de editar archivos en `backend/`.

## Cuándo usar

Invocar cuando se editen:
- `backend/motor_fiscal.py`
- `backend/cfdi_parser.py`
- `backend/banco_parser.py`
- `backend/routers/conciliacion.py`, `riesgos.py`, `scoring.py`, `emitidos.py`

No es necesario para cambios en auth, perfil, o infraestructura.

## Checklist de verificación

### 1. Precisión financiera — CRÍTICO

Verificar que no se usa `float` para montos monetarios:

```bash
grep -n "float(" backend/motor_fiscal.py backend/cfdi_parser.py | grep -v "# ok"
```

Correcto: `Decimal('0.05')`, `Decimal(str(valor))`, `from decimal import Decimal`
Incorrecto: `float(monto)`, `0.05` en comparaciones de montos, `round(x, 2)`

### 2. Validación RFC — ALTO

El regex canónico del proyecto es:
```python
RFC_REGEX = r'^[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}$'
```

Verificar que toda validación de RFC en el código editado usa este mismo patrón (no variantes inconsistentes). Buscar:

```bash
grep -n "re\.match.*RFC\|RFC.*re\.match\|[A-Z]{3,4}.*\d{6}" backend/*.py backend/routers/*.py
```

### 3. Autenticación — bcrypt directo, nunca passlib

```bash
grep -n "passlib\|from passlib" backend/*.py backend/routers/*.py
```

Si aparece `passlib`, es un error. El proyecto usa `import bcrypt as _bcrypt` directamente.

### 4. Lógica de anticipos SAT — 3 pasos

Si se edita `cfdi_parser.py` o `emitidos.py`, verificar que la lógica de los 3 pasos SAT sigue siendo coherente:

- **Paso 1 (Ingreso A)**: `tipo_comprobante="I"` + `ClaveProdServ=84111506` + `MetodoPago=PUE` + sin `CfdiRelacionados` → `es_anticipo_sat=True`
- **Paso 2 (Ingreso B)**: `tipo_comprobante="I"` + `CfdiRelacionados TipoRelacion=07` → `es_factura_con_anticipo`
- **Paso 3 (Egreso C)**: `tipo_comprobante="E"` + `FormaPago=30` + `CfdiRelacionados → UUID de B` → `aplicaciones_anticipo`

No mezclar TipoRelacion=07 en egresos con la detección de Ingreso A.

### 5. Tolerancias de conciliación

Las tolerancias del motor son invariantes — un cambio aquí afecta scores históricos:

| Constante | Valor correcto |
|-----------|---------------|
| Tolerancia exacta | ±$0.05 MXN |
| Tolerancia porcentual | ±2% |
| Umbral PPD sin REP | 60 días |
| `TOLERANCIA_FECHA_REP` | 5 días |

Si se modifican estas constantes en `motor_fiscal.py`, escalar al usuario antes de continuar.

### 6. Severidades de riesgos — NO modificar pesos

Los pesos del `MotorScoring` son fijos y afectan todos los scores históricos:

```
Crítico: -15, Alto: -8, Medio: -4, Bajo: -1
Conciliación: hasta -20 por baja conciliación
```

Si hay un cambio en estos valores, advertir explícitamente al usuario.

### 7. Tipos de match permitidos

Los valores válidos para `tipo_match` en `conciliaciones` son:
`exacto`, `parcial`, `sin_cfdi`, `sin_movimiento`, `complemento_pago`, `complemento_pago_total`, `complemento_pago_parcial`, `agrupado`, `parcial_multiple`, `heuristico`, `pendiente_rep`, `pagado_parcial`

Si el código introduce un nuevo valor, verificar que también exista la migración SQL correspondiente.

## Formato de reporte

Al finalizar la revisión, reportar en formato conciso:

```
[revision-fiscal] Backend — resultado:
✓ Decimal: OK / ⚠ Posible float en línea X
✓ RFC regex: consistente / ⚠ Variante encontrada en archivo Y
✓ bcrypt: directo / ⚠ passlib detectado
✓ Anticipos SAT: coherente / ⚠ Revisar paso N
✓ Tolerancias: sin cambios / ⚠ CAMBIO DETECTADO — escalar
```
