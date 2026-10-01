# Fase 1 — Detalle fiscal del CFDI — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Guardar de cada CFDI los impuestos por tasa, los conceptos, los encabezados faltantes, los impuestos de cada pago (REP 2.0) y los totales de nómina, y reprocesar los XML ya almacenados para que tengan el mismo detalle.

**Architecture:** `backend/cfdi_parser.py` (puro, sin base de datos) extrae el detalle a dataclasses nuevas; `backend/cfdi_store.py` lo persiste en tablas hijas con borrar-e-insertar idempotente; `backend/reproceso.py` vuelve a parsear `cfdi.xml_raw` por lotes y lo expone un endpoint de administrador. Ninguna pantalla ni cálculo existente cambia en esta fase: solo se agregan datos.

**Tech Stack:** Python 3.11, FastAPI, psycopg2 (helpers `db.query_one` / `db.query_all` / `db.execute`), PostgreSQL, pytest, `xml.etree.ElementTree`.

**Spec:** `docs/superpowers/specs/2026-10-01-paridad-y-mejoras-roadmap.md` (fase F1 y sección "Reglas fiscales → Comunes").

## Global Constraints

- Rama `feat/fase1-detalle-fiscal-cfdi` creada desde `main` **después** de terminar F0 del plan maestro (trabajo pendiente integrado). No trabajar sobre `chore/dev-sh-stack-completo`.
- Importes siempre `Decimal`; nunca `float` en cálculo. A la base se mandan como `str(decimal)`.
- La cifra oficial de impuestos es la del nodo `Impuestos` del comprobante; el desglose por concepto es informativo.
- Migraciones idempotentes (`IF NOT EXISTS`), numeradas, y registradas en `backend/db.py::init_db`.
- Todo endpoint nuevo se documenta en `docs/openapi.yaml` (lo exige `backend/tests/test_openapi_sync.py`).
- 4 espacios en Python; módulos en snake_case; commits Conventional Commit en imperativo.
- Finales de línea LF (los fija `.gitattributes` desde F0).
- Nunca commitear XML reales, `.env`, archivos FIEL ni dumps.
- Comandos de prueba: `python -m pytest -m "not db"` (rápido) y `python -m pytest -m db` (requiere `docker compose up -d db`). Línea base antes de empezar: 356 unitarias y 33 de integración en verde (389).

## Review Focus

- CFDI 3.3 no trae `Base` en los traslados del nodo raíz → la base por tasa debe salir de los conceptos (prueba en Task 2).
- Traslado `Exento` no trae `TasaOCuota` ni `Importe` → se guarda con tasa nula e importe 0, sin tronar (prueba en Task 2).
- Complemento de Pagos 1.0 no trae `ImpuestosDR` → lista vacía y `version == "1.0"`, sin tronar (prueba en Task 4).
- Re-subir el mismo CFDI o el mismo REP no duplica filas de detalle (prueba en Task 6).
- Un `xml_raw` ilegible durante el reproceso no detiene el lote ni se reintenta para siempre (prueba en Task 7).

## Mapa de archivos

| Archivo | Acción | Responsabilidad |
|---|---|---|
| `database/migrations/028_cfdi_detalle_fiscal.sql` | Crear | Columnas y tablas nuevas |
| `backend/db.py` | Modificar (`init_db`) | Registrar la 028 |
| `backend/cfdi_parser.py` | Modificar | Dataclasses y extracción del detalle |
| `backend/cfdi_store.py` | Modificar | Persistir el detalle |
| `backend/reproceso.py` | Crear | Reparsear `xml_raw` por lotes |
| `backend/routers/admin.py` | Modificar | `POST /api/v1/admin/reprocesar-cfdi` |
| `docs/openapi.yaml` | Modificar | Documentar el endpoint |
| `backend/tests/test_migracion_028.py` | Crear | Prueba de la migración (db) |
| `backend/tests/test_cfdi_parser_detalle.py` | Crear | Pruebas unitarias del parser |
| `backend/tests/test_e2e_detalle_cfdi.py` | Crear | Pruebas de persistencia y reproceso (db) |
| `backend/tests/test_router_admin.py` | Modificar | Prueba del endpoint (mock) |

---

### Task 1: Migración 028

**Files:**
- Create: `database/migrations/028_cfdi_detalle_fiscal.sql`
- Modify: `backend/db.py` (dentro de `init_db`, después de la línea que aplica `027_pagos_idempotentes.sql`)
- Test: `backend/tests/test_migracion_028.py`

**Interfaces:**
- Consumes: nada.
- Produces: tablas `cfdi_impuestos`, `cfdi_conceptos`, `pagos_relaciones_impuestos`; columnas nuevas en `cfdi`, `pagos_cfdi`, `pagos_relaciones` (nombres exactos en el SQL de abajo; las Tasks 6 y 7 dependen de ellos).

- [ ] **Step 1: Escribir la prueba que falla**

Crear `backend/tests/test_migracion_028.py`:

```python
"""Migración 028: detalle fiscal del CFDI. Requiere Postgres real."""
import pytest

from backend.tests.conftest import db_disponible

pytestmark = [pytest.mark.db, pytest.mark.skipif(not db_disponible(), reason="Postgres no disponible (docker compose up -d db)")]


def _columnas(db, tabla):
    filas = db.query_all(
        "SELECT column_name FROM information_schema.columns WHERE table_schema = 'public' AND table_name = %s",
        (tabla,),
    )
    return {f["column_name"] for f in filas}


def test_028_crea_tablas_y_columnas_y_se_puede_repetir():
    from backend import db

    db.init_db()
    db.init_db()  # idempotente: aplicarla dos veces no debe fallar

    assert {
        "regimen_emisor", "condiciones_pago", "no_certificado", "periodicidad", "meses",
        "anio_global", "nomina_percepciones", "nomina_deducciones", "nomina_otros_pagos",
        "nomina_gravado", "nomina_exento", "nomina_isr_retenido", "detalle_version",
    } <= _columnas(db, "cfdi")
    assert {"cfdi_id", "ambito", "impuesto", "tipo_factor", "tasa_o_cuota", "base", "importe"} <= _columnas(db, "cfdi_impuestos")
    assert {
        "cfdi_id", "linea", "clave_prod_serv", "no_identificacion", "cantidad", "clave_unidad", "unidad",
        "descripcion", "valor_unitario", "importe", "descuento", "objeto_imp", "cuenta_predial", "impuestos",
    } <= _columnas(db, "cfdi_conceptos")
    assert {"relacion_id", "ambito", "impuesto", "tipo_factor", "tasa_o_cuota", "base", "importe"} <= _columnas(db, "pagos_relaciones_impuestos")
    assert {"moneda_dr", "equivalencia_dr"} <= _columnas(db, "pagos_relaciones")
    assert "version_pago" in _columnas(db, "pagos_cfdi")
```

- [ ] **Step 2: Correr la prueba y verla fallar**

Run: `docker compose up -d db && python -m pytest backend/tests/test_migracion_028.py -v`
Expected: FAIL — el primer `assert` reporta que faltan las columnas en `cfdi`.

- [ ] **Step 3: Crear la migración**

Crear `database/migrations/028_cfdi_detalle_fiscal.sql`:

```sql
-- ============================================================
-- Migración 028: Detalle fiscal del CFDI
-- Idempotente: ADD COLUMN / CREATE TABLE / CREATE INDEX IF NOT EXISTS.
--
-- Hasta aquí `cfdi` solo guardaba totales (iva_trasladado, iva_retenido,
-- isr_retenido). Para desglosar IVA por tasa, armar la DIOT y el ISR por
-- flujo hacen falta: impuestos por tasa con su base, conceptos, encabezados
-- que el parser ya leía pero no se guardaban, los impuestos de cada pago
-- (ImpuestosDR del REP 2.0) y los totales del complemento de nómina.
-- ============================================================

-- 1. Encabezados y nómina en cfdi.
--    detalle_version: 0 = sin detalle (CFDI anterior a esta migración),
--    >=1 = detalle guardado con esa versión del extractor, -1 = el xml_raw
--    no se pudo reprocesar (no se reintenta).
ALTER TABLE cfdi
  ADD COLUMN IF NOT EXISTS regimen_emisor       VARCHAR(10),
  ADD COLUMN IF NOT EXISTS condiciones_pago     TEXT,
  ADD COLUMN IF NOT EXISTS no_certificado       VARCHAR(40),
  ADD COLUMN IF NOT EXISTS periodicidad         VARCHAR(2),
  ADD COLUMN IF NOT EXISTS meses                VARCHAR(2),
  ADD COLUMN IF NOT EXISTS anio_global          SMALLINT,
  ADD COLUMN IF NOT EXISTS nomina_percepciones  NUMERIC(18,2),
  ADD COLUMN IF NOT EXISTS nomina_deducciones   NUMERIC(18,2),
  ADD COLUMN IF NOT EXISTS nomina_otros_pagos   NUMERIC(18,2),
  ADD COLUMN IF NOT EXISTS nomina_gravado       NUMERIC(18,2),
  ADD COLUMN IF NOT EXISTS nomina_exento        NUMERIC(18,2),
  ADD COLUMN IF NOT EXISTS nomina_isr_retenido  NUMERIC(18,2),
  ADD COLUMN IF NOT EXISTS detalle_version      SMALLINT NOT NULL DEFAULT 0;

CREATE INDEX IF NOT EXISTS idx_cfdi_detalle_pendiente
    ON cfdi (created_at) WHERE detalle_version = 0;

-- 2. Impuestos del comprobante agrupados por ámbito, impuesto, factor y tasa.
CREATE TABLE IF NOT EXISTS cfdi_impuestos (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    cfdi_id       UUID NOT NULL REFERENCES cfdi(id) ON DELETE CASCADE,
    ambito        VARCHAR(10) NOT NULL CHECK (ambito IN ('traslado', 'retencion')),
    impuesto      VARCHAR(3)  NOT NULL,          -- 001 ISR, 002 IVA, 003 IEPS
    tipo_factor   VARCHAR(10) NOT NULL,          -- Tasa | Cuota | Exento
    tasa_o_cuota  NUMERIC(10,6),                 -- NULL en Exento o si el XML no la trae
    base          NUMERIC(18,2) NOT NULL DEFAULT 0,
    importe       NUMERIC(18,2) NOT NULL DEFAULT 0
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_cfdi_impuestos
    ON cfdi_impuestos (cfdi_id, ambito, impuesto, tipo_factor, COALESCE(tasa_o_cuota, -1));

-- 3. Conceptos del comprobante (impuestos por concepto en JSONB, informativos).
CREATE TABLE IF NOT EXISTS cfdi_conceptos (
    id                 UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    cfdi_id            UUID NOT NULL REFERENCES cfdi(id) ON DELETE CASCADE,
    linea              INTEGER NOT NULL,
    clave_prod_serv    VARCHAR(10),
    no_identificacion  TEXT,
    cantidad           NUMERIC(18,6) NOT NULL DEFAULT 0,
    clave_unidad       VARCHAR(10),
    unidad             TEXT,
    descripcion        TEXT,
    valor_unitario     NUMERIC(18,6) NOT NULL DEFAULT 0,
    importe            NUMERIC(18,6) NOT NULL DEFAULT 0,
    descuento          NUMERIC(18,6) NOT NULL DEFAULT 0,
    objeto_imp         VARCHAR(2),
    cuenta_predial     TEXT,
    impuestos          JSONB NOT NULL DEFAULT '[]'::jsonb
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_cfdi_conceptos_linea
    ON cfdi_conceptos (cfdi_id, linea);

-- 4. Pagos: versión del complemento, moneda/equivalencia del documento
--    relacionado e impuestos de cada documento pagado (ImpuestosDR).
ALTER TABLE pagos_cfdi
  ADD COLUMN IF NOT EXISTS version_pago VARCHAR(3);

ALTER TABLE pagos_relaciones
  ADD COLUMN IF NOT EXISTS moneda_dr       VARCHAR(3),
  ADD COLUMN IF NOT EXISTS equivalencia_dr NUMERIC(18,10);

CREATE TABLE IF NOT EXISTS pagos_relaciones_impuestos (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    relacion_id   UUID NOT NULL REFERENCES pagos_relaciones(id) ON DELETE CASCADE,
    ambito        VARCHAR(10) NOT NULL CHECK (ambito IN ('traslado', 'retencion')),
    impuesto      VARCHAR(3)  NOT NULL,
    tipo_factor   VARCHAR(10) NOT NULL,
    tasa_o_cuota  NUMERIC(10,6),
    base          NUMERIC(18,2) NOT NULL DEFAULT 0,
    importe       NUMERIC(18,2) NOT NULL DEFAULT 0
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_pagos_rel_impuestos
    ON pagos_relaciones_impuestos (relacion_id, ambito, impuesto, tipo_factor, COALESCE(tasa_o_cuota, -1));
```

- [ ] **Step 4: Registrar la migración en `init_db`**

En `backend/db.py`, justo después de `_run_sql_file("027_pagos_idempotentes.sql")` y antes del comentario `# Seed inicial`, agregar:

```python
        # 028 es idempotente — detalle fiscal del CFDI: impuestos por tasa, conceptos,
        # encabezados, impuestos de cada pago (REP) y totales de nómina
        _run_sql_file("028_cfdi_detalle_fiscal.sql")

```

- [ ] **Step 5: Correr la prueba y verla pasar**

Run: `python -m pytest backend/tests/test_migracion_028.py -v`
Expected: PASS (1 passed).

- [ ] **Step 6: Validar la migración y commitear**

Pedir al agente `migration-validator` que revise `database/migrations/028_cfdi_detalle_fiscal.sql`; corregir lo que señale.

```bash
git add database/migrations/028_cfdi_detalle_fiscal.sql backend/db.py backend/tests/test_migracion_028.py
git commit -m "feat: agregar migración 028 con el detalle fiscal del CFDI"
```

---

### Task 2: Parser — impuestos por tasa

**Files:**
- Modify: `backend/cfdi_parser.py`
- Test: `backend/tests/test_cfdi_parser_detalle.py` (crear)

**Interfaces:**
- Consumes: `CFDIParser._decimal(node, attr, default="0") -> Decimal` (ya existe).
- Produces:
  - `ImpuestoResumen(ambito: str, impuesto: str, tipo_factor: str, tasa_o_cuota: Optional[Decimal], base: Decimal, importe: Decimal)`
  - `_agrupar_impuestos(filas: list[ImpuestoResumen]) -> list[ImpuestoResumen]` (función de módulo)
  - `CFDIParser._leer_impuesto(nodo, ambito: str, sufijo: str = "") -> ImpuestoResumen`
  - `CFDIParsed.resumen_impuestos: list[ImpuestoResumen]`

Regla: los traslados se toman del nodo raíz cuando todos traen `Base` (CFDI 4.0: cifra oficial ya agrupada por tasa); si no (CFDI 3.3), se suman los de los conceptos. Las retenciones se toman de los conceptos (ahí traen base y tasa); si no hay, del nodo raíz, con tasa nula y base 0.

- [ ] **Step 1: Escribir las pruebas que fallan**

Crear `backend/tests/test_cfdi_parser_detalle.py`:

```python
"""Detalle fiscal del CFDI en backend/cfdi_parser.py: impuestos por tasa,
conceptos, encabezados, impuestos de cada pago y nómina. Lógica pura (sin DB)."""
from decimal import Decimal

from backend.cfdi_parser import CFDIParser

D = Decimal


def _cfdi(cuerpo, *, version="4.0", tipo="I", subtotal="1000.00", total="1128.00", extra_attrs="", complemento=""):
    ns = "http://www.sat.gob.mx/cfd/4" if version == "4.0" else "http://www.sat.gob.mx/cfd/3"
    return f'''<cfdi:Comprobante xmlns:cfdi="{ns}" xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital"
        Version="{version}" Fecha="2026-01-15T12:00:00" TipoDeComprobante="{tipo}" SubTotal="{subtotal}"
        Total="{total}" Moneda="MXN" MetodoPago="PUE" FormaPago="03" LugarExpedicion="01000"
        Exportacion="01" {extra_attrs}>
      <cfdi:Emisor Rfc="PROV010101AAA" Nombre="Proveedor SA" RegimenFiscal="601"/>
      <cfdi:Receptor Rfc="EMP010101AAA" Nombre="Empresa SA" UsoCFDI="G03"
          DomicilioFiscalReceptor="01000" RegimenFiscalReceptor="601"/>
      {cuerpo}
      <cfdi:Complemento>{complemento}<tfd:TimbreFiscalDigital
          UUID="AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE" FechaTimbrado="2026-01-15T12:05:00"/></cfdi:Complemento>
    </cfdi:Comprobante>'''


# Tres conceptos: 16 %, 0 % y exento. SubTotal 1000, IVA 128, Total 1128.
CUERPO_MIXTO = '''
<cfdi:Conceptos>
  <cfdi:Concepto ClaveProdServ="43211500" NoIdentificacion="SKU-1" Cantidad="2" ClaveUnidad="H87"
      Unidad="Pieza" Descripcion="Laptop" ValorUnitario="400.00" Importe="800.00" Descuento="0.00" ObjetoImp="02">
    <cfdi:Impuestos><cfdi:Traslados>
      <cfdi:Traslado Base="800.00" Impuesto="002" TipoFactor="Tasa" TasaOCuota="0.160000" Importe="128.00"/>
    </cfdi:Traslados></cfdi:Impuestos>
  </cfdi:Concepto>
  <cfdi:Concepto ClaveProdServ="50161500" Cantidad="1" ClaveUnidad="KGM" Descripcion="Alimento"
      ValorUnitario="150.00" Importe="150.00" ObjetoImp="02">
    <cfdi:Impuestos><cfdi:Traslados>
      <cfdi:Traslado Base="150.00" Impuesto="002" TipoFactor="Tasa" TasaOCuota="0.000000" Importe="0.00"/>
    </cfdi:Traslados></cfdi:Impuestos>
  </cfdi:Concepto>
  <cfdi:Concepto ClaveProdServ="85121600" Cantidad="1" ClaveUnidad="E48" Descripcion="Consulta"
      ValorUnitario="50.00" Importe="50.00" ObjetoImp="02">
    <cfdi:Impuestos><cfdi:Traslados>
      <cfdi:Traslado Base="50.00" Impuesto="002" TipoFactor="Exento"/>
    </cfdi:Traslados></cfdi:Impuestos>
    <cfdi:CuentaPredial Numero="PRED-9"/>
  </cfdi:Concepto>
</cfdi:Conceptos>
<cfdi:Impuestos TotalImpuestosTrasladados="128.00"><cfdi:Traslados>
  <cfdi:Traslado Base="800.00" Impuesto="002" TipoFactor="Tasa" TasaOCuota="0.160000" Importe="128.00"/>
  <cfdi:Traslado Base="150.00" Impuesto="002" TipoFactor="Tasa" TasaOCuota="0.000000" Importe="0.00"/>
  <cfdi:Traslado Base="50.00" Impuesto="002" TipoFactor="Exento"/>
</cfdi:Traslados></cfdi:Impuestos>'''

# CFDI 3.3: el nodo raíz no trae Base; dos conceptos al 16 %.
CUERPO_33 = '''
<cfdi:Conceptos>
  <cfdi:Concepto ClaveProdServ="01010101" Cantidad="1" ClaveUnidad="ACT" Descripcion="A" ValorUnitario="300.00" Importe="300.00">
    <cfdi:Impuestos><cfdi:Traslados>
      <cfdi:Traslado Base="300.00" Impuesto="002" TipoFactor="Tasa" TasaOCuota="0.160000" Importe="48.00"/>
    </cfdi:Traslados></cfdi:Impuestos>
  </cfdi:Concepto>
  <cfdi:Concepto ClaveProdServ="01010101" Cantidad="1" ClaveUnidad="ACT" Descripcion="B" ValorUnitario="200.00" Importe="200.00">
    <cfdi:Impuestos><cfdi:Traslados>
      <cfdi:Traslado Base="200.00" Impuesto="002" TipoFactor="Tasa" TasaOCuota="0.160000" Importe="32.00"/>
    </cfdi:Traslados></cfdi:Impuestos>
  </cfdi:Concepto>
</cfdi:Conceptos>
<cfdi:Impuestos TotalImpuestosTrasladados="80.00"><cfdi:Traslados>
  <cfdi:Traslado Impuesto="002" TipoFactor="Tasa" TasaOCuota="0.160000" Importe="80.00"/>
</cfdi:Traslados></cfdi:Impuestos>'''

# Honorarios: IVA 16 % trasladado, retención de ISR 10 % y de IVA 10.6667 %.
CUERPO_HONORARIOS = '''
<cfdi:Conceptos>
  <cfdi:Concepto ClaveProdServ="80111600" Cantidad="1" ClaveUnidad="E48" Descripcion="Honorarios"
      ValorUnitario="1000.00" Importe="1000.00" ObjetoImp="02">
    <cfdi:Impuestos>
      <cfdi:Traslados>
        <cfdi:Traslado Base="1000.00" Impuesto="002" TipoFactor="Tasa" TasaOCuota="0.160000" Importe="160.00"/>
      </cfdi:Traslados>
      <cfdi:Retenciones>
        <cfdi:Retencion Base="1000.00" Impuesto="001" TipoFactor="Tasa" TasaOCuota="0.100000" Importe="100.00"/>
        <cfdi:Retencion Base="1000.00" Impuesto="002" TipoFactor="Tasa" TasaOCuota="0.106667" Importe="106.67"/>
      </cfdi:Retenciones>
    </cfdi:Impuestos>
  </cfdi:Concepto>
</cfdi:Conceptos>
<cfdi:Impuestos TotalImpuestosTrasladados="160.00" TotalImpuestosRetenidos="206.67">
  <cfdi:Retenciones>
    <cfdi:Retencion Impuesto="001" Importe="100.00"/>
    <cfdi:Retencion Impuesto="002" Importe="106.67"/>
  </cfdi:Retenciones>
  <cfdi:Traslados>
    <cfdi:Traslado Base="1000.00" Impuesto="002" TipoFactor="Tasa" TasaOCuota="0.160000" Importe="160.00"/>
  </cfdi:Traslados>
</cfdi:Impuestos>'''

# Retención declarada solo en el nodo raíz (sin impuestos por concepto).
CUERPO_RETENCION_SOLO_RAIZ = '''
<cfdi:Conceptos>
  <cfdi:Concepto ClaveProdServ="80111600" Cantidad="1" ClaveUnidad="E48" Descripcion="Servicio"
      ValorUnitario="1000.00" Importe="1000.00"/>
</cfdi:Conceptos>
<cfdi:Impuestos TotalImpuestosRetenidos="100.00">
  <cfdi:Retenciones><cfdi:Retencion Impuesto="001" Importe="100.00"/></cfdi:Retenciones>
</cfdi:Impuestos>'''


def _mapa(impuestos):
    return {(i.ambito, i.impuesto, i.tipo_factor, i.tasa_o_cuota): (i.base, i.importe) for i in impuestos}


def test_resumen_separa_tasa_16_tasa_0_y_exento():
    p = CFDIParser().parse_xml(_cfdi(CUERPO_MIXTO))

    assert _mapa(p.resumen_impuestos) == {
        ("traslado", "002", "Tasa", D("0.160000")): (D("800.00"), D("128.00")),
        ("traslado", "002", "Tasa", D("0.000000")): (D("150.00"), D("0.00")),
        ("traslado", "002", "Exento", None): (D("50.00"), D("0.00")),
    }
    assert p.iva_trasladado == D("128.00")  # el total de siempre no cambia


def test_resumen_cfdi_33_toma_la_base_de_los_conceptos():
    p = CFDIParser().parse_xml(_cfdi(CUERPO_33, version="3.3", subtotal="500.00", total="580.00"))

    assert _mapa(p.resumen_impuestos) == {
        ("traslado", "002", "Tasa", D("0.160000")): (D("500.00"), D("80.00")),
    }


def test_resumen_incluye_retenciones_con_base_y_tasa():
    p = CFDIParser().parse_xml(_cfdi(CUERPO_HONORARIOS, total="953.33"))

    mapa = _mapa(p.resumen_impuestos)
    assert mapa[("retencion", "001", "Tasa", D("0.100000"))] == (D("1000.00"), D("100.00"))
    assert mapa[("retencion", "002", "Tasa", D("0.106667"))] == (D("1000.00"), D("106.67"))
    assert mapa[("traslado", "002", "Tasa", D("0.160000"))] == (D("1000.00"), D("160.00"))
    assert len(mapa) == 3


def test_retencion_solo_en_raiz_queda_sin_tasa_ni_base():
    p = CFDIParser().parse_xml(_cfdi(CUERPO_RETENCION_SOLO_RAIZ, total="900.00"))

    assert _mapa(p.resumen_impuestos) == {
        ("retencion", "001", "Tasa", None): (D("0.00"), D("100.00")),
    }
```

- [ ] **Step 2: Correr las pruebas y verlas fallar**

Run: `python -m pytest backend/tests/test_cfdi_parser_detalle.py -v`
Expected: 4 FAIL con `AttributeError: 'CFDIParsed' object has no attribute 'resumen_impuestos'`.

- [ ] **Step 3: Implementar**

En `backend/cfdi_parser.py`:

(a) Debajo de `NS_PAGO10 = ...` agregar:

```python
CENTAVOS = Decimal("0.01")
SEIS_DECIMALES = Decimal("0.000001")
```

(b) Encima de la dataclass `DoctoRelacionado` (la Task 4 la usa ahí) agregar:

```python
@dataclass
class ImpuestoResumen:
    """Impuesto agrupado por ámbito, impuesto, factor y tasa, con su base."""
    ambito: str                      # "traslado" | "retencion"
    impuesto: str                    # 001 ISR, 002 IVA, 003 IEPS
    tipo_factor: str                 # Tasa | Cuota | Exento
    tasa_o_cuota: Optional[Decimal]  # None en Exento o si el XML no la trae
    base: Decimal
    importe: Decimal


def _agrupar_impuestos(filas: list[ImpuestoResumen]) -> list[ImpuestoResumen]:
    """Suma base e importe de las filas con la misma clave y redondea a centavos."""
    grupos: dict[tuple, list[Decimal]] = {}
    for f in filas:
        clave = (f.ambito, f.impuesto, f.tipo_factor, f.tasa_o_cuota)
        acumulado = grupos.setdefault(clave, [Decimal("0"), Decimal("0")])
        acumulado[0] += f.base
        acumulado[1] += f.importe
    return [
        ImpuestoResumen(ambito, impuesto, factor, tasa, base.quantize(CENTAVOS), importe.quantize(CENTAVOS))
        for (ambito, impuesto, factor, tasa), (base, importe) in grupos.items()
    ]
```

(c) En `CFDIParsed`, después del campo `total_retenciones: Decimal = Decimal("0")`, agregar:

```python
    # Impuestos agrupados por tasa con su base (traslados y retenciones).
    resumen_impuestos: list[ImpuestoResumen] = field(default_factory=list)
```

(d) En `CFDIParser.parse_xml`, después de la asignación de `parsed.total_retenciones`, agregar:

```python
        parsed.resumen_impuestos = self._resumen_impuestos(root, ns_cfdi)
```

(e) En `CFDIParser`, después del método `_extraer_impuestos_locales`, agregar:

```python
    def _leer_impuesto(self, nodo, ambito: str, sufijo: str = "") -> ImpuestoResumen:
        """Lee un nodo Traslado/Retencion. ``sufijo="DR"`` para los nodos del REP
        (BaseDR, ImpuestoDR, TipoFactorDR, TasaOCuotaDR, ImporteDR)."""
        factor = nodo.get(f"TipoFactor{sufijo}") or "Tasa"
        tasa: Optional[Decimal] = None
        tasa_str = nodo.get(f"TasaOCuota{sufijo}")
        if factor != "Exento" and tasa_str:
            try:
                tasa = Decimal(tasa_str).quantize(SEIS_DECIMALES)
            except Exception:
                tasa = None
        return ImpuestoResumen(
            ambito=ambito,
            impuesto=nodo.get(f"Impuesto{sufijo}", ""),
            tipo_factor=factor,
            tasa_o_cuota=tasa,
            base=self._decimal(nodo, f"Base{sufijo}"),
            importe=self._decimal(nodo, f"Importe{sufijo}"),
        )

    def _resumen_impuestos(self, root, ns_cfdi: str) -> list[ImpuestoResumen]:
        """Impuestos por tasa con su base.

        Traslados: del nodo raíz cuando todos traen Base (CFDI 4.0, cifra oficial
        ya agrupada); si no (CFDI 3.3), de los conceptos. Retenciones: de los
        conceptos (traen base y tasa); si no hay, del nodo raíz."""
        raiz = root.find(f"{ns_cfdi}Impuestos")
        t_raiz = raiz.findall(f"{ns_cfdi}Traslados/{ns_cfdi}Traslado") if raiz is not None else []
        r_raiz = raiz.findall(f"{ns_cfdi}Retenciones/{ns_cfdi}Retencion") if raiz is not None else []

        t_conceptos, r_conceptos = [], []
        for concepto in root.findall(f"{ns_cfdi}Conceptos/{ns_cfdi}Concepto"):
            t_conceptos += concepto.findall(f"{ns_cfdi}Impuestos/{ns_cfdi}Traslados/{ns_cfdi}Traslado")
            r_conceptos += concepto.findall(f"{ns_cfdi}Impuestos/{ns_cfdi}Retenciones/{ns_cfdi}Retencion")

        raiz_con_base = bool(t_raiz) and all(t.get("Base") for t in t_raiz)
        traslados = t_raiz if (raiz_con_base or not t_conceptos) else t_conceptos
        retenciones = r_conceptos or r_raiz

        filas = [self._leer_impuesto(n, "traslado") for n in traslados]
        filas += [self._leer_impuesto(n, "retencion") for n in retenciones]
        return _agrupar_impuestos(filas)
```

- [ ] **Step 4: Correr las pruebas y verlas pasar**

Run: `python -m pytest backend/tests/test_cfdi_parser_detalle.py backend/tests/test_cfdi_parser.py -v`
Expected: PASS — 38 passed (4 nuevas y las 34 de `test_cfdi_parser.py`).

- [ ] **Step 5: Commit**

```bash
git add backend/cfdi_parser.py backend/tests/test_cfdi_parser_detalle.py
git commit -m "feat: extraer impuestos del CFDI agrupados por tasa con su base"
```

---

### Task 3: Parser — conceptos y encabezados

**Files:**
- Modify: `backend/cfdi_parser.py`
- Test: `backend/tests/test_cfdi_parser_detalle.py`

**Interfaces:**
- Consumes: `ImpuestoResumen`, `CFDIParser._leer_impuesto` (Task 2).
- Produces:
  - `ConceptoCFDI(linea: int, clave_prod_serv, no_identificacion, cantidad: Decimal, clave_unidad, unidad, descripcion, valor_unitario: Decimal, importe: Decimal, descuento: Decimal, objeto_imp, cuenta_predial, impuestos: list[ImpuestoResumen])` (los campos sin tipo son `Optional[str]`)
  - `CFDIParsed.conceptos: list[ConceptoCFDI]`, `CFDIParsed.no_certificado: Optional[str]`, `CFDIParsed.periodicidad: Optional[str]`, `CFDIParsed.meses: Optional[str]`, `CFDIParsed.anio_global: Optional[int]`

- [ ] **Step 1: Escribir las pruebas que fallan**

Agregar al final de `backend/tests/test_cfdi_parser_detalle.py`:

```python
def test_conceptos_se_extraen_en_orden_con_sus_impuestos():
    p = CFDIParser().parse_xml(_cfdi(CUERPO_MIXTO))

    assert [c.linea for c in p.conceptos] == [1, 2, 3]
    primero = p.conceptos[0]
    assert (primero.clave_prod_serv, primero.no_identificacion, primero.clave_unidad, primero.unidad) == (
        "43211500", "SKU-1", "H87", "Pieza")
    assert (primero.cantidad, primero.valor_unitario, primero.importe, primero.descuento) == (
        D("2"), D("400.00"), D("800.00"), D("0.00"))
    assert (primero.descripcion, primero.objeto_imp) == ("Laptop", "02")
    assert _mapa(primero.impuestos) == {("traslado", "002", "Tasa", D("0.160000")): (D("800.00"), D("128.00"))}
    assert p.conceptos[1].no_identificacion is None
    assert p.conceptos[2].cuenta_predial == "PRED-9"


def test_encabezados_certificado_e_informacion_global():
    cuerpo = '<cfdi:InformacionGlobal Periodicidad="04" Meses="09" Año="2026"/>' + CUERPO_MIXTO
    p = CFDIParser().parse_xml(_cfdi(
        cuerpo, extra_attrs='NoCertificado="00001000000504465028" CondicionesDePago="30 días"'))

    assert p.no_certificado == "00001000000504465028"
    assert p.condiciones_pago == "30 días"
    assert (p.periodicidad, p.meses, p.anio_global) == ("04", "09", 2026)
    assert p.regimen_emisor == "601"


def test_sin_informacion_global_los_campos_quedan_vacios():
    p = CFDIParser().parse_xml(_cfdi(CUERPO_MIXTO))

    assert (p.no_certificado, p.periodicidad, p.meses, p.anio_global) == (None, None, None, None)
```

- [ ] **Step 2: Correr las pruebas y verlas fallar**

Run: `python -m pytest backend/tests/test_cfdi_parser_detalle.py -v -k "conceptos or encabezados or informacion_global"`
Expected: 3 FAIL con `AttributeError: 'CFDIParsed' object has no attribute 'conceptos'` (o `no_certificado`).

- [ ] **Step 3: Implementar**

En `backend/cfdi_parser.py`:

(a) Debajo de la dataclass `ImpuestoDetalle` agregar:

```python
@dataclass
class ConceptoCFDI:
    linea: int
    clave_prod_serv: Optional[str]
    no_identificacion: Optional[str]
    cantidad: Decimal
    clave_unidad: Optional[str]
    unidad: Optional[str]
    descripcion: Optional[str]
    valor_unitario: Decimal
    importe: Decimal
    descuento: Decimal
    objeto_imp: Optional[str]
    cuenta_predial: Optional[str]
    impuestos: list[ImpuestoResumen] = field(default_factory=list)
```

(b) En `CFDIParsed`, después de `resumen_impuestos`, agregar:

```python
    conceptos: list["ConceptoCFDI"] = field(default_factory=list)

    # Encabezados adicionales
    no_certificado: Optional[str] = None
    periodicidad: Optional[str] = None   # InformacionGlobal (factura global)
    meses: Optional[str] = None
    anio_global: Optional[int] = None
```

(c) En `parse_xml`, después de `parsed.resumen_impuestos = ...`, agregar:

```python
        parsed.conceptos = self._extraer_conceptos(root, ns_cfdi)
        parsed.no_certificado = self._attr(root, "NoCertificado")
        info_global = root.find(f"{ns_cfdi}InformacionGlobal")
        if info_global is not None:
            parsed.periodicidad = info_global.get("Periodicidad")
            parsed.meses = info_global.get("Meses")
            anio = info_global.get("Año", "")
            parsed.anio_global = int(anio) if anio.isdigit() else None
```

(d) En `CFDIParser`, después de `_resumen_impuestos`, agregar:

```python
    def _extraer_conceptos(self, root, ns_cfdi: str) -> list[ConceptoCFDI]:
        conceptos: list[ConceptoCFDI] = []
        nodos = root.findall(f"{ns_cfdi}Conceptos/{ns_cfdi}Concepto")
        for linea, nodo in enumerate(nodos, start=1):
            predial = nodo.find(f"{ns_cfdi}CuentaPredial")
            impuestos = [
                self._leer_impuesto(n, "traslado")
                for n in nodo.findall(f"{ns_cfdi}Impuestos/{ns_cfdi}Traslados/{ns_cfdi}Traslado")
            ] + [
                self._leer_impuesto(n, "retencion")
                for n in nodo.findall(f"{ns_cfdi}Impuestos/{ns_cfdi}Retenciones/{ns_cfdi}Retencion")
            ]
            conceptos.append(ConceptoCFDI(
                linea=linea,
                clave_prod_serv=nodo.get("ClaveProdServ"),
                no_identificacion=nodo.get("NoIdentificacion"),
                cantidad=self._decimal(nodo, "Cantidad"),
                clave_unidad=nodo.get("ClaveUnidad"),
                unidad=nodo.get("Unidad"),
                descripcion=nodo.get("Descripcion"),
                valor_unitario=self._decimal(nodo, "ValorUnitario"),
                importe=self._decimal(nodo, "Importe"),
                descuento=self._decimal(nodo, "Descuento"),
                objeto_imp=nodo.get("ObjetoImp"),
                cuenta_predial=predial.get("Numero") if predial is not None else None,
                impuestos=impuestos,
            ))
        return conceptos
```

- [ ] **Step 4: Correr las pruebas y verlas pasar**

Run: `python -m pytest backend/tests/test_cfdi_parser_detalle.py backend/tests/test_cfdi_parser.py -v`
Expected: PASS — 41 passed (7 en el archivo nuevo, 34 en el existente).

- [ ] **Step 5: Commit**

```bash
git add backend/cfdi_parser.py backend/tests/test_cfdi_parser_detalle.py
git commit -m "feat: extraer conceptos y encabezados adicionales del CFDI"
```

---

### Task 4: Parser — impuestos de cada pago (REP)

**Files:**
- Modify: `backend/cfdi_parser.py` (`DoctoRelacionado`, `PagoCFDI`, `_extraer_pagos`)
- Test: `backend/tests/test_cfdi_parser_detalle.py`

**Interfaces:**
- Consumes: `ImpuestoResumen`, `_agrupar_impuestos`, `CFDIParser._leer_impuesto(nodo, ambito, sufijo)` (Task 2).
- Produces:
  - `DoctoRelacionado.moneda_dr: Optional[str]`, `DoctoRelacionado.equivalencia_dr: Decimal` (1 si no viene), `DoctoRelacionado.impuestos: list[ImpuestoResumen]`
  - `PagoCFDI.version: str` (`"2.0"` o `"1.0"`)

- [ ] **Step 1: Escribir las pruebas que fallan**

Agregar al final de `backend/tests/test_cfdi_parser_detalle.py`:

```python
def _rep(nodo_pagos):
    return f'''<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4"
        xmlns:pago20="http://www.sat.gob.mx/Pagos20" xmlns:pago10="http://www.sat.gob.mx/Pagos"
        xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital"
        Version="4.0" Fecha="2026-01-20T10:00:00" TipoDeComprobante="P" SubTotal="0" Total="0"
        Moneda="XXX" LugarExpedicion="01000" Exportacion="01">
      <cfdi:Emisor Rfc="PROV010101AAA" Nombre="Proveedor SA" RegimenFiscal="601"/>
      <cfdi:Receptor Rfc="EMP010101AAA" Nombre="Empresa SA" UsoCFDI="CP01"/>
      <cfdi:Complemento>{nodo_pagos}<tfd:TimbreFiscalDigital
          UUID="99999999-8888-7777-6666-555555555555" FechaTimbrado="2026-01-20T10:05:00"/></cfdi:Complemento>
    </cfdi:Comprobante>'''


PAGOS_20 = '''<pago20:Pagos Version="2.0">
  <pago20:Totales MontoTotalPagos="6150.00"/>
  <pago20:Pago FechaPago="2026-01-20T12:00:00" FormaDePagoP="03" MonedaP="MXN" TipoCambioP="1" Monto="6150.00">
    <pago20:DoctoRelacionado IdDocumento="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee" MonedaDR="MXN"
        EquivalenciaDR="1" NumParcialidad="1" ImpSaldoAnt="12300.00" ImpPagado="6150.00"
        ImpSaldoInsoluto="6150.00" ObjetoImpDR="02">
      <pago20:ImpuestosDR>
        <pago20:RetencionesDR>
          <pago20:RetencionDR BaseDR="5000.00" ImpuestoDR="001" TipoFactorDR="Tasa" TasaOCuotaDR="0.100000" ImporteDR="500.00"/>
        </pago20:RetencionesDR>
        <pago20:TrasladosDR>
          <pago20:TrasladoDR BaseDR="5000.00" ImpuestoDR="002" TipoFactorDR="Tasa" TasaOCuotaDR="0.160000" ImporteDR="800.00"/>
          <pago20:TrasladoDR BaseDR="250.00" ImpuestoDR="002" TipoFactorDR="Tasa" TasaOCuotaDR="0.000000" ImporteDR="0.00"/>
          <pago20:TrasladoDR BaseDR="100.00" ImpuestoDR="002" TipoFactorDR="Exento"/>
        </pago20:TrasladosDR>
      </pago20:ImpuestosDR>
    </pago20:DoctoRelacionado>
  </pago20:Pago>
</pago20:Pagos>'''

PAGOS_10 = '''<pago10:Pagos Version="1.0">
  <pago10:Pago FechaPago="2021-03-20T12:00:00" FormaDePagoP="03" MonedaP="MXN" Monto="580.00">
    <pago10:DoctoRelacionado IdDocumento="33333333-3333-3333-3333-333333333333" MonedaDR="MXN"
        NumParcialidad="1" ImpSaldoAnt="580.00" ImpPagado="580.00" ImpSaldoInsoluto="0.00"/>
  </pago10:Pago>
</pago10:Pagos>'''


def test_rep_20_trae_los_impuestos_de_cada_documento():
    p = CFDIParser().parse_xml(_rep(PAGOS_20))

    pago = p.pagos[0]
    docto = pago.doctos_relacionados[0]
    assert pago.version == "2.0"
    assert (docto.moneda_dr, docto.equivalencia_dr) == ("MXN", D("1"))
    assert _mapa(docto.impuestos) == {
        ("retencion", "001", "Tasa", D("0.100000")): (D("5000.00"), D("500.00")),
        ("traslado", "002", "Tasa", D("0.160000")): (D("5000.00"), D("800.00")),
        ("traslado", "002", "Tasa", D("0.000000")): (D("250.00"), D("0.00")),
        ("traslado", "002", "Exento", None): (D("100.00"), D("0.00")),
    }


def test_rep_10_no_trae_impuestos_y_se_marca_como_version_1():
    p = CFDIParser().parse_xml(_rep(PAGOS_10))

    pago = p.pagos[0]
    assert pago.version == "1.0"
    assert pago.doctos_relacionados[0].impuestos == []
    assert pago.doctos_relacionados[0].equivalencia_dr == D("1")
```

- [ ] **Step 2: Correr las pruebas y verlas fallar**

Run: `python -m pytest backend/tests/test_cfdi_parser_detalle.py -v -k rep`
Expected: 2 FAIL con `AttributeError: 'PagoCFDI' object has no attribute 'version'`.

- [ ] **Step 3: Implementar**

En `backend/cfdi_parser.py`:

(a) Reemplazar las dataclasses `DoctoRelacionado` y `PagoCFDI` por:

```python
@dataclass
class DoctoRelacionado:
    uuid: str
    num_parcialidad: Optional[int]
    imp_pagado: Decimal
    imp_saldo_ant: Decimal
    imp_saldo_insoluto: Decimal
    moneda_dr: Optional[str] = None
    equivalencia_dr: Decimal = Decimal("1")
    # ImpuestosDR del REP 2.0 (vacío en Pagos 1.0).
    impuestos: list[ImpuestoResumen] = field(default_factory=list)


@dataclass
class PagoCFDI:
    fecha_pago: Optional[datetime]
    monto: Decimal
    moneda: str
    tipo_cambio: Decimal
    doctos_relacionados: list["DoctoRelacionado"] = field(default_factory=list)
    version: str = "2.0"   # "1.0" cuando el complemento es Pagos 1.0
```

(b) En `_extraer_pagos`, reemplazar el bloque `doctos: list[DoctoRelacionado] = []` … hasta el `pagos.append(PagoCFDI(...))` inclusive por:

```python
            doctos: list[DoctoRelacionado] = []
            for docto in pago_node.findall(f"{ns_pago}DoctoRelacionado"):
                parcialidad_str = docto.get("NumParcialidad")
                try:
                    impuestos_dr = [
                        self._leer_impuesto(n, "traslado", "DR")
                        for n in docto.findall(f"{ns_pago}ImpuestosDR/{ns_pago}TrasladosDR/{ns_pago}TrasladoDR")
                    ] + [
                        self._leer_impuesto(n, "retencion", "DR")
                        for n in docto.findall(f"{ns_pago}ImpuestosDR/{ns_pago}RetencionesDR/{ns_pago}RetencionDR")
                    ]
                    doctos.append(DoctoRelacionado(
                        uuid=docto.get("IdDocumento", "").strip().upper(),
                        num_parcialidad=int(parcialidad_str) if parcialidad_str else None,
                        imp_pagado=Decimal(docto.get("ImpPagado", "0")),
                        imp_saldo_ant=Decimal(docto.get("ImpSaldoAnt", "0")),
                        imp_saldo_insoluto=Decimal(docto.get("ImpSaldoInsoluto", "0")),
                        moneda_dr=docto.get("MonedaDR"),
                        equivalencia_dr=self._decimal(docto, "EquivalenciaDR", "1"),
                        impuestos=_agrupar_impuestos(impuestos_dr),
                    ))
                except Exception:
                    continue

            pagos.append(PagoCFDI(
                fecha_pago=self._parse_fecha(fecha_str),
                monto=monto,
                moneda=moneda,
                tipo_cambio=tipo_cambio,
                doctos_relacionados=doctos,
                version="2.0" if ns_pago == NS_PAGO20 else "1.0",
            ))
```

- [ ] **Step 4: Correr las pruebas y verlas pasar**

Run: `python -m pytest backend/tests/test_cfdi_parser_detalle.py backend/tests/test_cfdi_parser.py -v`
Expected: PASS — 43 passed (9 en el archivo nuevo, 34 en el existente).

- [ ] **Step 5: Commit**

```bash
git add backend/cfdi_parser.py backend/tests/test_cfdi_parser_detalle.py
git commit -m "feat: extraer impuestos por documento de los complementos de pago"
```

---

### Task 5: Parser — totales de nómina

**Files:**
- Modify: `backend/cfdi_parser.py`
- Test: `backend/tests/test_cfdi_parser_detalle.py`

**Interfaces:**
- Consumes: `CFDIParser._decimal`.
- Produces:
  - `NominaResumen(total_percepciones: Decimal, total_deducciones: Decimal, total_otros_pagos: Decimal, total_gravado: Decimal, total_exento: Decimal, isr_retenido: Decimal)`
  - `CFDIParsed.nomina: Optional[NominaResumen]` (None si el CFDI no trae complemento de nómina)

- [ ] **Step 1: Escribir las pruebas que fallan**

Agregar al final de `backend/tests/test_cfdi_parser_detalle.py`:

```python
NOMINA = '''<nomina12:Nomina xmlns:nomina12="http://www.sat.gob.mx/nomina12" Version="1.2" TipoNomina="O"
    FechaPago="2026-01-15" FechaInicialPago="2026-01-01" FechaFinalPago="2026-01-15" NumDiasPagados="15"
    TotalPercepciones="10000.00" TotalDeducciones="1500.00" TotalOtrosPagos="200.00">
  <nomina12:Percepciones TotalSueldos="10000.00" TotalGravado="9000.00" TotalExento="1000.00"/>
  <nomina12:Deducciones TotalOtrasDeducciones="300.00" TotalImpuestosRetenidos="1200.00"/>
</nomina12:Nomina>'''

CUERPO_NOMINA = '''<cfdi:Conceptos>
  <cfdi:Concepto ClaveProdServ="84111505" Cantidad="1" ClaveUnidad="ACT" Descripcion="Pago de nómina"
      ValorUnitario="10200.00" Importe="10200.00" Descuento="1500.00" ObjetoImp="01"/>
</cfdi:Conceptos>'''


def test_nomina_extrae_gravado_exento_e_isr_retenido():
    p = CFDIParser().parse_xml(_cfdi(
        CUERPO_NOMINA, tipo="N", subtotal="10200.00", total="8700.00",
        extra_attrs='Descuento="1500.00"', complemento=NOMINA))

    n = p.nomina
    assert (n.total_percepciones, n.total_deducciones, n.total_otros_pagos) == (
        D("10000.00"), D("1500.00"), D("200.00"))
    assert (n.total_gravado, n.total_exento, n.isr_retenido) == (D("9000.00"), D("1000.00"), D("1200.00"))


def test_cfdi_sin_complemento_de_nomina_deja_nomina_en_none():
    assert CFDIParser().parse_xml(_cfdi(CUERPO_MIXTO)).nomina is None
```

- [ ] **Step 2: Correr las pruebas y verlas fallar**

Run: `python -m pytest backend/tests/test_cfdi_parser_detalle.py -v -k nomina`
Expected: 2 FAIL con `AttributeError: 'CFDIParsed' object has no attribute 'nomina'`.

- [ ] **Step 3: Implementar**

En `backend/cfdi_parser.py`:

(a) Debajo de `NS_PAGO10 = ...` agregar:

```python
NS_NOMINA12 = "{http://www.sat.gob.mx/nomina12}"
```

(b) Debajo de la dataclass `ConceptoCFDI` agregar:

```python
@dataclass
class NominaResumen:
    total_percepciones: Decimal
    total_deducciones: Decimal
    total_otros_pagos: Decimal
    total_gravado: Decimal
    total_exento: Decimal
    isr_retenido: Decimal
```

(c) En `CFDIParsed`, después de `anio_global`, agregar:

```python
    # Totales del complemento de nómina (solo CFDI tipo N).
    nomina: Optional["NominaResumen"] = None
```

(d) En `parse_xml`, después del bloque de `info_global`, agregar:

```python
        parsed.nomina = self._extraer_nomina(root)
```

(e) En `CFDIParser`, después de `_extraer_conceptos`, agregar:

```python
    def _extraer_nomina(self, root) -> Optional[NominaResumen]:
        """Suma los totales de todos los nodos nomina12:Nomina del comprobante."""
        nodos = root.findall(f".//{NS_NOMINA12}Nomina")
        if not nodos:
            return None
        resumen = NominaResumen(*([Decimal("0")] * 6))
        for nodo in nodos:
            percepciones = nodo.find(f"{NS_NOMINA12}Percepciones")
            deducciones = nodo.find(f"{NS_NOMINA12}Deducciones")
            resumen.total_percepciones += self._decimal(nodo, "TotalPercepciones")
            resumen.total_deducciones += self._decimal(nodo, "TotalDeducciones")
            resumen.total_otros_pagos += self._decimal(nodo, "TotalOtrosPagos")
            resumen.total_gravado += self._decimal(percepciones, "TotalGravado")
            resumen.total_exento += self._decimal(percepciones, "TotalExento")
            resumen.isr_retenido += self._decimal(deducciones, "TotalImpuestosRetenidos")
        return resumen
```

`_decimal` ya devuelve 0 cuando el nodo es `None`, así que una nómina sin deducciones no truena.

- [ ] **Step 4: Correr toda la suite unitaria**

Run: `python -m pytest -m "not db" -q`
Expected: PASS — 367 passed (356 de la línea base + 11 nuevas).

- [ ] **Step 5: Revisión fiscal y commit**

Pedir al agente `dominio-fiscal` que revise `backend/cfdi_parser.py` (regla de raíz contra conceptos, retenciones, nómina); corregir lo que señale.

```bash
git add backend/cfdi_parser.py backend/tests/test_cfdi_parser_detalle.py
git commit -m "feat: extraer totales del complemento de nómina"
```

---

### Task 6: Persistir el detalle

**Files:**
- Modify: `backend/cfdi_store.py`
- Test: `backend/tests/test_e2e_detalle_cfdi.py` (crear)

**Interfaces:**
- Consumes: `CFDIParsed.resumen_impuestos`, `.conceptos`, `.no_certificado`, `.periodicidad`, `.meses`, `.anio_global`, `.nomina`, `.regimen_emisor`, `.condiciones_pago`; `DoctoRelacionado.moneda_dr`, `.equivalencia_dr`, `.impuestos`; `PagoCFDI.version` (Tasks 2–5); tablas de la Task 1.
- Produces:
  - `cfdi_store.DETALLE_VERSION: int = 1`
  - `cfdi_store.guardar_detalle(empresa_id: str, resultado) -> bool` — True si el CFDI existe en esa empresa y se guardó su detalle.
  - `insertar_cfdi` llama a `guardar_detalle`; `persistir_complemento_pago` guarda versión, moneda, equivalencia e impuestos de cada documento.

- [ ] **Step 1: Escribir las pruebas que fallan**

Crear `backend/tests/test_e2e_detalle_cfdi.py`:

```python
"""E2E del detalle fiscal del CFDI contra un Postgres real: lo que se sube por
la API queda con impuestos por tasa, conceptos, encabezados e impuestos de cada
pago, y re-subir no duplica. Se salta si no hay DB."""
from decimal import Decimal

import pytest

from backend.tests.conftest import db_disponible, headers_usuario_e2e

D = Decimal
RFC = "DET010101E2E"
CLIENTE = "XAXX010101000"
EMAIL = "e2e-detalle-cfdi@test.local"
PERIODO = "2026-01"
UUID_FACTURA = "0D0D0D0D-1111-2222-3333-44445555DE70"
UUID_REP = "0D0D0D0D-9999-8888-7777-66665555DE70"

pytestmark = [pytest.mark.db, pytest.mark.skipif(not db_disponible(), reason="Postgres no disponible (docker compose up -d db)")]


def _xml_factura() -> bytes:
    """Factura PPD con tres tasas: 10,000 al 16 %, 500 al 0 % y 200 exento. Total 12,300."""
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4" xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital"
    Version="4.0" Fecha="2026-01-10T10:00:00" TipoDeComprobante="I" SubTotal="10700.00" Total="12300.00"
    Moneda="MXN" MetodoPago="PPD" FormaPago="99" Exportacion="01" LugarExpedicion="01000"
    NoCertificado="00001000000504465028" CondicionesDePago="30 días">
  <cfdi:Emisor Rfc="{RFC}" Nombre="Emisora E2E" RegimenFiscal="601"/>
  <cfdi:Receptor Rfc="{CLIENTE}" Nombre="Cliente" UsoCFDI="G03" DomicilioFiscalReceptor="01000" RegimenFiscalReceptor="616"/>
  <cfdi:Conceptos>
    <cfdi:Concepto ClaveProdServ="43211500" Cantidad="1" ClaveUnidad="H87" Descripcion="Equipo"
        ValorUnitario="10000.00" Importe="10000.00" ObjetoImp="02">
      <cfdi:Impuestos><cfdi:Traslados>
        <cfdi:Traslado Base="10000.00" Impuesto="002" TipoFactor="Tasa" TasaOCuota="0.160000" Importe="1600.00"/>
      </cfdi:Traslados></cfdi:Impuestos>
    </cfdi:Concepto>
    <cfdi:Concepto ClaveProdServ="50161500" Cantidad="1" ClaveUnidad="KGM" Descripcion="Alimento"
        ValorUnitario="500.00" Importe="500.00" ObjetoImp="02">
      <cfdi:Impuestos><cfdi:Traslados>
        <cfdi:Traslado Base="500.00" Impuesto="002" TipoFactor="Tasa" TasaOCuota="0.000000" Importe="0.00"/>
      </cfdi:Traslados></cfdi:Impuestos>
    </cfdi:Concepto>
    <cfdi:Concepto ClaveProdServ="85121600" Cantidad="1" ClaveUnidad="E48" Descripcion="Consulta"
        ValorUnitario="200.00" Importe="200.00" ObjetoImp="02">
      <cfdi:Impuestos><cfdi:Traslados>
        <cfdi:Traslado Base="200.00" Impuesto="002" TipoFactor="Exento"/>
      </cfdi:Traslados></cfdi:Impuestos>
    </cfdi:Concepto>
  </cfdi:Conceptos>
  <cfdi:Impuestos TotalImpuestosTrasladados="1600.00"><cfdi:Traslados>
    <cfdi:Traslado Base="10000.00" Impuesto="002" TipoFactor="Tasa" TasaOCuota="0.160000" Importe="1600.00"/>
    <cfdi:Traslado Base="500.00" Impuesto="002" TipoFactor="Tasa" TasaOCuota="0.000000" Importe="0.00"/>
    <cfdi:Traslado Base="200.00" Impuesto="002" TipoFactor="Exento"/>
  </cfdi:Traslados></cfdi:Impuestos>
  <cfdi:Complemento><tfd:TimbreFiscalDigital UUID="{UUID_FACTURA}" FechaTimbrado="2026-01-10T10:01:00"/></cfdi:Complemento>
</cfdi:Comprobante>'''.encode()


def _xml_rep() -> bytes:
    """REP 2.0 que cobra la mitad (6,150) con sus ImpuestosDR."""
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4" xmlns:pago20="http://www.sat.gob.mx/Pagos20"
    xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital"
    Version="4.0" Fecha="2026-01-20T10:00:00" TipoDeComprobante="P" SubTotal="0" Total="0" Moneda="XXX"
    Exportacion="01" LugarExpedicion="01000">
  <cfdi:Emisor Rfc="{RFC}" Nombre="Emisora E2E" RegimenFiscal="601"/>
  <cfdi:Receptor Rfc="{CLIENTE}" Nombre="Cliente" UsoCFDI="CP01" DomicilioFiscalReceptor="01000" RegimenFiscalReceptor="616"/>
  <cfdi:Complemento>
    <pago20:Pagos Version="2.0">
      <pago20:Totales MontoTotalPagos="6150.00"/>
      <pago20:Pago FechaPago="2026-01-20T12:00:00" FormaDePagoP="03" MonedaP="MXN" TipoCambioP="1" Monto="6150.00">
        <pago20:DoctoRelacionado IdDocumento="{UUID_FACTURA}" MonedaDR="MXN" EquivalenciaDR="1" NumParcialidad="1"
            ImpSaldoAnt="12300.00" ImpPagado="6150.00" ImpSaldoInsoluto="6150.00" ObjetoImpDR="02">
          <pago20:ImpuestosDR><pago20:TrasladosDR>
            <pago20:TrasladoDR BaseDR="5000.00" ImpuestoDR="002" TipoFactorDR="Tasa" TasaOCuotaDR="0.160000" ImporteDR="800.00"/>
            <pago20:TrasladoDR BaseDR="250.00" ImpuestoDR="002" TipoFactorDR="Tasa" TasaOCuotaDR="0.000000" ImporteDR="0.00"/>
            <pago20:TrasladoDR BaseDR="100.00" ImpuestoDR="002" TipoFactorDR="Exento"/>
          </pago20:TrasladosDR></pago20:ImpuestosDR>
        </pago20:DoctoRelacionado>
      </pago20:Pago>
    </pago20:Pagos>
    <tfd:TimbreFiscalDigital UUID="{UUID_REP}" FechaTimbrado="2026-01-20T10:01:00"/>
  </cfdi:Complemento>
</cfdi:Comprobante>'''.encode()


def _limpiar(db):
    # cfdi_impuestos, cfdi_conceptos, pagos_* caen por CASCADE.
    db.execute("DELETE FROM empresas WHERE rfc = %s", (RFC,))
    db.execute("DELETE FROM cfdi WHERE uuid IN (%s, %s)", (UUID_FACTURA, UUID_REP))
    db.execute("DELETE FROM usuarios WHERE email = %s", (EMAIL,))


@pytest.fixture
def entorno():
    from fastapi.testclient import TestClient

    import backend.main_api as main
    from backend import db

    db.init_db()
    _limpiar(db)
    client = TestClient(main.app)
    try:
        headers = headers_usuario_e2e(db, EMAIL)
        r = client.post("/api/v1/mis-empresas", headers=headers,
                        json={"rfc": RFC, "razon_social": "Emisora E2E"})
        assert r.status_code == 201, r.text
        yield db, client, headers, r.json()["empresa_id"]
    finally:
        _limpiar(db)


def _subir(client, headers, empresa_id, nombre, xml):
    r = client.post(
        f"/api/v1/empresas/{empresa_id}/cfdi/upload", headers=headers,
        data={"periodo": PERIODO}, files=[("archivos", (nombre, xml, "text/xml"))],
    )
    assert r.status_code == 200, r.text
    assert r.json()["registros_procesados"] == 1, r.json()


def _impuestos_cfdi(db):
    filas = db.query_all(
        """SELECT i.ambito, i.impuesto, i.tipo_factor, i.tasa_o_cuota, i.base, i.importe
           FROM cfdi_impuestos i JOIN cfdi c ON c.id = i.cfdi_id WHERE c.uuid = %s""",
        (UUID_FACTURA,),
    )
    return {(f["ambito"], f["impuesto"], f["tipo_factor"], f["tasa_o_cuota"], f["base"], f["importe"]) for f in filas}


IMPUESTOS_FACTURA = {
    ("traslado", "002", "Tasa", D("0.160000"), D("10000.00"), D("1600.00")),
    ("traslado", "002", "Tasa", D("0.000000"), D("500.00"), D("0.00")),
    ("traslado", "002", "Exento", None, D("200.00"), D("0.00")),
}
IMPUESTOS_PAGO = {
    ("Tasa", D("0.160000"), D("5000.00"), D("800.00")),
    ("Tasa", D("0.000000"), D("250.00"), D("0.00")),
    ("Exento", None, D("100.00"), D("0.00")),
}


def test_subir_factura_guarda_impuestos_conceptos_y_encabezados(entorno):
    db, client, headers, empresa_id = entorno

    _subir(client, headers, empresa_id, "factura.xml", _xml_factura())

    cfdi = db.query_one(
        "SELECT regimen_emisor, condiciones_pago, no_certificado, detalle_version FROM cfdi WHERE uuid = %s",
        (UUID_FACTURA,),
    )
    assert cfdi == {"regimen_emisor": "601", "condiciones_pago": "30 días",
                    "no_certificado": "00001000000504465028", "detalle_version": 1}
    assert _impuestos_cfdi(db) == IMPUESTOS_FACTURA
    conceptos = db.query_all(
        """SELECT k.linea, k.descripcion, k.importe, k.impuestos
           FROM cfdi_conceptos k JOIN cfdi c ON c.id = k.cfdi_id WHERE c.uuid = %s ORDER BY k.linea""",
        (UUID_FACTURA,),
    )
    assert [(k["linea"], k["descripcion"], k["importe"]) for k in conceptos] == [
        (1, "Equipo", D("10000.00")), (2, "Alimento", D("500.00")), (3, "Consulta", D("200.00"))]
    assert conceptos[0]["impuestos"] == [{
        "ambito": "traslado", "impuesto": "002", "tipo_factor": "Tasa",
        "tasa_o_cuota": "0.160000", "base": "10000.00", "importe": "1600.00"}]


def test_resubir_la_factura_no_duplica_el_detalle(entorno):
    db, client, headers, empresa_id = entorno

    for _ in range(3):
        _subir(client, headers, empresa_id, "factura.xml", _xml_factura())

    assert _impuestos_cfdi(db) == IMPUESTOS_FACTURA
    n = db.query_one(
        "SELECT COUNT(*) AS n FROM cfdi_conceptos k JOIN cfdi c ON c.id = k.cfdi_id WHERE c.uuid = %s",
        (UUID_FACTURA,))["n"]
    assert n == 3


def test_subir_rep_guarda_impuestos_del_documento_y_resubirlo_no_duplica(entorno):
    db, client, headers, empresa_id = entorno
    _subir(client, headers, empresa_id, "factura.xml", _xml_factura())

    for _ in range(2):
        _subir(client, headers, empresa_id, "rep.xml", _xml_rep())

    filas = db.query_all(
        """SELECT i.tipo_factor, i.tasa_o_cuota, i.base, i.importe
           FROM pagos_relaciones_impuestos i
           JOIN pagos_relaciones pr ON pr.id = i.relacion_id WHERE pr.cfdi_uuid = %s""",
        (UUID_FACTURA,),
    )
    assert len(filas) == 3
    assert {(f["tipo_factor"], f["tasa_o_cuota"], f["base"], f["importe"]) for f in filas} == IMPUESTOS_PAGO
    rel = db.query_one(
        """SELECT pr.moneda_dr, pr.equivalencia_dr, pc.version_pago
           FROM pagos_relaciones pr JOIN pagos_cfdi pc ON pc.id = pr.pago_id WHERE pr.cfdi_uuid = %s""",
        (UUID_FACTURA,),
    )
    assert (rel["moneda_dr"], rel["equivalencia_dr"], rel["version_pago"]) == ("MXN", D("1"), "2.0")
```

- [ ] **Step 2: Correr las pruebas y verlas fallar**

Run: `python -m pytest backend/tests/test_e2e_detalle_cfdi.py -v`
Expected: 3 FAIL — la primera con `assert {... 'detalle_version': 0} == {... 'detalle_version': 1}` (los encabezados llegan en `None`).

- [ ] **Step 3: Implementar la persistencia**

En `backend/cfdi_store.py`:

(a) Debajo de `from . import db` agregar:

```python
# Versión del extractor de detalle. Subirla cuando el parser extraiga algo nuevo
# hace que reproceso.reprocesar_detalle vuelva a tomar los CFDI ya guardados.
DETALLE_VERSION = 1


def _tasa(valor):
    return None if valor is None else str(valor)


def _reemplazar_impuestos(tabla: str, columna_fk: str, fk_id: str, impuestos) -> None:
    """Borra e inserta los impuestos de un CFDI o de una relación de pago.
    ``tabla`` y ``columna_fk`` son constantes internas, nunca entrada externa."""
    db.execute(f"DELETE FROM {tabla} WHERE {columna_fk} = %s", (fk_id,))
    if not impuestos:
        return
    params: list = []
    for i in impuestos:
        params += [fk_id, i.ambito, i.impuesto, i.tipo_factor, _tasa(i.tasa_o_cuota), str(i.base), str(i.importe)]
    db.execute(
        f"INSERT INTO {tabla} ({columna_fk}, ambito, impuesto, tipo_factor, tasa_o_cuota, base, importe) VALUES "
        + ",".join(["(%s,%s,%s,%s,%s,%s,%s)"] * len(impuestos)),
        tuple(params),
    )


def _reemplazar_conceptos(cfdi_id: str, conceptos) -> None:
    db.execute("DELETE FROM cfdi_conceptos WHERE cfdi_id = %s", (cfdi_id,))
    if not conceptos:
        return
    params: list = []
    for c in conceptos:
        impuestos = [
            {"ambito": i.ambito, "impuesto": i.impuesto, "tipo_factor": i.tipo_factor,
             "tasa_o_cuota": _tasa(i.tasa_o_cuota), "base": str(i.base), "importe": str(i.importe)}
            for i in c.impuestos
        ]
        params += [
            cfdi_id, c.linea, c.clave_prod_serv, c.no_identificacion, str(c.cantidad),
            c.clave_unidad, c.unidad, c.descripcion, str(c.valor_unitario), str(c.importe),
            str(c.descuento), c.objeto_imp, c.cuenta_predial, json.dumps(impuestos),
        ]
    db.execute(
        """INSERT INTO cfdi_conceptos (
               cfdi_id, linea, clave_prod_serv, no_identificacion, cantidad,
               clave_unidad, unidad, descripcion, valor_unitario, importe,
               descuento, objeto_imp, cuenta_predial, impuestos
           ) VALUES """
        + ",".join(["(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"] * len(conceptos)),
        tuple(params),
    )


def guardar_detalle(empresa_id: str, resultado) -> bool:
    """Guarda encabezados adicionales, impuestos por tasa y conceptos de un CFDI
    ya insertado. Idempotente: reemplaza lo que hubiera. ``detalle_version`` se
    escribe al final, así un fallo a medias deja el CFDI como pendiente de
    reproceso. Devuelve False si el CFDI no existe en esa empresa."""
    n = resultado.nomina

    def _nomina(campo: str):
        return str(getattr(n, campo)) if n is not None else None

    fila = db.execute(
        """
        UPDATE cfdi SET
            regimen_emisor = %s, condiciones_pago = %s, no_certificado = %s,
            periodicidad = %s, meses = %s, anio_global = %s,
            nomina_percepciones = %s, nomina_deducciones = %s, nomina_otros_pagos = %s,
            nomina_gravado = %s, nomina_exento = %s, nomina_isr_retenido = %s
        WHERE uuid = %s AND empresa_id = %s
        RETURNING id
        """,
        (
            resultado.regimen_emisor, resultado.condiciones_pago, resultado.no_certificado,
            resultado.periodicidad, resultado.meses, resultado.anio_global,
            _nomina("total_percepciones"), _nomina("total_deducciones"), _nomina("total_otros_pagos"),
            _nomina("total_gravado"), _nomina("total_exento"), _nomina("isr_retenido"),
            resultado.uuid, empresa_id,
        ),
        returning=True,
    )
    if not fila:
        return False
    cfdi_id = str(fila["id"])
    _reemplazar_impuestos("cfdi_impuestos", "cfdi_id", cfdi_id, resultado.resumen_impuestos)
    _reemplazar_conceptos(cfdi_id, resultado.conceptos)
    db.execute("UPDATE cfdi SET detalle_version = %s WHERE id = %s", (DETALLE_VERSION, cfdi_id))
    return True
```

(b) En `persistir_complemento_pago`, justo después de la línea `pago_db_id = str(pago_row["id"])`, agregar:

```python
        db.execute("UPDATE pagos_cfdi SET version_pago = %s WHERE id = %s", (pago.version, pago_db_id))
```

(c) En el mismo método, dentro del `for docto in pago.doctos_relacionados:`, justo después del `db.execute(INSERT INTO pagos_relaciones …)` y antes de `if docto_uuid not in uuids_afectados:`, agregar:

```python
            relacion = db.query_one(
                """SELECT id FROM pagos_relaciones
                   WHERE pago_id = %s AND cfdi_uuid = %s
                     AND COALESCE(parcialidad, 0) = COALESCE(%s, 0)""",
                (pago_db_id, docto_uuid, docto.num_parcialidad),
            )
            if relacion:
                relacion_id = str(relacion["id"])
                db.execute(
                    "UPDATE pagos_relaciones SET moneda_dr = %s, equivalencia_dr = %s WHERE id = %s",
                    (docto.moneda_dr, str(docto.equivalencia_dr), relacion_id),
                )
                _reemplazar_impuestos("pagos_relaciones_impuestos", "relacion_id", relacion_id, docto.impuestos)
```

(d) En `insertar_cfdi`, después del `db.execute(INSERT INTO cfdi …)` y antes de `if resultado.tipo_comprobante == "P":`, agregar:

```python
    guardar_detalle(empresa_id, resultado)

```

- [ ] **Step 4: Correr las pruebas y verlas pasar**

Run: `python -m pytest backend/tests/test_e2e_detalle_cfdi.py backend/tests/test_e2e_pagos_rep.py -v`
Expected: PASS (3 nuevas y las de `test_e2e_pagos_rep.py` sin cambios).

- [ ] **Step 5: Correr la suite completa y commitear**

Run: `python -m pytest -q`
Expected: PASS — 404 passed (389 de la línea base + 11 del parser + 1 de la migración + 3 E2E).

```bash
git add backend/cfdi_store.py backend/tests/test_e2e_detalle_cfdi.py
git commit -m "feat: persistir impuestos por tasa, conceptos y detalle de pagos del CFDI"
```

---

### Task 7: Reproceso de los XML almacenados

**Files:**
- Create: `backend/reproceso.py`
- Modify: `backend/routers/admin.py`, `docs/openapi.yaml`
- Test: `backend/tests/test_e2e_detalle_cfdi.py`, `backend/tests/test_router_admin.py`

**Interfaces:**
- Consumes: `cfdi_store.DETALLE_VERSION`, `cfdi_store.guardar_detalle(empresa_id, resultado) -> bool`, `cfdi_store.persistir_complemento_pago(empresa_id, resultado)`, `CFDIParser().parse_xml(xml)`.
- Produces:
  - `reproceso.reprocesar_detalle(limite: int = 500, empresa_id: Optional[str] = None) -> dict` con llaves `procesados: int`, `errores: list[dict]` (cada uno `{"uuid": str, "error": str}`), `pendientes: int`.
  - `POST /api/v1/admin/reprocesar-cfdi?limite=500` (rol admin) que devuelve ese dict.

- [ ] **Step 1: Escribir las pruebas que fallan**

(a) Agregar al final de `backend/tests/test_e2e_detalle_cfdi.py`:

```python
def test_reproceso_reconstruye_el_detalle_de_cfdis_anteriores(entorno):
    db, client, headers, empresa_id = entorno
    from backend import reproceso

    _subir(client, headers, empresa_id, "factura.xml", _xml_factura())
    _subir(client, headers, empresa_id, "rep.xml", _xml_rep())
    # Simular CFDI guardados antes de la migración 028: sin detalle.
    db.execute("DELETE FROM cfdi_impuestos WHERE cfdi_id IN (SELECT id FROM cfdi WHERE empresa_id = %s)", (empresa_id,))
    db.execute("DELETE FROM cfdi_conceptos WHERE cfdi_id IN (SELECT id FROM cfdi WHERE empresa_id = %s)", (empresa_id,))
    db.execute(
        """DELETE FROM pagos_relaciones_impuestos WHERE relacion_id IN (
               SELECT pr.id FROM pagos_relaciones pr JOIN pagos_cfdi pc ON pc.id = pr.pago_id
               WHERE pc.empresa_id = %s)""",
        (empresa_id,),
    )
    db.execute("UPDATE cfdi SET detalle_version = 0, regimen_emisor = NULL WHERE empresa_id = %s", (empresa_id,))

    resultado = reproceso.reprocesar_detalle(empresa_id=empresa_id)

    assert resultado == {"procesados": 2, "errores": [], "pendientes": 0}
    assert _impuestos_cfdi(db) == IMPUESTOS_FACTURA
    assert db.query_one("SELECT regimen_emisor FROM cfdi WHERE uuid = %s", (UUID_FACTURA,))["regimen_emisor"] == "601"
    n = db.query_one(
        """SELECT COUNT(*) AS n FROM pagos_relaciones_impuestos i
           JOIN pagos_relaciones pr ON pr.id = i.relacion_id WHERE pr.cfdi_uuid = %s""",
        (UUID_FACTURA,))["n"]
    assert n == 3


def test_reproceso_marca_el_xml_ilegible_y_no_lo_reintenta(entorno):
    db, client, headers, empresa_id = entorno
    from backend import reproceso

    _subir(client, headers, empresa_id, "factura.xml", _xml_factura())
    db.execute("UPDATE cfdi SET detalle_version = 0, xml_raw = '<roto' WHERE uuid = %s", (UUID_FACTURA,))

    primero = reproceso.reprocesar_detalle(empresa_id=empresa_id)
    segundo = reproceso.reprocesar_detalle(empresa_id=empresa_id)

    assert primero["procesados"] == 0
    assert [e["uuid"] for e in primero["errores"]] == [UUID_FACTURA]
    assert primero["pendientes"] == 0
    assert segundo == {"procesados": 0, "errores": [], "pendientes": 0}
    assert db.query_one("SELECT detalle_version FROM cfdi WHERE uuid = %s", (UUID_FACTURA,))["detalle_version"] == -1
```

(b) Agregar al final de `backend/tests/test_router_admin.py`:

```python
# ─── POST /admin/reprocesar-cfdi ───────────────────────────────────────────────

def test_reprocesar_cfdi_devuelve_el_resumen(monkeypatch):
    from backend import reproceso
    from backend.routers import admin as admin_router

    _auth_admin()
    llamadas = []
    monkeypatch.setattr(reproceso, "reprocesar_detalle",
                        lambda limite=500: llamadas.append(limite) or {"procesados": 7, "errores": [], "pendientes": 3})
    monkeypatch.setattr(admin_router, "registrar_evento", lambda *a, **k: None)

    try:
        r = client.post("/api/v1/admin/reprocesar-cfdi?limite=50")
    finally:
        _teardown()

    assert r.status_code == 200
    assert r.json() == {"procesados": 7, "errores": [], "pendientes": 3}
    assert llamadas == [50]


def test_reprocesar_cfdi_rechaza_limite_fuera_de_rango():
    _auth_admin()
    try:
        r = client.post("/api/v1/admin/reprocesar-cfdi?limite=0")
    finally:
        _teardown()

    assert r.status_code == 422


def test_reprocesar_cfdi_sin_token_da_401():
    assert client.post("/api/v1/admin/reprocesar-cfdi").status_code == 401
```

- [ ] **Step 2: Correr las pruebas y verlas fallar**

Run: `python -m pytest backend/tests/test_router_admin.py backend/tests/test_e2e_detalle_cfdi.py -v -k reproces`
Expected: FAIL — `ImportError: cannot import name 'reproceso' from 'backend'` en las E2E y en la primera de admin; 404/405 en las otras dos de admin.

- [ ] **Step 3: Crear `backend/reproceso.py`**

```python
"""Reproceso del detalle fiscal de CFDI ya guardados.

Los CFDI anteriores a la migración 028 solo tienen totales. Aquí se vuelve a
parsear su ``xml_raw`` para llenar impuestos por tasa, conceptos, encabezados y
los impuestos de cada pago, sin volver a descargar nada del SAT.

Por lotes: cada llamada toma hasta ``limite`` CFDI con ``detalle_version``
menor a la actual. Un XML que no se puede leer se marca con -1 para que no
se reintente en cada lote.
"""
from __future__ import annotations

import logging
from typing import Optional

from . import cfdi_store, db
from .cfdi_parser import CFDIParser

_log = logging.getLogger(__name__)

_PENDIENTE = "detalle_version >= 0 AND detalle_version < %s AND xml_raw IS NOT NULL"


def reprocesar_detalle(limite: int = 500, empresa_id: Optional[str] = None) -> dict:
    """Reprocesa hasta ``limite`` CFDI pendientes (de una empresa o de todas).

    Devuelve ``{"procesados": int, "errores": [{"uuid", "error"}], "pendientes": int}``.
    """
    filtro_empresa = " AND empresa_id = %s" if empresa_id else ""
    params_empresa = (empresa_id,) if empresa_id else ()

    filas = db.query_all(
        f"SELECT empresa_id, uuid, xml_raw FROM cfdi WHERE {_PENDIENTE}{filtro_empresa} "
        "ORDER BY created_at LIMIT %s",
        (cfdi_store.DETALLE_VERSION, *params_empresa, limite),
    )

    parser = CFDIParser()
    procesados = 0
    errores: list[dict] = []
    for fila in filas:
        empresa = str(fila["empresa_id"])
        try:
            resultado = parser.parse_xml(fila["xml_raw"])
            if resultado.uuid != fila["uuid"]:
                raise ValueError("el UUID del XML no coincide con el del registro")
            cfdi_store.guardar_detalle(empresa, resultado)
            if resultado.tipo_comprobante == "P" and resultado.pagos:
                cfdi_store.persistir_complemento_pago(empresa, resultado)
            procesados += 1
        except Exception as exc:
            _log.warning("reproceso: CFDI %s no se pudo reprocesar: %s", fila["uuid"], exc)
            errores.append({"uuid": fila["uuid"], "error": str(exc)[:300]})
            db.execute(
                "UPDATE cfdi SET detalle_version = -1 WHERE uuid = %s AND empresa_id = %s",
                (fila["uuid"], empresa),
            )

    pendientes = db.query_one(
        f"SELECT COUNT(*) AS n FROM cfdi WHERE {_PENDIENTE}{filtro_empresa}",
        (cfdi_store.DETALLE_VERSION, *params_empresa),
    )["n"]
    return {"procesados": procesados, "errores": errores, "pendientes": int(pendientes)}
```

- [ ] **Step 4: Agregar el endpoint**

En `backend/routers/admin.py`:

(a) Cambiar el import de FastAPI y el de módulos internos:

```python
from fastapi import APIRouter, Depends, HTTPException, Query, status
```

```python
from .. import db, reproceso
```

(b) Agregar al final del archivo:

```python


@router.post("/reprocesar-cfdi")
async def reprocesar_cfdi(
    limite: int = Query(500, ge=1, le=5000, description="CFDI a reprocesar en esta llamada"),
    admin: dict = Depends(require_admin),
):
    """Reconstruye el detalle fiscal (impuestos por tasa, conceptos, pagos) de los
    CFDI guardados antes de la migración 028, por lotes. Llamar hasta que
    ``pendientes`` sea 0."""
    resultado = reproceso.reprocesar_detalle(limite=limite)
    registrar_evento(
        admin["user_id"], "reproceso_cfdi",
        metadata={"procesados": resultado["procesados"], "errores": len(resultado["errores"]),
                  "pendientes": resultado["pendientes"]},
    )
    return resultado
```

- [ ] **Step 5: Documentar el endpoint**

En `docs/openapi.yaml`, después del bloque `/api/v1/admin/metricas:` (y antes de la siguiente ruta o de `components:`), agregar con la misma sangría que las demás rutas:

```yaml
  /api/v1/admin/reprocesar-cfdi:
    post:
      operationId: reprocesarCfdiAdmin
      tags: [Admin]
      summary: Reprocesar el detalle fiscal de los CFDI almacenados
      description: >
        Requiere rol admin. Vuelve a leer el XML guardado de los CFDI sin detalle
        (impuestos por tasa, conceptos, impuestos de cada pago) por lotes. Llamar
        hasta que `pendientes` sea 0.
      parameters:
        - name: limite
          in: query
          required: false
          schema: { type: integer, minimum: 1, maximum: 5000, default: 500 }
      responses:
        '200':
          description: Resumen del lote
          content:
            application/json:
              schema:
                type: object
                properties:
                  procesados: { type: integer }
                  pendientes: { type: integer }
                  errores:
                    type: array
                    items:
                      type: object
                      properties:
                        uuid: { type: string }
                        error: { type: string }
        '401':
          $ref: '#/components/responses/UnauthorizedError'
        '403':
          $ref: '#/components/responses/ForbiddenError'
        '422':
          description: Límite fuera de rango
```

- [ ] **Step 6: Correr las pruebas y verlas pasar**

Run: `python -m pytest backend/tests/test_router_admin.py backend/tests/test_e2e_detalle_cfdi.py backend/tests/test_openapi_sync.py -v`
Expected: PASS (incluidas las 2 E2E de reproceso, las 3 de admin y la de sincronía con openapi).

- [ ] **Step 7: Suite completa y commit**

Run: `python -m pytest -q`
Expected: PASS — 409 passed.

```bash
git add backend/reproceso.py backend/routers/admin.py docs/openapi.yaml backend/tests/test_router_admin.py backend/tests/test_e2e_detalle_cfdi.py
git commit -m "feat: reprocesar el detalle fiscal de los CFDI almacenados"
```

---

### Cierre de la fase

- [ ] Con los CFDI reales de COPLASUR cargados (F0), ejecutar el reproceso en local hasta `pendientes: 0` y anotar en el PR cuántos quedaron con error y por qué.
- [ ] Cuadre de control con datos reales, septiembre 2026, emitidos vigentes: la suma de `cfdi_impuestos.importe` de traslados de IVA debe ser igual a la suma de `cfdi.iva_trasladado`. Consulta:

```sql
SELECT (SELECT COALESCE(SUM(i.importe), 0)
          FROM cfdi_impuestos i JOIN cfdi c ON c.id = i.cfdi_id
         WHERE c.empresa_id = :empresa AND i.ambito = 'traslado' AND i.impuesto = '002'
           AND c.fecha_emision >= '2026-09-01' AND c.fecha_emision < '2026-10-01') AS por_tasa,
       (SELECT COALESCE(SUM(c.iva_trasladado), 0)
          FROM cfdi c
         WHERE c.empresa_id = :empresa
           AND c.fecha_emision >= '2026-09-01' AND c.fecha_emision < '2026-10-01') AS encabezado;
```

  Las dos columnas deben coincidir al centavo. Si no, listar los CFDI que difieren antes de abrir el PR.
- [ ] Abrir el PR de `feat/fase1-detalle-fiscal-cfdi` hacia `main` y marcar F1 como hecha en el plan maestro.
