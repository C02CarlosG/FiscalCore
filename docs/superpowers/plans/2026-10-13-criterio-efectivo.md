# Criterio de efectivo por empresa — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que cada empresa elija entre el criterio de efectivo `legal` (excluye efectivo mayor a $2,000) y `estricto` (excluye todo efectivo) en IVA acreditable y deducciones de ISR.

**Architecture:** Una función pura `umbral(criterio)` devuelve 2000 o 0. Cada evento de IVA/ISR guarda el umbral con el que se construyó (`ev["umbral_efectivo"]`); `motivo_exclusion` lo lee del evento, así que ninguno de sus llamadores cambia. Los loaders leen el criterio de la empresa una vez y lo pasan a los constructores de eventos. Un router nuevo expone `GET`/`PUT` del criterio con auditoría atómica, y un componente compartido lo muestra en las pantallas de IVA e ISR.

**Tech Stack:** Python 3 / FastAPI / psycopg2 / pytest; Next.js + TypeScript + TanStack Query + vitest.

**Spec:** `docs/superpowers/specs/2026-10-13-criterio-efectivo-design.md`

## Global Constraints

- Importes siempre `Decimal`, nunca `float` en cálculo (plan maestro, "Comunes").
- Migración SQL idempotente, numerada **072** (la 071 está reservada en la rama `ui-menu-avatar`), registrada en `backend/db.py::init_db`.
- Todo endpoint nuevo se documenta en `docs/openapi.yaml` (lo exige `backend/tests/test_openapi_sync.py`).
- Un cambio de criterio y su registro en `auditoria` van en la misma transacción: si falla la auditoría, se deshace el cambio.
- Con criterio `legal` el comportamiento actual no cambia: las pruebas existentes pasan sin editarlas.
- Commits Conventional Commit, imperativos, terminados con `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.
- Rama de trabajo: crear desde `main` actualizado (`git switch -c feat/criterio-efectivo main`). No mezclar los cambios sin confirmar que ya existen en el árbol de trabajo (`.gitignore`, `mise.toml`, `frontend/types/api.ts`, renombre de `cierre-periodo`).
- Alcance excluido: Cédula de IVA antigua (`iva.py`, `deducciones.py`) y la tarjeta de efectivo de Validaciones siguen con la regla legal; se documenta, no se parametriza.

## Review Focus

1. **Efectivo exactamente en el umbral ($2,000.00)**: con `legal` NO se excluye (la regla es "mayor a"); con `estricto` sí. Pruebas en Tareas 3 y 4.
2. **Pago en efectivo de una factura PPD (REP) en moneda extranjera**: el monto se mide en pesos; con `estricto` cualquier monto positivo se excluye. Prueba en Tarea 3.
3. **Nota de crédito recibida de un CFDI excluido solo por `estricto`**: hereda `original_no_acreditable` bajo `estricto` y NO bajo `legal` si el original era de $1,000 en efectivo. Prueba en Tarea 3.
4. **Valor de criterio inválido o `NULL` en la API**: 422, nunca se asume `legal` en silencio. Prueba en Tarea 6.
5. **Usuario sin rol de administrador intenta cambiarlo, o empresa ajena**: 403 sin escribir nada. Prueba en Tarea 6.
6. **Retención de IVA de una compra en efectivo bajo `estricto`**: se sigue enterando (LIVA 1-A). Prueba en Tarea 3.

---

## File Structure

| Archivo | Responsabilidad |
|---|---|
| `backend/criterio_efectivo.py` (nuevo) | Constantes, `validar`, `umbral`, `leer`, `guardar` (con auditoría). Sin FastAPI. |
| `backend/routers/criterio_efectivo.py` (nuevo) | `GET`/`PUT /api/v1/empresas/{id}/criterio-efectivo`, permisos. |
| `database/migrations/072_criterio_efectivo.sql` (nuevo) | Columna `empresas.criterio_efectivo` + CHECK. |
| `backend/iva_flujo.py` (mod.) | Umbral en eventos y exclusión de IVA acreditable. |
| `backend/isr_flujo.py` (mod.) | Umbral en eventos y exclusión de deducciones. |
| `backend/iva_flujo_datos.py`, `backend/isr_flujo_datos.py` (mod.) | Leen el criterio y lo pasan a los motores. |
| `backend/routers/iva_flujo.py`, `backend/routers/isr_flujo.py` (mod.) | Respuesta de resumen incluye `criterio_efectivo`. |
| `backend/db.py`, `backend/main_api.py`, `docs/openapi.yaml` (mod.) | Registro de migración, router y documentación. |
| `frontend/hooks/useCriterioEfectivo.ts` (nuevo) | Consulta y mutación del criterio. |
| `frontend/components/shared/CriterioEfectivo.tsx` (nuevo) | Selector + insignia. |
| `frontend/components/iva-flujo/IvaFlujoPantalla.tsx`, `frontend/components/isr-flujo/IsrFlujoPantalla.tsx` (mod.) | Montan el componente. |

---

### Task 1: Módulo puro `criterio_efectivo` (validar y umbral)

**Files:**
- Create: `backend/criterio_efectivo.py`
- Test: `backend/tests/test_criterio_efectivo.py`

**Interfaces:**
- Produces: `CRITERIOS = ("legal", "estricto")`, `CRITERIO_POR_DEFECTO = "legal"`, `UMBRAL_LEGAL = Decimal("2000")`, `UMBRAL_ESTRICTO = Decimal("0")`, `class CriterioInvalido(ValueError)`, `validar(valor) -> str`, `umbral(criterio: str) -> Decimal`.

- [ ] **Step 1: Write the failing test**

```python
"""Criterio de efectivo por empresa (spec 2026-10-13): validación y umbral. Sin DB."""
from decimal import Decimal

import pytest

from backend import criterio_efectivo as c


def test_umbral_legal_es_2000():
    assert c.umbral("legal") == Decimal("2000")


def test_umbral_estricto_es_cero():
    assert c.umbral("estricto") == Decimal("0")


@pytest.mark.parametrize("valor", [None, "", "Legal", "ESTRICTO", "otro", 3, ["legal"], {"c": "legal"}])
def test_validar_rechaza_valores_fuera_del_catalogo(valor):
    with pytest.raises(c.CriterioInvalido):
        c.validar(valor)


def test_umbral_no_asume_legal_con_valor_desconocido():
    with pytest.raises(c.CriterioInvalido):
        c.umbral("laxo")


def test_por_defecto_es_legal():
    assert c.CRITERIO_POR_DEFECTO == "legal"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest backend/tests/test_criterio_efectivo.py -v`
Expected: FAIL con `ImportError: cannot import name 'criterio_efectivo'`.

- [ ] **Step 3: Write minimal implementation**

```python
"""Criterio de efectivo por empresa (spec 2026-10-13-criterio-efectivo-design).

``legal``: el pago en efectivo (forma de pago 01) no se acredita ni se deduce solo si supera $2,000
(LIVA 5-III, LISR 27-III). ``estricto``: ningún pago en efectivo se acredita ni se deduce (criterio de la
plataforma de referencia). El resto del cálculo no cambia: el umbral 0 hace que la comparación existente
«efectivo y monto mayor al umbral» excluya cualquier efectivo mayor a cero.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

CRITERIOS = ("legal", "estricto")
CRITERIO_POR_DEFECTO = "legal"
UMBRAL_LEGAL = Decimal("2000")
UMBRAL_ESTRICTO = Decimal("0")


class CriterioInvalido(ValueError):
    """El valor no es uno de ``CRITERIOS``."""


def validar(valor: Any) -> str:
    if not isinstance(valor, str) or valor not in CRITERIOS:
        raise CriterioInvalido(f"criterio de efectivo inválido; valores permitidos: {', '.join(CRITERIOS)}")
    return valor


def umbral(criterio: Any) -> Decimal:
    """Monto en efectivo por encima del cual un pago no se acredita ni se deduce."""
    return UMBRAL_ESTRICTO if validar(criterio) == "estricto" else UMBRAL_LEGAL
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest backend/tests/test_criterio_efectivo.py -v`
Expected: PASS (5 grupos de pruebas).

- [ ] **Step 5: Commit**

```bash
git add backend/criterio_efectivo.py backend/tests/test_criterio_efectivo.py
git commit -m "feat: módulo criterio_efectivo con validación y umbral"
```

---

### Task 2: Migración 072 y registro en `init_db`

**Files:**
- Create: `database/migrations/072_criterio_efectivo.sql`, `backend/tests/test_migracion_072.py`
- Modify: `backend/db.py` (después de la llamada a `067_reinicios_empresa.sql`, antes de `_seed_admin()`)

**Interfaces:**
- Produces: columna `empresas.criterio_efectivo TEXT NOT NULL DEFAULT 'legal'` con CHECK `IN ('legal','estricto')`.

- [ ] **Step 1: Write the failing test** (requiere Postgres; ver memoria del proyecto sobre Postgres desechable si Docker no está accesible)

```python
"""Migración 072: criterio de efectivo por empresa. Requiere Postgres."""
import psycopg2
import pytest

from backend.tests.conftest import db_disponible

pytestmark = [pytest.mark.db, pytest.mark.skipif(not db_disponible(), reason="Postgres no disponible (docker compose up -d db)")]


def test_072_idempotente_default_legal_y_check():
    from backend import db

    db.init_db()
    db.init_db()
    empresa = db.execute("INSERT INTO empresas (rfc, razon_social) VALUES ('RCE010101AB1', 'M072') RETURNING id",
                         returning=True)["id"]
    try:
        fila = db.query_one("SELECT criterio_efectivo FROM empresas WHERE id = %s", (empresa,))
        assert fila["criterio_efectivo"] == "legal"
        db.execute("UPDATE empresas SET criterio_efectivo = 'estricto' WHERE id = %s", (empresa,))
        with pytest.raises(psycopg2.errors.CheckViolation):
            db.execute("UPDATE empresas SET criterio_efectivo = 'laxo' WHERE id = %s", (empresa,))
        with pytest.raises(psycopg2.errors.NotNullViolation):
            db.execute("UPDATE empresas SET criterio_efectivo = NULL WHERE id = %s", (empresa,))
    finally:
        db.execute("DELETE FROM empresas WHERE id = %s", (empresa,))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest backend/tests/test_migracion_072.py -v -m db`
Expected: FAIL con `UndefinedColumn: column "criterio_efectivo" ... does not exist`. (Si Postgres no está disponible la prueba se omite: levantar uno primero.)

- [ ] **Step 3: Write the migration and register it**

`database/migrations/072_criterio_efectivo.sql`:

```sql
-- 072: criterio de efectivo por empresa (spec 2026-10-13-criterio-efectivo-design).
-- 'legal': efectivo mayor a $2,000 no se acredita ni se deduce (LIVA 5-III, LISR 27-III).
-- 'estricto': ningún pago en efectivo se acredita ni se deduce.
-- Idempotente: se puede ejecutar en cada arranque.

ALTER TABLE empresas ADD COLUMN IF NOT EXISTS criterio_efectivo TEXT NOT NULL DEFAULT 'legal';

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'empresas_criterio_efectivo_check') THEN
        ALTER TABLE empresas
            ADD CONSTRAINT empresas_criterio_efectivo_check CHECK (criterio_efectivo IN ('legal', 'estricto'));
    END IF;
END $$;
```

En `backend/db.py`, después de la llamada a la 067:

```python
        # 072 es idempotente — criterio de efectivo por empresa: legal (> $2,000) o estricto (todo efectivo)
        _run_sql_file("072_criterio_efectivo.sql")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest backend/tests/test_migracion_072.py -v -m db`
Expected: PASS.

- [ ] **Step 5: Validar la migración y commit**

Invocar el agente `migration-validator` sobre `database/migrations/072_criterio_efectivo.sql` y resolver lo que reporte.

```bash
git add database/migrations/072_criterio_efectivo.sql backend/db.py backend/tests/test_migracion_072.py
git commit -m "feat: migración 072 criterio de efectivo por empresa"
```

---

### Task 3: Motor de IVA — el evento lleva su umbral

**Files:**
- Modify: `backend/iva_flujo.py` (`_evento` ~132, `_no_acreditable_por_si_mismo` ~216, `_marcas_por_originales` ~223, `eventos_de_documento` ~241, `eventos_de_pago` ~378, `evento_de_pago` ~404, `motivo_exclusion` ~417)
- Test: `backend/tests/test_iva_flujo_criterio_efectivo.py`

**Interfaces:**
- Consumes: `UMBRAL_EFECTIVO` (ya definido en `iva_flujo.py`, `Decimal("2000")`).
- Produces: `eventos_de_documento(doc, rfc, umbral_efectivo=UMBRAL_EFECTIVO)`, `eventos_de_pago(pago, doc, rfc, umbral_efectivo=UMBRAL_EFECTIVO)`, `evento_de_pago(pago, doc, rfc, umbral_efectivo=UMBRAL_EFECTIVO)`; cada evento trae `ev["umbral_efectivo"]: Decimal`; `motivo_exclusion(ev)` lo usa.

- [ ] **Step 1: Write the failing tests**

Los ayudantes `doc`, `recibido`, `pago`, `tras` salen de `backend/tests/test_iva_flujo.py` (copiarlos al archivo nuevo tal cual, líneas 1-60, para que sea autocontenido). Pruebas:

```python
"""Criterio de efectivo en IVA base flujo (spec 2026-10-13). Sin DB."""
from datetime import date
from decimal import Decimal

from backend import iva_flujo as f

D = Decimal
LEGAL, ESTRICTO = D("2000"), D("0")

# --- copiar aquí de test_iva_flujo.py: RFC, OTRO, PROV, imp, tras, doc, recibido, pago ---


def _acreditable(evs):
    return [e for e in evs if e["direccion"] == "acreditable"]


def test_compra_de_1000_en_efectivo_legal_se_considera_y_estricto_se_excluye():
    c = recibido("R1", forma_pago="01", total=D("1160"), subtotal=D("1000"))
    # total 1160 <= 2000: con legal cuenta
    ev_legal = _acreditable(f.eventos_de_documento(c, RFC, LEGAL))[0]
    ev_estricto = _acreditable(f.eventos_de_documento(c, RFC, ESTRICTO))[0]
    assert f.motivo_exclusion(ev_legal) is None
    assert f.motivo_exclusion(ev_estricto) == "efectivo"


def test_efectivo_exactamente_en_el_umbral_no_se_excluye_con_legal():
    c = recibido("R2", forma_pago="01", total=D("2000.00"), subtotal=D("1724.14"), iva_trasladado=D("275.86"))
    ev = _acreditable(f.eventos_de_documento(c, RFC, LEGAL))[0]
    assert f.motivo_exclusion(ev) is None
    ev = _acreditable(f.eventos_de_documento(c, RFC, ESTRICTO))[0]
    assert f.motivo_exclusion(ev) == "efectivo"


def test_efectivo_de_2000_01_se_excluye_con_ambos_criterios():
    c = recibido("R3", forma_pago="01", total=D("2000.01"))
    for umbral in (LEGAL, ESTRICTO):
        ev = _acreditable(f.eventos_de_documento(c, RFC, umbral))[0]
        assert f.motivo_exclusion(ev) == "efectivo"


def test_transferencia_nunca_se_excluye_por_efectivo():
    c = recibido("R4", forma_pago="03", total=D("1160"))
    ev = _acreditable(f.eventos_de_documento(c, RFC, ESTRICTO))[0]
    assert f.motivo_exclusion(ev) is None


def test_el_criterio_no_aplica_a_lo_trasladado():
    c = doc("U1", forma_pago="01", total=D("1160"))      # emitida por la empresa, cobrada en efectivo
    ev = [e for e in f.eventos_de_documento(c, RFC, ESTRICTO) if e["direccion"] == "trasladado"][0]
    assert f.motivo_exclusion(ev) is None


def test_sin_argumento_el_umbral_es_el_legal():
    c = recibido("R5", forma_pago="01", total=D("1160"))
    ev = _acreditable(f.eventos_de_documento(c, RFC))[0]
    assert ev["umbral_efectivo"] == LEGAL
    assert f.motivo_exclusion(ev) is None


def test_pago_en_efectivo_de_factura_ppd_sigue_el_criterio():
    c = recibido("R6", metodo_pago="PPD", forma_pago="99", total=D("1160"))
    p = pago("R6", importe="580", forma_pago_p="01")
    ev_l = _acreditable(f.eventos_de_pago(p, c, RFC, LEGAL))[0]
    ev_e = _acreditable(f.eventos_de_pago(p, c, RFC, ESTRICTO))[0]
    assert f.motivo_exclusion(ev_l) is None
    assert f.motivo_exclusion(ev_e) == "efectivo"


def test_nota_de_credito_de_un_original_en_efectivo_hereda_motivo_solo_con_estricto():
    original = recibido("O1", forma_pago="01", total=D("1160"))
    nota = recibido("N1", tipo_comprobante="E", forma_pago="03", total=D("116"), relacionados_info=[original])
    ev_l = _acreditable(f.eventos_de_documento(nota, RFC, LEGAL))[0]
    ev_e = _acreditable(f.eventos_de_documento(nota, RFC, ESTRICTO))[0]
    assert "original_no_acreditable" not in ev_l["marcas"]
    assert "original_no_acreditable" in ev_e["marcas"]
    assert f.motivo_exclusion(ev_e) == "original_no_acreditable"


def test_retencion_de_iva_de_compra_en_efectivo_se_sigue_enterando_con_estricto():
    c = recibido("R7", forma_pago="01", total=D("1000"), iva_retenido=D("106.67"))
    ev = _acreditable(f.eventos_de_documento(c, RFC, ESTRICTO))[0]
    assert f.motivo_exclusion(ev) == "efectivo"
    assert "efectivo" in f.MOTIVOS_QUE_CONSERVAN_RETENCION
```

> Nota para quien ejecute: los argumentos exactos de `pago(...)` (p. ej. `forma_pago_p`) y la forma de `relacionados_info` salen de `test_iva_flujo.py`; si algún nombre difiere, ajustar la llamada, no la expectativa.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest backend/tests/test_iva_flujo_criterio_efectivo.py -v`
Expected: FAIL con `TypeError: eventos_de_documento() takes 2 positional arguments but 3 were given`.

- [ ] **Step 3: Implement**

En `_evento` agregar al diccionario devuelto (junto a `"marcas": marcas,`):

```python
        "umbral_efectivo": extra.get("umbral_efectivo", UMBRAL_EFECTIVO),
```

`_no_acreditable_por_si_mismo` y `_marcas_por_originales`:

```python
def _no_acreditable_por_si_mismo(rel: dict, umbral_efectivo: Decimal = UMBRAL_EFECTIVO) -> bool:
    """El CFDI relacionado nunca se acreditó (efectivo mayor al umbral o uso sin efectos)."""
    tc = _tc_documento({"moneda": rel.get("moneda"), "tipo_cambio": rel.get("tipo_cambio")}) or UNO
    efectivo = rel.get("forma_pago") == "01" and _dec(rel.get("total")) * tc > umbral_efectivo
    return efectivo or rel.get("uso_cfdi") in USOS_NO_ACREDITABLES


def _marcas_por_originales(doc: dict, direccion: str, umbral_efectivo: Decimal = UMBRAL_EFECTIVO) -> set:
    ...  # cuerpo igual; en la última condición usar:
    if direccion == "acreditable" and any(_no_acreditable_por_si_mismo(r, umbral_efectivo) for r in relacionados):
        marcas.add("original_no_acreditable")
    return marcas
```

`eventos_de_documento(doc, rfc, umbral_efectivo=UMBRAL_EFECTIVO)`: pasar `marcas |= _marcas_por_originales(doc, direccion, umbral_efectivo)` y `umbral_efectivo=umbral_efectivo` en la llamada a `_evento(...)`.

`eventos_de_pago(pago, doc, rfc, umbral_efectivo=UMBRAL_EFECTIVO)`: agregar `umbral_efectivo=umbral_efectivo` a la llamada a `_evento(...)`. `evento_de_pago(pago, doc, rfc, umbral_efectivo=UMBRAL_EFECTIVO)` lo reenvía.

`motivo_exclusion`:

```python
    if ev["direccion"] == "acreditable" and ev["origen"] != "notas_credito":
        monto = ev["monto_efecto"] if ev.get("monto_efecto") is not None else ev["total_documento"]
        if ev.get("forma_pago") == "01" and monto > ev.get("umbral_efectivo", UMBRAL_EFECTIVO):
            return "efectivo"
```

- [ ] **Step 4: Run tests to verify they pass, plus la suite existente**

Run: `python -m pytest backend/tests/test_iva_flujo_criterio_efectivo.py backend/tests/test_iva_flujo.py backend/tests/test_iva_flujo_contraparte.py backend/tests/test_iva_flujo_exportacion.py -v`
Expected: PASS (las existentes sin editar).

- [ ] **Step 5: Commit**

```bash
git add backend/iva_flujo.py backend/tests/test_iva_flujo_criterio_efectivo.py
git commit -m "feat: umbral de efectivo configurable en el motor de IVA flujo"
```

---

### Task 4: Motor de ISR — el evento lleva su umbral

**Files:**
- Modify: `backend/isr_flujo.py` (`_evento` ~79, `_no_deducible_por_si_mismo` ~105, `_marcas_de_deduccion` ~113, `_marcas_de_egreso` ~122, `eventos_de_documento` ~134, `eventos_de_pago` ~162, `motivo_exclusion` ~234)
- Test: `backend/tests/test_isr_flujo_criterio_efectivo.py`

**Interfaces:**
- Consumes: `UMBRAL_EFECTIVO` de `isr_flujo.py`.
- Produces: `eventos_de_documento(doc, rfc, umbral_efectivo=UMBRAL_EFECTIVO)`, `eventos_de_pago(pago, doc, rfc, umbral_efectivo=UMBRAL_EFECTIVO)`; `ev["umbral_efectivo"]`; `motivo_exclusion(ev)` lo usa; la marca `efectivo_hasta_umbral` solo se emite si el umbral es mayor que 0.

- [ ] **Step 1: Write the failing tests**

Copiar de `backend/tests/test_isr_flujo.py` los ayudantes de documentos y pagos (leer sus primeras ~50 líneas y reutilizar `doc`/`recibido`/`pago` con los mismos nombres). Pruebas:

```python
"""Criterio de efectivo en ISR base flujo (spec 2026-10-13). Sin DB."""
from decimal import Decimal

from backend import isr_flujo as f

D = Decimal
LEGAL, ESTRICTO = D("2000"), D("0")

# --- copiar aquí los ayudantes de test_isr_flujo.py (RFC, doc, recibido, pago) ---


def _deduccion(evs):
    return [e for e in evs if e["lado"] == "deduccion"]


def test_compra_en_efectivo_de_1000_se_deduce_con_legal_y_no_con_estricto():
    c = recibido("R1", forma_pago="01", total=D("1000"), subtotal=D("862.07"))
    assert f.motivo_exclusion(_deduccion(f.eventos_de_documento(c, RFC, LEGAL))[0]) is None
    assert f.motivo_exclusion(_deduccion(f.eventos_de_documento(c, RFC, ESTRICTO))[0]) == "efectivo"


def test_efectivo_exactamente_en_2000_se_deduce_con_legal():
    c = recibido("R2", forma_pago="01", total=D("2000.00"))
    assert f.motivo_exclusion(_deduccion(f.eventos_de_documento(c, RFC, LEGAL))[0]) is None
    assert f.motivo_exclusion(_deduccion(f.eventos_de_documento(c, RFC, ESTRICTO))[0]) == "efectivo"


def test_efectivo_mayor_a_2000_se_excluye_con_ambos():
    c = recibido("R3", forma_pago="01", total=D("2000.01"))
    for umbral in (LEGAL, ESTRICTO):
        assert f.motivo_exclusion(_deduccion(f.eventos_de_documento(c, RFC, umbral))[0]) == "efectivo"


def test_marca_efectivo_hasta_umbral_solo_con_umbral_positivo():
    c = recibido("R4", forma_pago="01", total=D("1000"))
    assert "efectivo_hasta_umbral" in _deduccion(f.eventos_de_documento(c, RFC, LEGAL))[0]["marcas"]
    assert "efectivo_hasta_umbral" not in _deduccion(f.eventos_de_documento(c, RFC, ESTRICTO))[0]["marcas"]


def test_ingresos_cobrados_en_efectivo_no_se_afectan():
    c = doc("U1", forma_pago="01", total=D("1000"))
    ev = [e for e in f.eventos_de_documento(c, RFC, ESTRICTO) if e["lado"] == "ingreso"][0]
    assert f.motivo_exclusion(ev) is None


def test_pago_en_efectivo_de_factura_ppd_sigue_el_criterio():
    c = recibido("R5", metodo_pago="PPD", forma_pago="99", total=D("1160"))
    p = pago("R5", importe="580", forma_pago_p="01")
    ev_l = _deduccion(f.eventos_de_pago(p, c, RFC, LEGAL))[0]
    ev_e = _deduccion(f.eventos_de_pago(p, c, RFC, ESTRICTO))[0]
    assert f.motivo_exclusion(ev_l) is None
    assert f.motivo_exclusion(ev_e) == "efectivo"


def test_devolucion_de_original_en_efectivo_hereda_motivo_solo_con_estricto():
    original = recibido("O1", forma_pago="01", total=D("1000"))
    nota = recibido("N1", tipo_comprobante="E", forma_pago="03", total=D("100"), relacionados_info=[original])
    ev_l = _deduccion(f.eventos_de_documento(nota, RFC, LEGAL))[0]
    ev_e = _deduccion(f.eventos_de_documento(nota, RFC, ESTRICTO))[0]
    assert "original_no_deducible" not in ev_l["marcas"]
    assert "original_no_deducible" in ev_e["marcas"]


def test_sin_argumento_el_umbral_es_el_legal():
    c = recibido("R6", forma_pago="01", total=D("1000"))
    assert _deduccion(f.eventos_de_documento(c, RFC))[0]["umbral_efectivo"] == LEGAL
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest backend/tests/test_isr_flujo_criterio_efectivo.py -v`
Expected: FAIL con `TypeError ... takes 2 positional arguments but 3 were given`.

- [ ] **Step 3: Implement**

- `_evento`: agregar `"umbral_efectivo": extra.get("umbral_efectivo", UMBRAL_EFECTIVO),` al diccionario devuelto.
- `_no_deducible_por_si_mismo(rel, umbral_efectivo=UMBRAL_EFECTIVO)`: cambiar `> UMBRAL_EFECTIVO` por `> umbral_efectivo`.
- `_marcas_de_deduccion(doc, marcas, forma_pago, monto, umbral_efectivo=UMBRAL_EFECTIVO)`:

```python
    if umbral_efectivo > 0 and forma_pago == "01" and monto <= umbral_efectivo:
        marcas.add("efectivo_hasta_umbral")
```

- `_marcas_de_egreso(doc, lado, umbral_efectivo=UMBRAL_EFECTIVO)`: pasar el umbral a `_no_deducible_por_si_mismo(r, umbral_efectivo)`.
- `eventos_de_documento(doc, rfc, umbral_efectivo=UMBRAL_EFECTIVO)`: pasar el umbral a `_marcas_de_egreso(...)`, a `_marcas_de_deduccion(...)` y `umbral_efectivo=umbral_efectivo` a `_evento(...)`.
- `eventos_de_pago(pago, doc, rfc, umbral_efectivo=UMBRAL_EFECTIVO)`: pasar el umbral a `_marcas_de_deduccion(...)` y a `_evento(...)`.
- `motivo_exclusion`: `if ev.get("forma_pago") == "01" and monto > ev.get("umbral_efectivo", UMBRAL_EFECTIVO):`.

- [ ] **Step 4: Run tests to verify they pass, plus la suite existente**

Run: `python -m pytest backend/tests/test_isr_flujo_criterio_efectivo.py backend/tests/test_isr_flujo.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/isr_flujo.py backend/tests/test_isr_flujo_criterio_efectivo.py
git commit -m "feat: umbral de efectivo configurable en el motor de ISR flujo"
```

---

### Task 5: Los loaders leen el criterio de la empresa

**Files:**
- Modify: `backend/criterio_efectivo.py` (agregar `leer`), `backend/iva_flujo_datos.py` (`_cargar`, líneas ~135-141), `backend/isr_flujo_datos.py` (`cargar_eventos`, líneas ~96-100)
- Test: `backend/tests/test_criterio_efectivo_loaders.py`, `backend/tests/test_e2e_criterio_efectivo.py` (db)

**Interfaces:**
- Consumes: `criterio_efectivo.umbral`, `eventos_de_documento(..., umbral_efectivo)`, `eventos_de_pago(..., umbral_efectivo)` (Tareas 1, 3, 4).
- Produces: `criterio_efectivo.leer(empresa_id: str) -> str`. `cargar_eventos` / `cargar_eventos_ejercicio` conservan su firma.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_criterio_efectivo_loaders.py` (sin DB, con `db` mockeado):

```python
"""Los loaders pasan el umbral de la empresa a los motores. Sin DB."""
from datetime import date
from decimal import Decimal

from backend import criterio_efectivo, iva_flujo_datos, isr_flujo_datos

D = Decimal
RFC = "AAA010101AAA"


def _compra(uuid="R1"):
    return dict(uuid=uuid, tipo_comprobante="I", metodo_pago="PUE", forma_pago="01", uso_cfdi="G03", estado="vigente",
                es_anticipo_sat=False, rfc_emisor="PRO010101AAA", nombre_emisor="PROV", rfc_receptor=RFC,
                nombre_receptor="EMP", fecha_emision=date(2026, 10, 1), subtotal=D("862.07"), descuento=D("0"),
                total=D("1000"), iva_trasladado=D("137.93"), iva_retenido=D("0"), isr_retenido=D("0"),
                moneda="MXN", tipo_cambio=D("1"), impuestos=[], no_objeto=D("0"), relacionados_info=[])


def _fake_query_all(docs):
    llamadas = []

    def fake(sql, params=None):
        llamadas.append(sql)
        return docs if len(llamadas) == 1 else []
    return fake


def test_leer_devuelve_el_criterio_de_la_empresa(monkeypatch):
    monkeypatch.setattr(criterio_efectivo.db, "query_one", lambda *a, **k: {"criterio_efectivo": "estricto"})
    assert criterio_efectivo.leer("e1") == "estricto"


def test_leer_sin_empresa_devuelve_el_valor_por_defecto(monkeypatch):
    monkeypatch.setattr(criterio_efectivo.db, "query_one", lambda *a, **k: None)
    assert criterio_efectivo.leer("e1") == "legal"


def test_iva_cargar_pasa_el_umbral_estricto(monkeypatch):
    monkeypatch.setattr(iva_flujo_datos.criterio_efectivo, "leer", lambda e: "estricto")
    monkeypatch.setattr(iva_flujo_datos.db, "query_all", _fake_query_all([_compra()]))
    eventos = iva_flujo_datos.cargar_eventos("e1", RFC, "2026-10", {})
    ev = [e for e in eventos if e["direccion"] == "acreditable"][0]
    assert ev["umbral_efectivo"] == D("0")


def test_iva_cargar_con_legal_conserva_2000(monkeypatch):
    monkeypatch.setattr(iva_flujo_datos.criterio_efectivo, "leer", lambda e: "legal")
    monkeypatch.setattr(iva_flujo_datos.db, "query_all", _fake_query_all([_compra()]))
    ev = [e for e in iva_flujo_datos.cargar_eventos("e1", RFC, "2026-10", {}) if e["direccion"] == "acreditable"][0]
    assert ev["umbral_efectivo"] == D("2000")


def test_isr_cargar_pasa_el_umbral_estricto(monkeypatch):
    monkeypatch.setattr(isr_flujo_datos.criterio_efectivo, "leer", lambda e: "estricto")
    monkeypatch.setattr(isr_flujo_datos.db, "query_all", _fake_query_all([_compra()]))
    monkeypatch.setattr(isr_flujo_datos, "_cargar_nominas", lambda *a: [])
    ev = [e for e in isr_flujo_datos.cargar_eventos("e1", RFC, "2026-10") if e["lado"] == "deduccion"][0]
    assert ev["umbral_efectivo"] == D("0")
```

> Los dos `query_all` de los loaders son: 1.º documentos, 2.º pagos (confirmado leyendo `iva_flujo_datos._cargar` e `isr_flujo_datos.cargar_eventos`). Si un loader agrega una consulta antes de la de documentos, ajustar `_fake_query_all`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest backend/tests/test_criterio_efectivo_loaders.py -v`
Expected: FAIL con `AttributeError: module 'backend.criterio_efectivo' has no attribute 'db'` / `'leer'`.

- [ ] **Step 3: Implement**

En `backend/criterio_efectivo.py` agregar:

```python
from . import db


def leer(empresa_id: str) -> str:
    """Criterio vigente de la empresa; ``legal`` si la empresa no existe."""
    fila = db.query_one("SELECT criterio_efectivo FROM empresas WHERE id = %s", (empresa_id,))
    return fila["criterio_efectivo"] if fila else CRITERIO_POR_DEFECTO
```

En `iva_flujo_datos.py` cambiar `from . import db, iva_flujo` por `from . import criterio_efectivo, db, iva_flujo` y, antes de construir los eventos en `_cargar`:

```python
    umbral = criterio_efectivo.umbral(criterio_efectivo.leer(empresa_id))
    eventos = [e for d in docs for e in iva_flujo.eventos_de_documento(d, rfc, umbral)]
    ...
        nuevos = iva_flujo.eventos_de_pago(p, doc, rfc, umbral)
```

En `isr_flujo_datos.py` igual (`from . import criterio_efectivo, db, isr_flujo`):

```python
    umbral = criterio_efectivo.umbral(criterio_efectivo.leer(empresa_id))
    eventos = [e for d in docs for e in isr_flujo.eventos_de_documento(d, rfc, umbral)]
    ...
            eventos.extend(isr_flujo.eventos_de_pago(p, doc, rfc, umbral))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest backend/tests/test_criterio_efectivo_loaders.py backend/tests/test_criterio_efectivo.py -v`
Expected: PASS.

- [ ] **Step 5: Prueba E2E con Postgres (caso COPLASUR)**

Crear `backend/tests/test_e2e_criterio_efectivo.py` (marcada `db`, mismo encabezado `pytestmark` que `test_migracion_067.py`). Seguir el patrón de siembra de `backend/tests/test_e2e_iva_flujo.py` (leer sus primeras ~80 líneas y reutilizar sus ayudantes de inserción de empresa y CFDI). Sembrar la empresa, una factura recibida de contado por cada una de las 9 compras de octubre de 2026 (IVA: 224.13, 135.42, 203.19, 158.02, 240.03, 56.43, 255.86, 204.76, 94.82; forma de pago `01`; totales 1655.00, 1000.00, 1500.39, 1145.65, 1740.20, 409.14, 1855.00, 1484.50, 700.00) y una de $586.50 + IVA 93.84 por transferencia (`03`). Afirmar:

```python
def test_coplasur_octubre_diferencia_entre_criterios_es_1572_66():
    # legal: acreditable = 93.84 + 1572.66 ; estricto: acreditable = 93.84
    resumen_legal = _resumen(empresa, "2026-10")           # criterio por defecto
    db.execute("UPDATE empresas SET criterio_efectivo = 'estricto' WHERE id = %s", (empresa,))
    resumen_estricto = _resumen(empresa, "2026-10")
    dif = resumen_legal["acreditable"]["iva_total"] - resumen_estricto["acreditable"]["iva_total"]
    assert round(dif, 2) == 1572.66
    assert round(resumen_estricto["acreditable"]["iva_total"], 2) == 93.84
```

donde `_resumen` llama a `iva_flujo_datos.cargar_eventos` + `iva_flujo.resumen` y devuelve la sección `acreditable` (revisar la forma exacta del resumen en `test_e2e_iva_flujo.py` y usar sus mismas claves).

Run: `python -m pytest backend/tests/test_e2e_criterio_efectivo.py -v -m db`
Expected: PASS (suma de IVA de las 9 = 1,572.66).

- [ ] **Step 6: Commit**

```bash
git add backend/criterio_efectivo.py backend/iva_flujo_datos.py backend/isr_flujo_datos.py backend/tests/test_criterio_efectivo_loaders.py backend/tests/test_e2e_criterio_efectivo.py
git commit -m "feat: los loaders de IVA e ISR leen el criterio de efectivo de la empresa"
```

---

### Task 6: API — `GET`/`PUT /criterio-efectivo` y `criterio_efectivo` en los resúmenes

**Files:**
- Create: `backend/routers/criterio_efectivo.py`, `backend/tests/test_router_criterio_efectivo.py`
- Modify: `backend/criterio_efectivo.py` (agregar `guardar`), `backend/main_api.py` (registrar router), `backend/routers/iva_flujo.py` (respuesta de resumen, ~línea 159), `backend/routers/isr_flujo.py` (respuesta de resumen, ~línea 178-200), `docs/openapi.yaml`

**Interfaces:**
- Consumes: `criterio_efectivo.validar/umbral/leer` (Tareas 1 y 5); `usuarios_empresa.roles_efectivos`, `usuarios_empresa.puede_administrar` (existentes); `deps.validar_acceso_empresa`, `deps.get_current_user`.
- Produces: `criterio_efectivo.guardar(empresa_id, nuevo, usuario_id) -> dict` (`{"criterio_efectivo", "anterior"}`); `GET`/`PUT /api/v1/empresas/{empresa_id}/criterio-efectivo` → `{"criterio_efectivo": str, "umbral_efectivo": float}`.

- [ ] **Step 1: Write the failing tests**

```python
"""Router del criterio de efectivo (spec 2026-10-13). DB mockeada."""
import pytest
from fastapi.testclient import TestClient

import backend.main_api as main
from backend import criterio_efectivo
from backend.deps import get_current_user
from backend.routers import criterio_efectivo as router

client = TestClient(main.app)
URL = "/api/v1/empresas/emp-1/criterio-efectivo"


@pytest.fixture
def sesion(monkeypatch):
    main.app.dependency_overrides[get_current_user] = lambda: {"id": "u1", "user_id": "u1"}
    monkeypatch.setattr(router, "validar_acceso_empresa", lambda *a, **k: None)
    yield monkeypatch
    main.app.dependency_overrides.clear()


def _como(monkeypatch, *, administrador: bool, plataforma=None):
    monkeypatch.setattr(router, "_roles_de_empresa", lambda eid: {"u1": "administrador" if administrador else "contador"})
    monkeypatch.setattr(router, "_rol_plataforma", lambda uid: plataforma)


def test_get_devuelve_criterio_y_umbral(sesion):
    sesion.setattr(criterio_efectivo, "leer", lambda e: "estricto")
    r = client.get(URL)
    assert r.status_code == 200
    assert r.json() == {"criterio_efectivo": "estricto", "umbral_efectivo": 0.0}


def test_put_como_administrador_guarda_y_devuelve(sesion):
    _como(sesion, administrador=True)
    visto = {}
    sesion.setattr(criterio_efectivo, "guardar", lambda e, n, u: visto.update(e=e, n=n, u=u) or {"criterio_efectivo": n, "anterior": "legal"})
    r = client.put(URL, json={"criterio": "estricto"})
    assert r.status_code == 200
    assert r.json()["criterio_efectivo"] == "estricto" and r.json()["umbral_efectivo"] == 0.0
    assert visto == {"e": "emp-1", "n": "estricto", "u": "u1"}


@pytest.mark.parametrize("cuerpo", [{}, {"criterio": None}, {"criterio": ""}, {"criterio": "Legal"}, {"criterio": "laxo"}, {"criterio": 1}])
def test_put_rechaza_valores_invalidos_con_422(sesion, cuerpo):
    _como(sesion, administrador=True)
    sesion.setattr(criterio_efectivo, "guardar", lambda *a: pytest.fail("no debe guardar"))
    assert client.put(URL, json=cuerpo).status_code == 422


def test_put_sin_rol_de_administrador_da_403_y_no_guarda(sesion):
    _como(sesion, administrador=False)
    sesion.setattr(criterio_efectivo, "guardar", lambda *a: pytest.fail("no debe guardar"))
    assert client.put(URL, json={"criterio": "estricto"}).status_code == 403


def test_put_como_admin_de_plataforma_puede(sesion):
    _como(sesion, administrador=False, plataforma="admin")
    sesion.setattr(criterio_efectivo, "guardar", lambda e, n, u: {"criterio_efectivo": n, "anterior": "legal"})
    assert client.put(URL, json={"criterio": "legal"}).status_code == 200


def test_put_sin_token_da_401():
    assert client.put(URL, json={"criterio": "legal"}).status_code == 401
```

Y agregar a `backend/tests/test_router_iva_flujo.py` y `backend/tests/test_router_isr_flujo.py` una prueba por cada uno (siguiendo la fixture `con_acceso` existente de cada archivo, con `empresa_or_404` devolviendo `"criterio_efectivo": "estricto"`) que afirme `r.json()["criterio_efectivo"] == "estricto"` en la respuesta del resumen. Para `guardar` (con DB) agregar a `test_e2e_criterio_efectivo.py`:

```python
def test_guardar_audita_en_la_misma_transaccion(empresa_sembrada, usuario_id):
    criterio_efectivo.guardar(empresa_sembrada, "estricto", usuario_id)
    assert criterio_efectivo.leer(empresa_sembrada) == "estricto"
    fila = db.query_one("SELECT metadata FROM auditoria WHERE empresa_id = %s AND accion = 'criterio_efectivo' "
                        "ORDER BY created_at DESC LIMIT 1", (empresa_sembrada,))
    assert fila["metadata"] == {"anterior": "legal", "nuevo": "estricto"}
```

> `empresa_sembrada` y `usuario_id` son fixtures locales del archivo E2E (crear la empresa y un usuario con los mismos ayudantes de `test_e2e_iva_flujo.py`; limpiar en `finally`/teardown).

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest backend/tests/test_router_criterio_efectivo.py -v`
Expected: FAIL con `ImportError: cannot import name 'criterio_efectivo' from 'backend.routers'`.

- [ ] **Step 3: Implement**

`guardar` en `backend/criterio_efectivo.py` (añadir `import psycopg2.extras` arriba):

```python
def guardar(empresa_id: str, nuevo: str, usuario_id: str) -> dict:
    """Cambia el criterio y lo audita, todo o nada. Devuelve el valor nuevo y el anterior."""
    nuevo = validar(nuevo)
    with db.get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT criterio_efectivo FROM empresas WHERE id = %s FOR UPDATE", (empresa_id,))
            fila = cur.fetchone()
            if fila is None:
                raise LookupError("Empresa no encontrada")
            anterior = fila["criterio_efectivo"]
            cur.execute("UPDATE empresas SET criterio_efectivo = %s WHERE id = %s", (nuevo, empresa_id))
            cur.execute(
                """INSERT INTO auditoria (usuario_id, empresa_id, accion, entidad, entidad_id, metadata)
                   VALUES (%s, %s, 'criterio_efectivo', 'empresa', %s, %s)""",
                (usuario_id, empresa_id, empresa_id, psycopg2.extras.Json({"anterior": anterior, "nuevo": nuevo})),
            )
    return {"criterio_efectivo": nuevo, "anterior": anterior}
```

`backend/routers/criterio_efectivo.py`:

```python
"""Criterio de efectivo de la empresa (spec 2026-10-13): consulta y cambio, solo para administradores."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .. import criterio_efectivo, db, usuarios_empresa
from ..deps import get_current_user, validar_acceso_empresa

router = APIRouter(tags=["Criterio de efectivo"])

_RUTA = "/api/v1/empresas/{empresa_id}/criterio-efectivo"


class CriterioIn(BaseModel):
    criterio: Literal["legal", "estricto"]


def _rol_plataforma(usuario_id: str):
    return (db.query_one("SELECT rol FROM usuarios WHERE id = %s", (usuario_id,)) or {}).get("rol")


def _roles_de_empresa(empresa_id: str) -> dict:
    miembros = db.query_all(
        "SELECT usuario_id, rol, created_at FROM usuario_empresas WHERE empresa_id = %s", (empresa_id,))
    return usuarios_empresa.roles_efectivos(miembros)


def _respuesta(criterio: str) -> dict:
    return {"criterio_efectivo": criterio, "umbral_efectivo": float(criterio_efectivo.umbral(criterio))}


@router.get(_RUTA)
async def leer_criterio(empresa_id: str, current_user: dict = Depends(get_current_user)):
    """Criterio de efectivo vigente de la empresa y el umbral que implica."""
    validar_acceso_empresa(empresa_id, current_user)
    return _respuesta(criterio_efectivo.leer(empresa_id))


@router.put(_RUTA)
async def cambiar_criterio(empresa_id: str, datos: CriterioIn, current_user: dict = Depends(get_current_user)):
    """Cambia el criterio de efectivo (``legal`` o ``estricto``) y lo audita. Solo administradores."""
    validar_acceso_empresa(empresa_id, current_user)
    usuario_id = current_user["user_id"]
    if not usuarios_empresa.puede_administrar(usuario_id, _roles_de_empresa(empresa_id), _rol_plataforma(usuario_id)):
        raise HTTPException(status_code=403, detail="Solo un administrador de la empresa puede cambiar el criterio de efectivo")
    try:
        resultado = criterio_efectivo.guardar(empresa_id, datos.criterio, usuario_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")
    return _respuesta(resultado["criterio_efectivo"])
```

`backend/main_api.py`: importar el router junto a los demás (`from .routers import criterio_efectivo as criterio_efectivo_router`) y `app.include_router(criterio_efectivo_router.router)` después de `cierre_router`.

`backend/routers/iva_flujo.py` y `backend/routers/isr_flujo.py`: en el `return _json({...})` del resumen agregar `"criterio_efectivo": empresa.get("criterio_efectivo", "legal"),` (la variable `empresa` ya viene de `empresa_or_404`, que hace `SELECT *`).

`docs/openapi.yaml`: agregar bajo `paths:` (junto a las rutas de IVA flujo) las dos operaciones, con el mismo estilo que las existentes:

```yaml
  /api/v1/empresas/{empresa_id}/criterio-efectivo:
    get:
      tags:
      - Criterio de efectivo
      summary: Leer Criterio
      description: Criterio de efectivo vigente de la empresa y el umbral que implica.
      operationId: leer_criterio_api_v1_empresas__empresa_id__criterio_efectivo_get
      security:
      - HTTPBearer: []
      parameters:
      - name: empresa_id
        in: path
        required: true
        schema:
          type: string
          title: Empresa Id
      responses:
        '200':
          description: Successful Response
          content:
            application/json:
              schema: {}
        '422':
          description: Validation Error
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/HTTPValidationError'
    put:
      tags:
      - Criterio de efectivo
      summary: Cambiar Criterio
      description: Cambia el criterio de efectivo (legal o estricto) y lo audita. Solo
        administradores.
      operationId: cambiar_criterio_api_v1_empresas__empresa_id__criterio_efectivo_put
      security:
      - HTTPBearer: []
      parameters:
      - name: empresa_id
        in: path
        required: true
        schema:
          type: string
          title: Empresa Id
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required:
              - criterio
              properties:
                criterio:
                  type: string
                  enum:
                  - legal
                  - estricto
      responses:
        '200':
          description: Successful Response
          content:
            application/json:
              schema: {}
        '422':
          description: Validation Error
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/HTTPValidationError'
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest backend/tests/test_router_criterio_efectivo.py backend/tests/test_router_iva_flujo.py backend/tests/test_router_isr_flujo.py backend/tests/test_openapi_sync.py -v`
Expected: PASS. Con Postgres: `python -m pytest backend/tests/test_e2e_criterio_efectivo.py -v -m db` también PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/criterio_efectivo.py backend/routers/criterio_efectivo.py backend/main_api.py backend/routers/iva_flujo.py backend/routers/isr_flujo.py docs/openapi.yaml backend/tests/test_router_criterio_efectivo.py backend/tests/test_router_iva_flujo.py backend/tests/test_router_isr_flujo.py backend/tests/test_e2e_criterio_efectivo.py
git commit -m "feat: API del criterio de efectivo y criterio en los resúmenes de IVA e ISR"
```

---

### Task 7: Frontend — selector e insignia en IVA e ISR

**Files:**
- Create: `frontend/hooks/useCriterioEfectivo.ts`, `frontend/hooks/useCriterioEfectivo.test.tsx`, `frontend/components/shared/CriterioEfectivo.tsx`, `frontend/components/shared/CriterioEfectivo.test.tsx`
- Modify: `frontend/components/iva-flujo/IvaFlujoPantalla.tsx`, `frontend/components/isr-flujo/IsrFlujoPantalla.tsx`, `frontend/types/api.ts`

**Interfaces:**
- Consumes: `GET`/`PUT /api/v1/empresas/{id}/criterio-efectivo` (Tarea 6); `apiFetch` y el patrón de `useGuardarPorcentajeNomina` en `frontend/hooks/useIsrFlujo.ts` (líneas 69-80) para invalidar consultas.
- Produces: `useCriterioEfectivo(empresaId)` → resultado de `useQuery` con `data: { criterio_efectivo, umbral_efectivo }`; `useCambiarCriterioEfectivo(empresaId)` (mutación que invalida las consultas `["iva-flujo", ...]`, `["isr-flujo", ...]` e `["criterio-efectivo", empresaId]`); `<CriterioEfectivo empresaId={...} />`.

- [ ] **Step 1: Write the failing tests**

Antes, leer `frontend/hooks/useIsrFlujo.test.tsx` y `frontend/components/isr-flujo/IsrFlujoPantalla.test.tsx` para copiar el envoltorio de `QueryClientProvider` y el mock de `apiFetch`/`fetch` que ya usan, y mantener la misma convención.

`CriterioEfectivo.test.tsx` — casos:
1. Con `criterio = "legal"` muestra el select con "Legal (efectivo mayor a $2,000)" seleccionado y **no** muestra la insignia "Criterio: Estricto".
2. Con `criterio = "estricto"` muestra la insignia "Criterio: Estricto".
3. Cambiar el select a "Estricto (todo efectivo)" llama a `PUT .../criterio-efectivo` con `{"criterio":"estricto"}`.
4. Si el `PUT` responde 403, muestra el mensaje de error del servidor y el select vuelve al valor anterior.

`useCriterioEfectivo.test.tsx` — casos: (1) lee el criterio del `GET`; (2) tras la mutación se invalidan las consultas de IVA e ISR del mismo `empresaId`.

Y en `IvaFlujoPantalla.test.tsx` / `IsrFlujoPantalla.test.tsx` un caso por pantalla: el componente `CriterioEfectivo` aparece (por su `aria-label="Criterio de efectivo"`).

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run components/shared/CriterioEfectivo.test.tsx hooks/useCriterioEfectivo.test.tsx`
Expected: FAIL con "Failed to resolve import".

- [ ] **Step 3: Implement**

`frontend/hooks/useCriterioEfectivo.ts`:

```ts
"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";

export type CriterioEfectivoValor = "legal" | "estricto";

export interface CriterioEfectivoRespuesta {
  criterio_efectivo: CriterioEfectivoValor;
  umbral_efectivo: number;
}

const ruta = (empresaId: string) => `/api/v1/empresas/${empresaId}/criterio-efectivo`;

export function useCriterioEfectivo(empresaId: string) {
  return useQuery({
    queryKey: ["criterio-efectivo", empresaId],
    queryFn: () => apiFetch<CriterioEfectivoRespuesta>(ruta(empresaId)),
    enabled: Boolean(empresaId),
  });
}

/** Cambia el criterio y refresca todo lo que depende de él (IVA, ISR, DIOT, inicio y declaraciones). */
export function useCambiarCriterioEfectivo(empresaId: string) {
  const cliente = useQueryClient();
  return useMutation({
    mutationFn: (criterio: CriterioEfectivoValor) =>
      apiFetch<CriterioEfectivoRespuesta>(ruta(empresaId), { method: "PUT", body: JSON.stringify({ criterio }) }),
    onSuccess: () => {
      for (const clave of ["criterio-efectivo", "iva-flujo", "isr-flujo", "diot", "inicio", "declaraciones"]) {
        cliente.invalidateQueries({ queryKey: [clave] });
      }
    },
  });
}
```

> Verificar contra `useIvaFlujo.ts` / `useIsrFlujo.ts` / `useDiotFlujo.ts` / `useInicio.ts` / `useDeclaraciones.ts` el primer elemento real de cada `queryKey` y usar esos nombres exactos en el arreglo de arriba; si alguno no coincide, la invalidación no surte efecto (el test del hook lo detecta).

`frontend/components/shared/CriterioEfectivo.tsx`: componente cliente con `<Label htmlFor="criterio-efectivo">Criterio de efectivo</Label>`, un `<select id="criterio-efectivo" aria-label="Criterio de efectivo">` con las opciones `legal` ("Legal (efectivo mayor a $2,000)") y `estricto` ("Estricto (todo efectivo)"), una `<Badge>` "Criterio: Estricto" visible solo con `estricto`, y un texto de ayuda de una línea por opción. Al cambiar llama a `useCambiarCriterioEfectivo(...).mutateAsync(valor)`; si falla, muestra `error.message` en un `<p role="alert">` y deja el valor del servidor. Usar los mismos primitivos y clases que `IsrFlujoPantalla.tsx` líneas 149-160 (`Label`, `select` nativo con las clases de ese archivo) para consistencia visual.

Montaje: en `IsrFlujoPantalla.tsx` colocar `<CriterioEfectivo empresaId={empresaId} />` junto al selector `isr-pct` (línea ~149); en `IvaFlujoPantalla.tsx` junto al control de periodo/factor. En `frontend/types/api.ts` agregar `criterio_efectivo?: "legal" | "estricto"` a los tipos de respuesta de resumen de IVA e ISR.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run components/shared hooks/useCriterioEfectivo.test.tsx components/iva-flujo components/isr-flujo && npx tsc --noEmit`
Expected: PASS y sin errores de tipos nuevos (ya había 4 errores de tipos de `useCierre.ts`/`CierrePeriodo.tsx` ajenos a este trabajo; no deben aumentar).

- [ ] **Step 5: Commit**

```bash
git add frontend/hooks/useCriterioEfectivo.ts frontend/hooks/useCriterioEfectivo.test.tsx frontend/components/shared/CriterioEfectivo.tsx frontend/components/shared/CriterioEfectivo.test.tsx frontend/components/iva-flujo frontend/components/isr-flujo frontend/types/api.ts
git commit -m "feat: selector e insignia del criterio de efectivo en IVA e ISR flujo"
```

---

### Task 8: Verificación fiscal, documentación y cierre

**Files:**
- Modify: `docs/superpowers/specs/2026-10-01-paridad-y-mejoras-roadmap.md` (nueva decisión D11)
- Modify: `docs/superpowers/specs/2026-10-13-criterio-efectivo-design.md` (estado → implementada)

- [ ] **Step 1: Suites completas**

Run: `python -m pytest -m "not db" -q` — Expected: todo en verde.
Run (con Postgres): `python -m pytest -m db -q` — Expected: todo en verde.
Run: `cd frontend && npm test -- --run` — Expected: todo en verde.

- [ ] **Step 2: Revisión fiscal**

Invocar el agente `dominio-fiscal` sobre el diff de `backend/iva_flujo.py`, `backend/isr_flujo.py`, `backend/iva_flujo_datos.py`, `backend/isr_flujo_datos.py` y `backend/criterio_efectivo.py` con la pregunta: ¿el criterio `estricto` rompe alguna otra regla (retenciones de IVA, notas de crédito, REP en moneda extranjera, anticipos)? Resolver lo que reporte o anotarlo en el PR.

- [ ] **Step 3: Documentar la decisión**

En la tabla "Decisiones tomadas" del plan maestro agregar:

```markdown
| D11 | Criterio de efectivo (decidido por Carlos, 2026-10-13) | Por empresa: `legal` (efectivo mayor a $2,000, por defecto) o `estricto` (todo efectivo, como la plataforma de referencia). La Cédula de IVA antigua y la tarjeta de efectivo de Validaciones siguen con la regla legal | F5, F7 |
```

Y cambiar el estado de la spec a "implementada".

- [ ] **Step 4: Verificación visual**

Levantar `./dev.sh`, abrir IVA base flujo e ISR base flujo de una empresa con compras en efectivo, cambiar el criterio y confirmar: (a) la insignia aparece, (b) los CFDI en efectivo pasan a "No considerados" con motivo `efectivo`, (c) al volver a `legal` regresan. Capturar pantalla de cada paso para el PR.

- [ ] **Step 5: Commit y PR**

```bash
git add docs/superpowers/specs/2026-10-01-paridad-y-mejoras-roadmap.md docs/superpowers/specs/2026-10-13-criterio-efectivo-design.md
git commit -m "docs: decisión D11 criterio de efectivo y estado de la spec"
```

PR con título `feat: criterio de efectivo por empresa (legal / estricto)`, descripción con el cuadre de octubre de 2026 (diferencia de $1,572.66) y la nota de alcance excluido (Cédula antigua y Validaciones).
