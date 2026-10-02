# F3.1 — API del listado de CFDI — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Exponer un listado de CFDI paginado en el servidor, con filtros, orden, conteos por tipo y totales del periodo y del acumulado, más el catálogo de columnas que lo describe.

**Architecture:** El catálogo de columnas (`backend/cfdi_columnas.py`) es la única fuente de qué se puede mostrar, ordenar y filtrar; cada columna lleva su expresión SQL. `backend/cfdi_listado.py` valida la consulta contra ese catálogo y arma el SQL con valores siempre parametrizados. El router `backend/routers/cfdis.py` es delgado: valida acceso, delega y traduce errores de validación a 422.

**Tech Stack:** Python 3.11, FastAPI, psycopg2 (`db.query_one` / `db.query_all`), PostgreSQL, pytest.

**Spec:** `docs/superpowers/specs/2026-10-02-f3-listado-cfdi-design.md` (entrega F3.1; secciones "API", "Datos" y criterios de aceptación 5, 6 y 7).

## Global Constraints

- Rama `feat/f3-1-api-listado-cfdi`, apilada sobre `feat/frontend-conexion-sat` (PR #11 a #13 sin fusionar).
- Importes en `Decimal` dentro del cálculo; se convierten a `float` solo al serializar la respuesta, como el resto de la API.
- `campo`, `orden` y `op` solo aceptan valores del catálogo; cualquier otro responde 422. Los valores del usuario van siempre como parámetros de la consulta, nunca concatenados.
- Máximo 10 filtros avanzados por consulta; `por_pagina` solo 30, 50 o 100.
- Importes de totales en pesos: importe × tipo de cambio (1 si falta o es 0).
- "Emitido" es `rfc_emisor = RFC de la empresa`; "recibido" es `rfc_receptor = RFC`.
- Sin CFDI, las cifras de totales van en `null`.
- Migraciones idempotentes y registradas en `backend/db.py::init_db`; endpoints documentados en `docs/openapi.yaml`.
- En F3.1 todas las pestañas usan las columnas y los totales de comprobante; las columnas y totales propios de Nómina y Pago son de F3.5.
- Línea base: `python -m pytest` → 430 passed.

## Review Focus

- Intento de inyección por `orden`, `campo` u `op` (por ejemplo `fecha_emision; DROP TABLE cfdi`) → 422 y el texto nunca llega al SQL (Task 4).
- Búsqueda con comodines `%` y `_` en `q` → se buscan literalmente, no como comodín (Task 4 y Task 5).
- CFDI en moneda extranjera → los totales lo suman en pesos, el listado muestra importe original y en pesos (Task 5).
- Periodo sin CFDI → totales en `null`, no ceros ni error (Task 5).
- Usuario sin acceso a la empresa → 403 en los tres endpoints (Task 6).

---

### Task 1: Migración 030

**Files:**
- Create: `database/migrations/030_listado_cfdi.sql`
- Modify: `backend/db.py` (`init_db`, después de la 028)
- Test: `backend/tests/test_migracion_030.py`

**Interfaces:**
- Produces: tabla `preferencias_tabla (usuario_id, vista, config, updated_at)`; índices `idx_cfdi_emp_emisor_fecha`, `idx_cfdi_emp_receptor_fecha`, `idx_cfdi_impuestos_no_iva`.

- [ ] **Step 1: Prueba que falla**

<!-- T1:test crear backend/tests/test_migracion_030.py -->
```python
"""Migración 030: índices del listado de CFDI y preferencias de tabla. Requiere Postgres."""
import pytest

from backend.tests.conftest import db_disponible

pytestmark = [pytest.mark.db, pytest.mark.skipif(not db_disponible(), reason="Postgres no disponible (docker compose up -d db)")]


def test_030_crea_indices_y_preferencias_y_se_puede_repetir():
    from backend import db

    db.init_db()
    db.init_db()

    indices = {f["indexname"] for f in db.query_all(
        "SELECT indexname FROM pg_indexes WHERE schemaname = 'public' AND tablename IN ('cfdi', 'cfdi_impuestos')")}
    assert {"idx_cfdi_emp_emisor_fecha", "idx_cfdi_emp_receptor_fecha", "idx_cfdi_impuestos_no_iva"} <= indices

    columnas = {f["column_name"] for f in db.query_all(
        "SELECT column_name FROM information_schema.columns WHERE table_name = 'preferencias_tabla'")}
    assert columnas == {"usuario_id", "vista", "config", "updated_at"}
```

- [ ] **Step 2:** Run: `python -m pytest backend/tests/test_migracion_030.py -q` — Expected: FAIL (faltan los índices).

- [ ] **Step 3: Migración**

<!-- T1:impl crear database/migrations/030_listado_cfdi.sql -->
```sql
-- ============================================================
-- Migración 030: Listado de CFDI
-- Idempotente: CREATE INDEX / CREATE TABLE IF NOT EXISTS.
--
-- El listado filtra siempre por empresa + RFC (emisor o receptor) + rango de
-- fecha; los índices de una sola columna de la 001 no lo cubren.
-- ============================================================

-- 1. Índices del listado (emitidos y recibidos).
CREATE INDEX IF NOT EXISTS idx_cfdi_emp_emisor_fecha
    ON cfdi (empresa_id, rfc_emisor, fecha_emision);
CREATE INDEX IF NOT EXISTS idx_cfdi_emp_receptor_fecha
    ON cfdi (empresa_id, rfc_receptor, fecha_emision);

-- 2. Los totales suman IEPS e ISR trasladado desde cfdi_impuestos; casi todas
--    sus filas son IVA (002), así que el índice parcial es pequeño.
CREATE INDEX IF NOT EXISTS idx_cfdi_impuestos_no_iva
    ON cfdi_impuestos (cfdi_id) WHERE impuesto <> '002';

-- 3. Orden y visibilidad de columnas por usuario y por tabla ("vista").
CREATE TABLE IF NOT EXISTS preferencias_tabla (
    usuario_id  UUID NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    vista       VARCHAR(80) NOT NULL,
    config      JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (usuario_id, vista)
);
```

<!-- T1:impl despues backend/db.py ::         _run_sql_file("029_ampliar_serie_cfdi.sql") -->
```python

        # 030 es idempotente — índices del listado de CFDI y preferencias de tabla por usuario
        _run_sql_file("030_listado_cfdi.sql")
```

- [ ] **Step 4:** Run: `python -m pytest backend/tests/test_migracion_030.py -q` — Expected: PASS (1 passed).

- [ ] **Step 5:** Actualizar `AGENTS.md` ("through `030_...`") y commit: `feat: agregar migración 030 con índices del listado de CFDI y preferencias de tabla`.

---

### Task 2: Catálogos del SAT

**Files:**
- Create: `backend/catalogos_sat.py`
- Test: `backend/tests/test_catalogos_sat.py`

**Interfaces:**
- Produces: diccionarios `FORMA_PAGO`, `METODO_PAGO`, `USO_CFDI`, `REGIMEN_FISCAL`, `TIPO_RELACION` (código → descripción) y `descripcion(catalogo: dict, codigo) -> Optional[str]` que devuelve `"<código> - <descripción>"`, el código solo si no está en el catálogo, o `None` si el código es vacío.

- [ ] **Step 1: Prueba que falla**

<!-- T2:test crear backend/tests/test_catalogos_sat.py -->
```python
"""Catálogos del SAT usados para describir códigos del CFDI."""
from backend import catalogos_sat as cat


def test_descripcion_une_codigo_y_texto():
    assert cat.descripcion(cat.FORMA_PAGO, "99") == "99 - Por definir"
    assert cat.descripcion(cat.METODO_PAGO, "PPD") == "PPD - Pago en parcialidades o diferido"
    assert cat.descripcion(cat.USO_CFDI, "G01") == "G01 - Adquisición de mercancías"
    assert cat.descripcion(cat.REGIMEN_FISCAL, "601") == "601 - General de Ley Personas Morales"
    assert cat.descripcion(cat.TIPO_RELACION, "07") == "07 - CFDI por aplicación de anticipo"


def test_codigo_fuera_de_catalogo_se_devuelve_tal_cual():
    assert cat.descripcion(cat.FORMA_PAGO, "ZZ") == "ZZ"


def test_codigo_vacio_no_tiene_descripcion():
    assert cat.descripcion(cat.FORMA_PAGO, None) is None
    assert cat.descripcion(cat.FORMA_PAGO, "") is None
```

- [ ] **Step 2:** Run: `python -m pytest backend/tests/test_catalogos_sat.py -q` — Expected: FAIL (`ImportError`).

- [ ] **Step 3: Implementación**

<!-- T2:impl crear backend/catalogos_sat.py -->
```python
"""Catálogos del SAT (Anexo 20) para mostrar la descripción de los códigos del
CFDI. Solo lectura: se usan para presentar, nunca para validar un comprobante
(un código que no esté aquí se muestra tal cual)."""
from __future__ import annotations

from typing import Optional

FORMA_PAGO = {
    "01": "Efectivo",
    "02": "Cheque nominativo",
    "03": "Transferencia electrónica de fondos",
    "04": "Tarjeta de crédito",
    "05": "Monedero electrónico",
    "06": "Dinero electrónico",
    "08": "Vales de despensa",
    "12": "Dación en pago",
    "13": "Pago por subrogación",
    "14": "Pago por consignación",
    "15": "Condonación",
    "17": "Compensación",
    "23": "Novación",
    "24": "Confusión",
    "25": "Remisión de deuda",
    "26": "Prescripción o caducidad",
    "27": "A satisfacción del acreedor",
    "28": "Tarjeta de débito",
    "29": "Tarjeta de servicios",
    "30": "Aplicación de anticipos",
    "31": "Intermediario pagos",
    "99": "Por definir",
}

METODO_PAGO = {
    "PUE": "Pago en una sola exhibición",
    "PPD": "Pago en parcialidades o diferido",
}

USO_CFDI = {
    "G01": "Adquisición de mercancías",
    "G02": "Devoluciones, descuentos o bonificaciones",
    "G03": "Gastos en general",
    "I01": "Construcciones",
    "I02": "Mobiliario y equipo de oficina por inversiones",
    "I03": "Equipo de transporte",
    "I04": "Equipo de cómputo y accesorios",
    "I05": "Dados, troqueles, moldes, matrices y herramental",
    "I06": "Comunicaciones telefónicas",
    "I07": "Comunicaciones satelitales",
    "I08": "Otra maquinaria y equipo",
    "D01": "Honorarios médicos, dentales y gastos hospitalarios",
    "D02": "Gastos médicos por incapacidad o discapacidad",
    "D03": "Gastos funerales",
    "D04": "Donativos",
    "D05": "Intereses reales efectivamente pagados por créditos hipotecarios (casa habitación)",
    "D06": "Aportaciones voluntarias al SAR",
    "D07": "Primas por seguros de gastos médicos",
    "D08": "Gastos de transportación escolar obligatoria",
    "D09": "Depósitos en cuentas para el ahorro, primas que tengan como base planes de pensiones",
    "D10": "Pagos por servicios educativos (colegiaturas)",
    "S01": "Sin efectos fiscales",
    "CP01": "Pagos",
    "CN01": "Nómina",
    "P01": "Por definir",
}

REGIMEN_FISCAL = {
    "601": "General de Ley Personas Morales",
    "603": "Personas Morales con Fines no Lucrativos",
    "605": "Sueldos y Salarios e Ingresos Asimilados a Salarios",
    "606": "Arrendamiento",
    "607": "Régimen de Enajenación o Adquisición de Bienes",
    "608": "Demás ingresos",
    "610": "Residentes en el Extranjero sin Establecimiento Permanente en México",
    "611": "Ingresos por Dividendos (socios y accionistas)",
    "612": "Personas Físicas con Actividades Empresariales y Profesionales",
    "614": "Ingresos por intereses",
    "615": "Régimen de los ingresos por obtención de premios",
    "616": "Sin obligaciones fiscales",
    "620": "Sociedades Cooperativas de Producción que optan por diferir sus ingresos",
    "621": "Incorporación Fiscal",
    "622": "Actividades Agrícolas, Ganaderas, Silvícolas y Pesqueras",
    "623": "Opcional para Grupos de Sociedades",
    "624": "Coordinados",
    "625": "Régimen de las Actividades Empresariales con ingresos a través de Plataformas Tecnológicas",
    "626": "Régimen Simplificado de Confianza",
}

TIPO_RELACION = {
    "01": "Nota de crédito de los documentos relacionados",
    "02": "Nota de débito de los documentos relacionados",
    "03": "Devolución de mercancía sobre facturas o traslados previos",
    "04": "Sustitución de los CFDI previos",
    "05": "Traslados de mercancías facturados previamente",
    "06": "Factura generada por los traslados previos",
    "07": "CFDI por aplicación de anticipo",
    "08": "Factura generada por pagos en parcialidades",
    "09": "Factura generada por pagos diferidos",
}


def descripcion(catalogo: dict[str, str], codigo: Optional[str]) -> Optional[str]:
    """``"<código> - <descripción>"``; el código solo si no está en el catálogo."""
    if not codigo:
        return None
    texto = catalogo.get(codigo)
    return f"{codigo} - {texto}" if texto else codigo
```

- [ ] **Step 4:** Run: `python -m pytest backend/tests/test_catalogos_sat.py -q` — Expected: PASS (3 passed).

- [ ] **Step 5:** Commit: `feat: agregar catálogos del SAT para describir códigos del CFDI`.

---

### Task 3: Catálogo de columnas

**Files:**
- Create: `backend/cfdi_columnas.py`
- Test: `backend/tests/test_cfdi_columnas.py`

**Interfaces:**
- Consumes: `catalogos_sat.FORMA_PAGO`, `METODO_PAGO`, `USO_CFDI`, `REGIMEN_FISCAL`.
- Produces:
  - `Columna` (dataclass congelada): `clave`, `etiqueta`, `tipo_dato`, `sql`, `visible`, `simple`, `opciones`, `grupo`; propiedades `ordenable`, `filtrable`; método `publica() -> dict` (sin `sql`).
  - `columnas(direccion: str, tipo: str) -> list[Columna]` (encabezado).
  - `columnas_concepto() -> list[Columna]`.
  - `DESCRIPCIONES: dict[str, tuple[str, dict]]` (clave derivada → (clave del código, catálogo)).
  - Constantes SQL `A_PESOS` y `LATERALES` (los `LEFT JOIN LATERAL` con alias `imp` y `pag` que usan algunas columnas).
  - `TIPOS_DATO: tuple[str, ...]`.

- [ ] **Step 1: Prueba que falla**

<!-- T3:test crear backend/tests/test_cfdi_columnas.py -->
```python
"""Catálogo de columnas del listado de CFDI."""
import pytest

from backend import cfdi_columnas as cc

VISIBLES = [
    "fecha_emision", "serie", "folio", "rfc_contraparte", "contraparte", "total", "saldo",
    "pagos_relacionados", "subtotal", "descuento", "neto", "traslado_iva", "uuid_sustituye",
    "uso_cfdi", "metodo_pago", "forma_pago", "categoria", "estado",
]


@pytest.mark.parametrize("direccion", ["emitidos", "recibidos"])
def test_claves_unicas_y_tipos_de_dato_validos(direccion):
    cols = cc.columnas(direccion, "I")
    claves = [c.clave for c in cols]

    assert len(claves) == len(set(claves))
    assert {c.tipo_dato for c in cols} <= set(cc.TIPOS_DATO)


def test_columnas_visibles_por_defecto_en_su_orden():
    assert [c.clave for c in cc.columnas("emitidos", "I") if c.visible] == VISIBLES


def test_la_contraparte_depende_de_la_direccion():
    emitidos = {c.clave: c for c in cc.columnas("emitidos", "I")}
    recibidos = {c.clave: c for c in cc.columnas("recibidos", "I")}

    assert (emitidos["rfc_contraparte"].etiqueta, emitidos["rfc_contraparte"].sql) == ("RFC receptor", "c.rfc_receptor")
    assert (emitidos["contraparte"].etiqueta, emitidos["contraparte"].sql) == ("Receptor", "c.nombre_receptor")
    assert (recibidos["rfc_contraparte"].etiqueta, recibidos["rfc_contraparte"].sql) == ("RFC emisor", "c.rfc_emisor")
    assert (recibidos["contraparte"].etiqueta, recibidos["contraparte"].sql) == ("Emisor", "c.nombre_emisor")


def test_columnas_calculadas_fuera_del_cfdi_no_se_ordenan_ni_filtran():
    cols = {c.clave: c for c in cc.columnas("emitidos", "I")}

    for clave in ("traslado_ieps", "retencion_ieps", "pagos_relacionados", "uuid_relacionado", "forma_pago_desc"):
        assert (cols[clave].ordenable, cols[clave].filtrable) == (False, False), clave
    assert (cols["total"].ordenable, cols["total"].filtrable) == (True, True)


def test_los_filtros_de_la_barra_no_se_repiten_en_el_filtro_avanzado():
    cols = {c.clave: c for c in cc.columnas("emitidos", "I")}

    for clave in ("tipo_comprobante", "estado", "metodo_pago"):
        assert cols[clave].ordenable is True
        assert cols[clave].filtrable is False


def test_la_version_publica_no_expone_el_sql():
    publica = cc.columnas("emitidos", "I")[0].publica()

    assert publica == {
        "clave": "fecha_emision", "etiqueta": "Fecha expedición", "tipo_dato": "fecha",
        "grupo": "encabezado", "visible_por_defecto": True, "ordenable": True, "filtrable": True,
        "opciones": [],
    }


def test_cada_descripcion_apunta_a_una_columna_de_codigo_existente():
    claves = {c.clave for c in cc.columnas("emitidos", "I")}

    for derivada, (origen, catalogo) in cc.DESCRIPCIONES.items():
        assert derivada in claves and origen in claves
        assert isinstance(catalogo, dict) and catalogo


def test_columnas_de_concepto():
    cols = cc.columnas_concepto()

    assert {c.grupo for c in cols} == {"concepto"}
    assert [c.clave for c in cols if c.visible] == [
        "clave_prod_serv", "cantidad", "clave_unidad", "descripcion", "valor_unitario",
        "importe", "descuento", "iva_traslado_base", "iva_traslado_importe",
    ]
```

- [ ] **Step 2:** Run: `python -m pytest backend/tests/test_cfdi_columnas.py -q` — Expected: FAIL (`ImportError`).

- [ ] **Step 3: Implementación**

<!-- T3:impl crear backend/cfdi_columnas.py -->
```python
"""Catálogo de columnas del listado de CFDI.

Única fuente de qué se puede mostrar, ordenar, filtrar y exportar. Cada columna
lleva su expresión SQL sobre el alias ``c`` (tabla ``cfdi``) o sobre las
subconsultas de ``LATERALES``; el frontend solo recibe la versión pública.
Lo que no está aquí no se puede pedir: ``cfdi_listado`` valida contra este
catálogo antes de armar cualquier consulta.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from . import catalogos_sat

TIPOS_DATO = ("texto", "fecha", "fecha_hora", "moneda", "numero", "booleano", "catalogo", "lista")

# Tipo de cambio a pesos; un comprobante en MXN lo trae en 1 (o vacío).
A_PESOS = "COALESCE(NULLIF(c.tipo_cambio, 0), 1)"

# Subconsultas por CFDI que usan algunas columnas. Solo se ejecutan sobre la
# página ya recortada, por eso sus columnas no se pueden ordenar ni filtrar.
LATERALES = """
    LEFT JOIN LATERAL (
        SELECT SUM(i.importe) FILTER (WHERE i.ambito = 'traslado'  AND i.impuesto = '003') AS traslado_ieps,
               SUM(i.importe) FILTER (WHERE i.ambito = 'retencion' AND i.impuesto = '003') AS retencion_ieps
        FROM cfdi_impuestos i
        WHERE i.cfdi_id = c.id AND i.impuesto <> '002'
    ) imp ON TRUE
    LEFT JOIN LATERAL (
        SELECT array_agg(DISTINCT pc.uuid_cfdi_pago) AS uuids
        FROM pagos_relaciones pr
        JOIN pagos_cfdi pc ON pc.id = pr.pago_id
        WHERE pc.empresa_id = c.empresa_id AND pr.cfdi_uuid = c.uuid
    ) pag ON TRUE
"""

# Filtros que ya viven en la barra del listado (pestaña de tipo, estado, método).
_FILTROS_DE_BARRA = {"tipo_comprobante", "estado", "metodo_pago"}

_RELACIONES = "jsonb_array_elements(COALESCE(c.cfdi_relacionados, '[]'::jsonb)) r"


@dataclass(frozen=True)
class Columna:
    clave: str
    etiqueta: str
    tipo_dato: str
    sql: Optional[str] = None          # None: se deriva en Python (descripciones de catálogo)
    visible: bool = False
    simple: bool = True                # False: depende de subconsultas
    opciones: tuple[str, ...] = ()     # valores válidos cuando tipo_dato == "catalogo"
    grupo: str = "encabezado"

    @property
    def ordenable(self) -> bool:
        return self.sql is not None and self.simple

    @property
    def filtrable(self) -> bool:
        return self.ordenable and self.clave not in _FILTROS_DE_BARRA

    def publica(self) -> dict:
        return {
            "clave": self.clave,
            "etiqueta": self.etiqueta,
            "tipo_dato": self.tipo_dato,
            "grupo": self.grupo,
            "visible_por_defecto": self.visible,
            "ordenable": self.ordenable,
            "filtrable": self.filtrable,
            "opciones": list(self.opciones),
        }


# Columna derivada → (columna con el código, catálogo que lo describe).
DESCRIPCIONES: dict[str, tuple[str, dict[str, str]]] = {
    "regimen_fiscal_receptor_desc": ("regimen_fiscal_receptor", catalogos_sat.REGIMEN_FISCAL),
    "regimen_emisor_desc": ("regimen_emisor", catalogos_sat.REGIMEN_FISCAL),
    "metodo_pago_desc": ("metodo_pago", catalogos_sat.METODO_PAGO),
    "forma_pago_desc": ("forma_pago", catalogos_sat.FORMA_PAGO),
    "uso_cfdi_desc": ("uso_cfdi", catalogos_sat.USO_CFDI),
}


def _categoria_sql(direccion: str) -> str:
    """Clasificación propia de FiscalCore (anticipos según la guía del SAT)."""
    operacion = "venta" if direccion == "emitidos" else "compra"
    return f"""CASE
        WHEN c.tipo_comprobante = 'I' AND c.es_anticipo_sat THEN 'anticipo'
        WHEN c.tipo_comprobante = 'I'
             AND COALESCE(c.cfdi_relacionados, '[]'::jsonb) @> '[{{"tipo_relacion": "07"}}]'::jsonb
            THEN 'factura_con_anticipo'
        WHEN c.tipo_comprobante = 'I' THEN '{operacion}'
        WHEN c.tipo_comprobante = 'E' AND c.forma_pago = '30' THEN 'aplicacion_anticipo'
        WHEN c.tipo_comprobante = 'E' THEN 'nota_credito'
    END"""


def columnas(direccion: str, tipo: str) -> list[Columna]:
    """Columnas de encabezado del listado. ``tipo`` se recibe para que Nómina y
    Pago tengan su propio juego (F3.5); hoy todos los tipos comparten este."""
    emitidos = direccion == "emitidos"
    rfc_sql, nombre_sql = ("c.rfc_receptor", "c.nombre_receptor") if emitidos else ("c.rfc_emisor", "c.nombre_emisor")
    rfc_etq, nombre_etq = ("RFC receptor", "Receptor") if emitidos else ("RFC emisor", "Emisor")
    operacion = "venta" if emitidos else "compra"
    neto = "(c.subtotal - COALESCE(c.descuento, 0))"
    saldo = "(CASE WHEN c.metodo_pago = 'PPD' THEN GREATEST(c.total - COALESCE(c.monto_cobrado, 0), 0) ELSE 0 END)"

    return [
        # Identificación
        Columna("fecha_emision", "Fecha expedición", "fecha", "c.fecha_emision", visible=True),
        Columna("serie", "Serie", "texto", "c.serie", visible=True),
        Columna("folio", "Folio", "texto", "c.folio", visible=True),
        Columna("uuid", "UUID", "texto", "c.uuid"),
        Columna("version", "Versión", "texto", "c.version"),
        Columna("tipo_comprobante", "Tipo comprobante", "catalogo", "c.tipo_comprobante",
                opciones=("I", "E", "T", "N", "P")),
        Columna("lugar_expedicion", "Lugar de expedición", "texto", "c.lugar_expedicion"),
        Columna("fecha_timbrado", "Fecha timbrado", "fecha_hora", "c.fecha_timbrado"),
        Columna("no_certificado", "No. certificado", "texto", "c.no_certificado"),
        Columna("exportacion", "Exportación", "texto", "c.exportacion"),
        # Contraparte
        Columna("rfc_contraparte", rfc_etq, "texto", rfc_sql, visible=True),
        Columna("contraparte", nombre_etq, "texto", nombre_sql, visible=True),
        Columna("regimen_fiscal_receptor", "Régimen fiscal receptor", "texto", "c.regimen_fiscal_receptor"),
        Columna("regimen_fiscal_receptor_desc", "Régimen fiscal receptor descripción", "texto"),
        Columna("regimen_emisor", "Régimen fiscal emisor", "texto", "c.regimen_emisor"),
        Columna("regimen_emisor_desc", "Régimen fiscal emisor descripción", "texto"),
        # Importes
        Columna("total", "Total", "moneda", "c.total", visible=True),
        Columna("saldo", "Saldo de la factura", "moneda", saldo, visible=True),
        Columna("pagos_relacionados", "CFDIs de pago relacionados", "lista", "pag.uuids", visible=True, simple=False),
        Columna("subtotal", "Subtotal", "moneda", "c.subtotal", visible=True),
        Columna("descuento", "Total descuento", "moneda", "COALESCE(c.descuento, 0)", visible=True),
        Columna("neto", "Neto", "moneda", neto, visible=True),
        Columna("total_mxn", "Total MXN", "moneda", f"(c.total * {A_PESOS})"),
        Columna("subtotal_mxn", "Subtotal MXN", "moneda", f"(c.subtotal * {A_PESOS})"),
        Columna("descuento_mxn", "Total descuento MXN", "moneda", f"(COALESCE(c.descuento, 0) * {A_PESOS})"),
        Columna("neto_mxn", "Neto MXN", "moneda", f"({neto} * {A_PESOS})"),
        Columna("moneda", "Moneda", "texto", "c.moneda"),
        Columna("tipo_cambio", "Tipo de cambio", "numero", "c.tipo_cambio"),
        # Impuestos
        Columna("traslado_iva", "Traslado IVA", "moneda", "COALESCE(c.iva_trasladado, 0)", visible=True),
        Columna("traslado_iva_mxn", "Traslado IVA MXN", "moneda", f"(COALESCE(c.iva_trasladado, 0) * {A_PESOS})"),
        Columna("traslado_ieps", "Traslado IEPS", "moneda", "COALESCE(imp.traslado_ieps, 0)", simple=False),
        Columna("retencion_iva", "Retención IVA", "moneda", "COALESCE(c.iva_retenido, 0)"),
        Columna("retencion_iva_mxn", "Retención IVA MXN", "moneda", f"(COALESCE(c.iva_retenido, 0) * {A_PESOS})"),
        Columna("retencion_isr", "Retención ISR", "moneda", "COALESCE(c.isr_retenido, 0)"),
        Columna("retencion_isr_mxn", "Retención ISR MXN", "moneda", f"(COALESCE(c.isr_retenido, 0) * {A_PESOS})"),
        Columna("retencion_ieps", "Retención IEPS", "moneda", "COALESCE(imp.retencion_ieps, 0)", simple=False),
        # Relaciones
        Columna("uuid_relacionado", "UUID relacionado", "lista",
                f"(SELECT array_agg(u) FROM {_RELACIONES}, jsonb_array_elements_text(r->'uuids') u)", simple=False),
        Columna("tipo_relacion", "Tipo de relación", "texto",
                f"(SELECT string_agg(DISTINCT r->>'tipo_relacion', ', ') FROM {_RELACIONES})", simple=False),
        Columna("uuid_sustituye", "UUID que sustituye", "lista",
                f"(SELECT array_agg(u) FROM {_RELACIONES}, jsonb_array_elements_text(r->'uuids') u"
                " WHERE r->>'tipo_relacion' = '04')", visible=True, simple=False),
        # Pago
        Columna("uso_cfdi", "Uso de CFDI", "texto", "c.uso_cfdi", visible=True),
        Columna("uso_cfdi_desc", "Uso de CFDI descripción", "texto"),
        Columna("metodo_pago", "Método pago código", "catalogo", "c.metodo_pago", visible=True,
                opciones=("PUE", "PPD")),
        Columna("metodo_pago_desc", "Método pago", "texto"),
        Columna("forma_pago", "Forma de pago código", "texto", "c.forma_pago", visible=True),
        Columna("forma_pago_desc", "Forma de pago", "texto"),
        Columna("condiciones_pago", "Condiciones de pago", "texto", "c.condiciones_pago"),
        # Factura global
        Columna("periodicidad", "Periodicidad", "texto", "c.periodicidad"),
        Columna("meses", "Meses", "texto", "c.meses"),
        Columna("anio_global", "Año", "numero", "c.anio_global"),
        # Propias de FiscalCore
        Columna("categoria", "Categoría", "catalogo", _categoria_sql(direccion), visible=True,
                opciones=(operacion, "anticipo", "factura_con_anticipo", "aplicacion_anticipo", "nota_credito")),
        Columna("estado", "Estado", "catalogo", "c.estado", visible=True,
                opciones=("vigente", "cancelado", "sustituido")),
        Columna("estado_pago", "Estado de pago", "texto", "c.estado_pago"),
    ]


def columnas_concepto() -> list[Columna]:
    """Columnas de la fila desplegada (conceptos). En F3.1 solo se publican; las
    consume el detalle del CFDI en F3.3."""
    def c(clave: str, etiqueta: str, tipo: str, visible: bool = False) -> Columna:
        return Columna(clave, etiqueta, tipo, visible=visible, grupo="concepto")

    return [
        c("clave_prod_serv", "Clave producto", "texto", True),
        c("no_identificacion", "No. identificación", "texto"),
        c("cantidad", "Cantidad", "numero", True),
        c("clave_unidad", "Clave unidad", "texto", True),
        c("unidad", "Unidad", "texto"),
        c("descripcion", "Descripción", "texto", True),
        c("valor_unitario", "Valor unitario", "moneda", True),
        c("importe", "Importe", "moneda", True),
        c("descuento", "Descuento", "moneda", True),
        c("objeto_imp", "Objeto de impuesto", "texto"),
        c("cuenta_predial", "Cuenta predial", "texto"),
        c("iva_traslado_base", "Base de IVA traslado", "moneda", True),
        c("iva_traslado_tasa", "Tasa o cuota IVA traslado", "numero"),
        c("iva_traslado_importe", "Importe IVA traslado", "moneda", True),
        c("ieps_base", "Base IEPS", "moneda"),
        c("ieps_tasa", "Tasa o cuota IEPS", "numero"),
        c("ieps_importe", "Importe IEPS", "moneda"),
        c("iva_retencion_base", "Base IVA retención", "moneda"),
        c("iva_retencion_tasa", "Tasa o cuota IVA retención", "numero"),
        c("iva_retencion_importe", "Importe IVA retención", "moneda"),
        c("isr_base", "Base ISR", "moneda"),
        c("isr_tasa", "Tasa o cuota ISR", "numero"),
        c("isr_importe", "Importe ISR", "moneda"),
    ]
```

- [ ] **Step 4:** Run: `python -m pytest backend/tests/test_cfdi_columnas.py -q` — Expected: PASS (9 passed).

- [ ] **Step 5:** Commit: `feat: agregar el catálogo de columnas del listado de CFDI`.

---

### Task 4: Validación de la consulta y armado del SQL

**Files:**
- Create: `backend/cfdi_listado.py`
- Test: `backend/tests/test_cfdi_listado.py`

**Interfaces:**
- Consumes: `cfdi_columnas.columnas`, `Columna`.
- Produces:
  - `FiltroInvalido(ValueError)`.
  - `Consulta` (dataclass): `direccion`, `periodo`, `tipo`, `estado`, `metodo`, `pago`, `q`, `filtros: list[dict]`, `orden`, `dir`, `pagina`, `por_pagina`.
  - `validar(direccion, periodo, tipo="I", estado="vigente", metodo="todos", pago="todos", q=None, filtros=None, orden="fecha_emision", dir="asc", pagina=1, por_pagina=30) -> Consulta` — `filtros` acepta una cadena JSON o una lista; lanza `FiltroInvalido`.
  - `rango(periodo: str) -> tuple[date, date]` (primer día del mes, primer día del mes siguiente).
  - `condiciones(c: Consulta, empresa_id: str, rfc: str, *, desde: date, hasta: date, con_tipo: bool = True) -> tuple[str, list]` (fragmento `WHERE` sin la palabra `WHERE`, y sus parámetros).

- [ ] **Step 1: Prueba que falla**

<!-- T4:test crear backend/tests/test_cfdi_listado.py -->
```python
"""Validación de la consulta del listado de CFDI y armado del SQL (sin DB)."""
import json
from datetime import date
from decimal import Decimal

import pytest

from backend import cfdi_listado as cl


def _condiciones(**kw):
    c = cl.validar("emitidos", "2026-09", **kw)
    return cl.condiciones(c, "emp-1", "AAA010101AAA", desde=date(2026, 9, 1), hasta=date(2026, 10, 1))


def test_valores_por_defecto():
    c = cl.validar("emitidos", "2026-09")

    assert (c.tipo, c.estado, c.metodo, c.pago, c.q, c.filtros) == ("I", "vigente", "todos", "todos", None, [])
    assert (c.orden, c.dir, c.pagina, c.por_pagina) == ("fecha_emision", "asc", 1, 30)


def test_rango_del_periodo():
    assert cl.rango("2026-09") == (date(2026, 9, 1), date(2026, 10, 1))
    assert cl.rango("2026-12") == (date(2026, 12, 1), date(2027, 1, 1))


@pytest.mark.parametrize("kw", [
    {"direccion": "ambos"},
    {"periodo": "2026-13"},
    {"periodo": "septiembre"},
    {"tipo": "X"},
    {"estado": "borrado"},
    {"metodo": "CONTADO"},
    {"pago": "algo"},
    {"dir": "arriba"},
    {"pagina": 0},
    {"por_pagina": 31},
    {"orden": "columna_inexistente"},
    {"orden": "fecha_emision; DROP TABLE cfdi"},
    {"orden": "pagos_relacionados"},          # existe, pero no es ordenable
    {"q": "x" * 101},
])
def test_parametros_fuera_de_catalogo_se_rechazan(kw):
    base = {"direccion": "emitidos", "periodo": "2026-09"}
    base.update(kw)

    with pytest.raises(cl.FiltroInvalido):
        cl.validar(**base)


@pytest.mark.parametrize("filtros", [
    "esto no es json",
    '{"campo": "total"}',                                               # no es lista
    '[{"campo": "inexistente", "op": "igual", "valor": 1}]',
    '[{"campo": "pagos_relacionados", "op": "igual", "valor": "x"}]',   # no filtrable
    '[{"campo": "estado", "op": "igual", "valor": "vigente"}]',         # filtro de barra
    '[{"campo": "total", "op": "contiene", "valor": 1}]',               # operador de otro tipo
    '[{"campo": "total", "op": "mayor", "valor": "mucho"}]',
    '[{"campo": "total", "op": "mayor; DROP TABLE cfdi", "valor": 1}]',
    '[{"campo": "total", "op": "entre", "valor": [1]}]',
    '[{"campo": "fecha_emision", "op": "igual", "valor": "ayer"}]',
    '[{"campo": "categoria", "op": "igual", "valor": "inventada"}]',
    '[{"campo": "serie", "op": "igual", "valor": {"a": 1}}]',
    '[{"campo": "serie", "op": "igual"}]',
    json.dumps([{"campo": "serie", "op": "igual", "valor": "A"}] * 11),
    json.dumps([{"campo": "serie", "op": "igual", "valor": "x" * 201}]),
])
def test_filtros_avanzados_invalidos_se_rechazan(filtros):
    with pytest.raises(cl.FiltroInvalido):
        cl.validar("emitidos", "2026-09", filtros=filtros)


def test_condiciones_base_de_emitidos_y_recibidos():
    sql, params = _condiciones()
    assert sql.startswith("c.empresa_id = %s AND c.rfc_emisor = %s AND c.fecha_emision >= %s AND c.fecha_emision < %s")
    assert params[:4] == ["emp-1", "AAA010101AAA", date(2026, 9, 1), date(2026, 10, 1)]
    assert params[4:] == ["I", "vigente"]

    recibidos = cl.validar("recibidos", "2026-09", estado="todos")
    sql, params = cl.condiciones(recibidos, "emp-1", "AAA010101AAA", desde=date(2026, 9, 1), hasta=date(2026, 10, 1))
    assert "c.rfc_receptor = %s" in sql and "c.estado" not in sql
    assert params == ["emp-1", "AAA010101AAA", date(2026, 9, 1), date(2026, 10, 1), "I"]


def test_sin_tipo_para_los_conteos_por_pestana():
    c = cl.validar("emitidos", "2026-09")
    sql, params = cl.condiciones(c, "e", "R", desde=date(2026, 9, 1), hasta=date(2026, 10, 1), con_tipo=False)

    assert "c.tipo_comprobante" not in sql
    assert params == ["e", "R", date(2026, 9, 1), date(2026, 10, 1), "vigente"]


def test_el_filtro_de_pago_solo_aplica_con_ppd():
    sql, _ = _condiciones(metodo="todos", pago="pendientes")
    assert "monto_cobrado" not in sql

    sql, params = _condiciones(metodo="PPD", pago="pendientes")
    assert "COALESCE(c.monto_cobrado, 0) < c.total" in sql and "PPD" in params

    sql, _ = _condiciones(metodo="PPD", pago="pagadas")
    assert "COALESCE(c.monto_cobrado, 0) >= c.total" in sql


def test_la_busqueda_escapa_los_comodines_y_va_como_parametro():
    sql, params = _condiciones(q="50%_DESC")

    assert "50%" not in sql and "DESC" not in sql
    assert params[-4:] == ["%50\\%\\_DESC%"] * 4
    assert sql.count("ILIKE %s ESCAPE") == 4


def test_filtros_avanzados_generan_sql_parametrizado():
    filtros = json.dumps([
        {"campo": "total", "op": "mayor", "valor": "4000.50"},
        {"campo": "serie", "op": "contiene", "valor": "A%"},
        {"campo": "fecha_emision", "op": "entre", "valor": ["2026-09-01", "2026-09-15"]},
        {"campo": "categoria", "op": "en", "valor": ["venta", "anticipo"]},
        {"campo": "uuid", "op": "igual", "valor": "abc"},
    ])
    sql, params = _condiciones(filtros=filtros)

    assert "c.total > %s" in sql
    assert "c.serie ILIKE %s ESCAPE" in sql
    assert "(c.fecha_emision)::date BETWEEN %s AND %s" in sql
    assert "= ANY(%s)" in sql
    assert "UPPER(c.uuid) = UPPER(%s)" in sql
    assert params[6:] == [
        Decimal("4000.50"), "%A\\%%", date(2026, 9, 1), date(2026, 9, 15), ["venta", "anticipo"], "abc",
    ]


def test_ningun_valor_del_usuario_llega_al_texto_del_sql():
    filtros = json.dumps([{"campo": "serie", "op": "igual", "valor": "'; DROP TABLE cfdi; --"}])
    sql, params = _condiciones(q="'; DROP TABLE cfdi; --", filtros=filtros)

    assert "DROP" not in sql
    assert "'; DROP TABLE cfdi; --" in params
```

- [ ] **Step 2:** Run: `python -m pytest backend/tests/test_cfdi_listado.py -q` — Expected: FAIL (`ImportError`).

- [ ] **Step 3: Implementación**

<!-- T4:impl crear backend/cfdi_listado.py -->
```python
"""Listado de CFDI: valida la consulta contra el catálogo de columnas y arma el
SQL. Todo valor que viene del usuario viaja como parámetro; los nombres de
columna, el orden y los operadores salen únicamente del catálogo.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Optional

from . import catalogos_sat, db
from .cfdi_columnas import A_PESOS, DESCRIPCIONES, LATERALES, Columna, columnas

DIRECCIONES = ("emitidos", "recibidos")
TIPOS = ("I", "E", "T", "N", "P")
ESTADOS = ("vigente", "cancelado", "todos")
METODOS = ("PUE", "PPD", "todos")
PAGOS = ("pendientes", "pagadas", "todos")
POR_PAGINA = (30, 50, 100)
MAX_FILTROS = 10
MAX_TEXTO = 200
MAX_BUSQUEDA = 100
CENTAVOS = Decimal("0.01")

_PERIODO_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
_COMPARACION = {"igual": "=", "mayor": ">", "menor": "<"}
_NUMERICOS = ("igual", "mayor", "menor", "entre")
OPERADORES = {
    "texto": ("contiene", "igual", "empieza"),
    "numero": _NUMERICOS,
    "moneda": _NUMERICOS,
    "fecha": _NUMERICOS,
    "fecha_hora": _NUMERICOS,
    "booleano": ("igual",),
    "catalogo": ("igual", "en"),
}


class FiltroInvalido(ValueError):
    """La consulta pide algo fuera del catálogo o con un valor mal formado."""


@dataclass
class Consulta:
    direccion: str
    periodo: str
    tipo: str = "I"
    estado: str = "vigente"
    metodo: str = "todos"
    pago: str = "todos"
    q: Optional[str] = None
    filtros: list[dict] = field(default_factory=list)
    orden: str = "fecha_emision"
    dir: str = "asc"
    pagina: int = 1
    por_pagina: int = 30


def _uno_de(nombre: str, valor: Any, opciones: tuple) -> None:
    if valor not in opciones:
        raise FiltroInvalido(f"{nombre} inválido; valores permitidos: {', '.join(str(o) for o in opciones)}")


def _escapar_like(texto: str) -> str:
    return texto.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _valor(col: Columna, valor: Any) -> Any:
    """Convierte y valida un valor de filtro según el tipo de dato de la columna."""
    if isinstance(valor, (dict, list)) or valor is None:
        raise FiltroInvalido(f"Valor inválido para {col.clave}")
    if col.tipo_dato == "booleano":
        if not isinstance(valor, bool):
            raise FiltroInvalido(f"{col.clave} espera verdadero o falso")
        return valor
    if col.tipo_dato in ("numero", "moneda"):
        try:
            numero = Decimal(str(valor))
        except Exception:
            raise FiltroInvalido(f"{col.clave} espera un número")
        if not numero.is_finite():
            raise FiltroInvalido(f"{col.clave} espera un número")
        return numero
    if col.tipo_dato in ("fecha", "fecha_hora"):
        try:
            return date.fromisoformat(str(valor))
        except ValueError:
            raise FiltroInvalido(f"{col.clave} espera una fecha AAAA-MM-DD")
    texto = str(valor)
    if len(texto) > MAX_TEXTO:
        raise FiltroInvalido(f"Valor demasiado largo para {col.clave}")
    if col.tipo_dato == "catalogo" and col.opciones and texto not in col.opciones:
        raise FiltroInvalido(f"{col.clave} no admite el valor {texto!r}")
    return texto


def _validar_filtros(crudo: Any, por_clave: dict[str, Columna]) -> list[dict]:
    if crudo in (None, "", []):
        return []
    if isinstance(crudo, str):
        try:
            crudo = json.loads(crudo)
        except ValueError:
            raise FiltroInvalido("filtros debe ser JSON válido")
    if not isinstance(crudo, list):
        raise FiltroInvalido("filtros debe ser una lista")
    if len(crudo) > MAX_FILTROS:
        raise FiltroInvalido(f"Máximo {MAX_FILTROS} filtros")

    limpios = []
    for f in crudo:
        if not isinstance(f, dict) or "valor" not in f:
            raise FiltroInvalido("Cada filtro lleva campo, op y valor")
        col = por_clave.get(f.get("campo"))
        if col is None or not col.filtrable:
            raise FiltroInvalido(f"No se puede filtrar por {f.get('campo')!r}")
        op = f.get("op")
        if op not in OPERADORES.get(col.tipo_dato, ()):
            raise FiltroInvalido(f"Operador {op!r} no aplica a {col.clave}")
        valor = f["valor"]
        if op in ("entre", "en"):
            if not isinstance(valor, list) or not valor or (op == "entre" and len(valor) != 2) or len(valor) > 50:
                raise FiltroInvalido(f"{op} espera una lista de valores para {col.clave}")
            valor = [_valor(col, v) for v in valor]
        else:
            valor = _valor(col, valor)
        limpios.append({"campo": col.clave, "op": op, "valor": valor})
    return limpios


def validar(
    direccion: str,
    periodo: str,
    tipo: str = "I",
    estado: str = "vigente",
    metodo: str = "todos",
    pago: str = "todos",
    q: Optional[str] = None,
    filtros: Any = None,
    orden: str = "fecha_emision",
    dir: str = "asc",
    pagina: int = 1,
    por_pagina: int = 30,
) -> Consulta:
    """Valida todos los parámetros contra el catálogo. Lanza ``FiltroInvalido``."""
    _uno_de("direccion", direccion, DIRECCIONES)
    if not isinstance(periodo, str) or not _PERIODO_RE.match(periodo):
        raise FiltroInvalido("periodo inválido; formato esperado YYYY-MM")
    _uno_de("tipo", tipo, TIPOS)
    _uno_de("estado", estado, ESTADOS)
    _uno_de("metodo", metodo, METODOS)
    _uno_de("pago", pago, PAGOS)
    _uno_de("dir", dir, ("asc", "desc"))
    _uno_de("por_pagina", por_pagina, POR_PAGINA)
    if not isinstance(pagina, int) or pagina < 1:
        raise FiltroInvalido("pagina debe ser un entero mayor o igual a 1")
    q = (q or "").strip() or None
    if q and len(q) > MAX_BUSQUEDA:
        raise FiltroInvalido(f"La búsqueda admite hasta {MAX_BUSQUEDA} caracteres")

    por_clave = {c.clave: c for c in columnas(direccion, tipo)}
    col_orden = por_clave.get(orden)
    if col_orden is None or not col_orden.ordenable:
        raise FiltroInvalido(f"No se puede ordenar por {orden!r}")

    return Consulta(
        direccion=direccion, periodo=periodo, tipo=tipo, estado=estado, metodo=metodo, pago=pago,
        q=q, filtros=_validar_filtros(filtros, por_clave), orden=orden, dir=dir,
        pagina=pagina, por_pagina=por_pagina,
    )


def rango(periodo: str) -> tuple[date, date]:
    """Primer día del mes y primer día del mes siguiente."""
    anio, mes = int(periodo[:4]), int(periodo[5:7])
    return date(anio, mes, 1), (date(anio + 1, 1, 1) if mes == 12 else date(anio, mes + 1, 1))


def _filtro_sql(col: Columna, op: str, valor: Any) -> tuple[str, list]:
    expr = col.sql
    if col.tipo_dato == "texto":
        if op == "igual":
            return f"UPPER({expr}) = UPPER(%s)", [valor]
        patron = _escapar_like(valor) + "%"
        return f"{expr} ILIKE %s ESCAPE '\\'", [("%" if op == "contiene" else "") + patron]
    if col.tipo_dato in ("fecha", "fecha_hora"):
        expr = f"({expr})::date"
    if op == "entre":
        return f"{expr} BETWEEN %s AND %s", list(valor)
    if op == "en":
        return f"{expr} = ANY(%s)", [list(valor)]
    return f"{expr} {_COMPARACION[op]} %s", [valor]


def condiciones(
    c: Consulta, empresa_id: str, rfc: str, *, desde: date, hasta: date, con_tipo: bool = True
) -> tuple[str, list]:
    """Fragmento WHERE (sin la palabra) y sus parámetros, en el mismo orden."""
    por_clave = {col.clave: col for col in columnas(c.direccion, c.tipo)}
    col_rfc = "c.rfc_emisor" if c.direccion == "emitidos" else "c.rfc_receptor"
    sql = ["c.empresa_id = %s", f"{col_rfc} = %s", "c.fecha_emision >= %s", "c.fecha_emision < %s"]
    params: list = [empresa_id, rfc, desde, hasta]

    if con_tipo:
        sql.append("c.tipo_comprobante = %s")
        params.append(c.tipo)
    if c.estado != "todos":
        sql.append("c.estado = %s")
        params.append(c.estado)
    if c.metodo != "todos":
        sql.append("c.metodo_pago = %s")
        params.append(c.metodo)
        if c.metodo == "PPD" and c.pago != "todos":
            comparador = "<" if c.pago == "pendientes" else ">="
            sql.append(f"COALESCE(c.monto_cobrado, 0) {comparador} c.total")
    if c.q:
        patron = f"%{_escapar_like(c.q)}%"
        campos = ["c.uuid", por_clave["rfc_contraparte"].sql, por_clave["contraparte"].sql,
                  "(COALESCE(c.serie, '') || COALESCE(c.folio, ''))"]
        sql.append("(" + " OR ".join(f"{campo} ILIKE %s ESCAPE '\\'" for campo in campos) + ")")
        params += [patron] * len(campos)
    for f in c.filtros:
        fragmento, valores = _filtro_sql(por_clave[f["campo"]], f["op"], f["valor"])
        sql.append(fragmento)
        params += valores

    return " AND ".join(sql), params
```

- [ ] **Step 4:** Run: `python -m pytest backend/tests/test_cfdi_listado.py -q` — Expected: PASS (37 passed).

- [ ] **Step 5:** Commit: `feat: validar la consulta del listado de CFDI contra el catálogo de columnas`.

---

### Task 5: Listado y resumen contra la base

**Files:**
- Modify: `backend/cfdi_listado.py` (anexar)
- Test: `backend/tests/test_e2e_listado_cfdi.py`

**Interfaces:**
- Consumes: `Consulta`, `validar`, `rango`, `condiciones` (Task 4); `columnas`, `LATERALES`, `A_PESOS`, `DESCRIPCIONES` (Task 3); `catalogos_sat.descripcion` (Task 2).
- Produces:
  - `listar(empresa_id: str, rfc: str, c: Consulta) -> dict` → `{"items": [dict], "total": int, "pagina": int, "por_pagina": int}`.
  - `resumen(empresa_id: str, rfc: str, c: Consulta) -> dict` → `{"conteos": {"I","E","T","N","P"}, "totales": {"periodo": {...}, "acumulado": {...}}, "advertencias": [...]}`. Cada bloque de totales tiene `conteo`, `retencion_iva`, `retencion_ieps`, `retencion_isr`, `traslado_iva`, `traslado_ieps`, `traslado_isr`, `total_retenciones`, `subtotal`, `descuento`, `neto`, `total`; con `conteo == 0` las demás van en `None`.

Datos de la prueba (empresa `LST010101E2E`, periodo 2026-03), todos emitidos salvo que se indique:

| Grupo | CFDI | Subtotal / IVA / Total |
|---|---|---|
| 35 ingresos PUE vigentes MXN, folio 1 a 35 | fecha 2026-03-(1 + i mod 28) | 100·i / 16·i / 116·i → suman 63,000 / 10,080 / 73,080 |
| Ingreso PUE vigente en USD, folio 900, receptor "CLIENTE 50%_DOLARES" | tipo de cambio 20, IEPS trasladado 5.00 | 10 / 1.60 / 11.60 → en pesos 200 / 32 / 232, IEPS 100 |
| Ingreso PUE cancelado, folio 901 | | 1,000 / 160 / 1,160 |
| Ingreso PPD vigente pagado, folio 902 | cobrado 1,160; lo liquida el REP | 1,000 / 160 / 1,160 |
| Ingreso PPD vigente pendiente, folio 903 | cobrado 500 | 2,000 / 320 / 2,320 |
| Egreso, Pago (REP) y Nómina vigentes | | |
| 2 ingresos recibidos | | |
| Ingreso PUE vigente de febrero, folio 950 | | 500 / 80 / 580 |

Totales esperados de Ingreso vigente: periodo 38 CFDI, subtotal 66,200, IVA 10,592, total 76,792, IEPS 100; acumulado 39 CFDI, subtotal 66,700, IVA 10,672, total 77,372.

- [ ] **Step 1: Prueba que falla**

<!-- T5:test crear backend/tests/test_e2e_listado_cfdi.py -->
```python
"""E2E del listado de CFDI contra Postgres real: filtros, orden, paginación,
conteos por tipo y totales del periodo y del acumulado. Se salta sin DB."""
import json
from datetime import date

import pytest

from backend.tests.conftest import db_disponible, headers_usuario_e2e

RFC = "LST010101E2E"
OTRO = "XAXX010101000"
EMAIL = "e2e-listado-cfdi@test.local"
EMAIL_AJENO = "e2e-listado-ajeno@test.local"

pytestmark = [pytest.mark.db, pytest.mark.skipif(not db_disponible(), reason="Postgres no disponible (docker compose up -d db)")]


def _uuid(n: int) -> str:
    return f"1F3A{n:04d}-0000-4000-8000-000000000000"


def _cfdi(db, empresa_id, n, **kw):
    v = dict(
        uuid=_uuid(n), tipo_comprobante="I", serie="A", folio=str(n),
        rfc_emisor=RFC, nombre_emisor="Emisora E2E", rfc_receptor=OTRO, nombre_receptor="CLIENTE",
        fecha_emision="2026-03-10", subtotal="100", descuento="0", iva_trasladado="16",
        iva_retenido="0", isr_retenido="0", total="116", estado="vigente", metodo_pago="PUE",
        forma_pago="03", uso_cfdi="G03", moneda="MXN", tipo_cambio="1", monto_cobrado="0",
        cfdi_relacionados="[]",
    )
    v.update(kw)
    fila = db.execute(
        f"INSERT INTO cfdi (empresa_id, {', '.join(v)}) VALUES (%s, {', '.join(['%s'] * len(v))}) RETURNING id",
        (empresa_id, *v.values()), returning=True,
    )
    return str(fila["id"])


def _limpiar(db):
    db.execute("DELETE FROM empresas WHERE rfc = %s", (RFC,))
    db.execute("DELETE FROM cfdi WHERE uuid LIKE '1F3A%%'")
    db.execute("DELETE FROM usuarios WHERE email IN (%s, %s)", (EMAIL, EMAIL_AJENO))


def _sembrar(db, empresa_id):
    for i in range(1, 36):
        _cfdi(db, empresa_id, i, fecha_emision=date(2026, 3, 1 + i % 28).isoformat(),
              subtotal=str(100 * i), iva_trasladado=str(16 * i), total=str(116 * i))
    dolares = _cfdi(db, empresa_id, 900, nombre_receptor="CLIENTE 50%_DOLARES", subtotal="10",
                    iva_trasladado="1.60", total="11.60", moneda="USD", tipo_cambio="20", forma_pago="99")
    db.execute(
        "INSERT INTO cfdi_impuestos (cfdi_id, ambito, impuesto, tipo_factor, tasa_o_cuota, base, importe)"
        " VALUES (%s, 'traslado', '003', 'Tasa', 0.08, 10, 5.00)", (dolares,))
    _cfdi(db, empresa_id, 901, estado="cancelado", subtotal="1000", iva_trasladado="160", total="1160")
    _cfdi(db, empresa_id, 902, metodo_pago="PPD", forma_pago="99", subtotal="1000", iva_trasladado="160",
          total="1160", monto_cobrado="1160")
    _cfdi(db, empresa_id, 903, metodo_pago="PPD", forma_pago="99", subtotal="2000", iva_trasladado="320",
          total="2320", monto_cobrado="500")
    _cfdi(db, empresa_id, 910, tipo_comprobante="E", subtotal="50", iva_trasladado="8", total="58")
    rep = _cfdi(db, empresa_id, 911, tipo_comprobante="P", subtotal="0", iva_trasladado="0", total="0",
                metodo_pago=None, forma_pago=None, uso_cfdi="CP01", moneda="XXX")
    _cfdi(db, empresa_id, 912, tipo_comprobante="N", subtotal="5000", iva_trasladado="0", total="4500",
          uso_cfdi="CN01")
    _cfdi(db, empresa_id, 920, rfc_emisor="PROV010101AAA", nombre_emisor="PROVEEDOR UNO", rfc_receptor=RFC,
          nombre_receptor="Emisora E2E", subtotal="300", iva_trasladado="48", total="348")
    _cfdi(db, empresa_id, 921, rfc_emisor="PROV010101AAA", nombre_emisor="PROVEEDOR UNO", rfc_receptor=RFC,
          nombre_receptor="Emisora E2E", subtotal="700", iva_trasladado="112", total="812")
    _cfdi(db, empresa_id, 950, fecha_emision="2026-02-15", subtotal="500", iva_trasladado="80", total="580")
    pago = db.execute(
        "INSERT INTO pagos_cfdi (empresa_id, cfdi_id, uuid_cfdi_pago, fecha_pago, monto)"
        " VALUES (%s, %s, %s, '2026-03-20', 1160) RETURNING id", (empresa_id, rep, _uuid(911)), returning=True)
    db.execute(
        "INSERT INTO pagos_relaciones (pago_id, cfdi_uuid, parcialidad, importe_pagado, saldo_anterior, saldo_restante)"
        " VALUES (%s, %s, 1, 1160, 1160, 0)", (str(pago["id"]), _uuid(902)))


@pytest.fixture(scope="module")
def entorno():
    from fastapi.testclient import TestClient

    import backend.main_api as main
    from backend import db

    db.init_db()
    _limpiar(db)
    client = TestClient(main.app)
    try:
        headers = headers_usuario_e2e(db, EMAIL)
        r = client.post("/api/v1/mis-empresas", headers=headers, json={"rfc": RFC, "razon_social": "Emisora E2E"})
        assert r.status_code == 201, r.text
        empresa_id = r.json()["empresa_id"]
        _sembrar(db, empresa_id)
        yield db, client, headers, empresa_id
    finally:
        _limpiar(db)


def _get(entorno, ruta="", **params):
    _db, client, headers, empresa_id = entorno
    base = {"direccion": "emitidos", "periodo": "2026-03"}
    base.update(params)
    r = client.get(f"/api/v1/empresas/{empresa_id}/cfdis{ruta}", headers=headers, params=base)
    assert r.status_code == 200, r.text
    return r.json()


def test_listado_pagina_en_el_servidor(entorno):
    primera = _get(entorno)
    segunda = _get(entorno, pagina=2)

    assert (primera["total"], primera["pagina"], primera["por_pagina"]) == (38, 1, 30)
    assert (len(primera["items"]), len(segunda["items"])) == (30, 8)
    assert not {i["uuid"] for i in primera["items"]} & {i["uuid"] for i in segunda["items"]}
    fechas = [i["fecha_emision"] for i in primera["items"] + segunda["items"]]
    assert fechas == sorted(fechas)


def test_orden_por_columna(entorno):
    datos = _get(entorno, orden="total", dir="desc")

    assert [i["total"] for i in datos["items"][:3]] == [4060.0, 3944.0, 3828.0]


def test_filtro_de_estado(entorno):
    assert _get(entorno, estado="cancelado")["total"] == 1
    assert _get(entorno, estado="todos")["total"] == 39


def test_filtro_de_metodo_y_de_pago(entorno):
    assert _get(entorno, metodo="PPD")["total"] == 2
    pendientes = _get(entorno, metodo="PPD", pago="pendientes")["items"]
    pagadas = _get(entorno, metodo="PPD", pago="pagadas")["items"]

    assert [(i["folio"], i["saldo"]) for i in pendientes] == [("903", 1820.0)]
    assert [(i["folio"], i["saldo"], i["pagos_relacionados"]) for i in pagadas] == [("902", 0.0, [_uuid(911)])]


def test_busqueda_trata_los_comodines_como_texto(entorno):
    assert [i["folio"] for i in _get(entorno, q="50%_DOL")["items"]] == ["900"]
    assert _get(entorno, q="%")["total"] == 1          # solo el que trae el signo, no todos
    assert _get(entorno, q=_uuid(7).lower())["total"] == 1


def test_moneda_extranjera_muestra_importe_original_y_en_pesos(entorno):
    item = _get(entorno, q="DOLARES")["items"][0]

    assert (item["total"], item["total_mxn"], item["subtotal_mxn"], item["traslado_iva_mxn"]) == (11.6, 232.0, 200.0, 32.0)
    assert (item["moneda"], item["tipo_cambio"], item["traslado_ieps"]) == ("USD", 20.0, 5.0)
    assert item["forma_pago_desc"] == "99 - Por definir"
    assert item["categoria"] == "venta"


def test_filtro_avanzado(entorno):
    filtros = json.dumps([{"campo": "total", "op": "mayor", "valor": 4000}])
    assert [i["folio"] for i in _get(entorno, filtros=filtros)["items"]] == ["35"]

    filtros = json.dumps([{"campo": "fecha_emision", "op": "entre", "valor": ["2026-03-02", "2026-03-03"]}])
    assert sorted(i["folio"] for i in _get(entorno, filtros=filtros)["items"]) == ["1", "2", "29", "30"]


def test_recibidos_muestran_al_emisor_como_contraparte(entorno):
    datos = _get(entorno, direccion="recibidos")

    assert datos["total"] == 2
    assert {(i["rfc_contraparte"], i["contraparte"], i["categoria"]) for i in datos["items"]} == {
        ("PROV010101AAA", "PROVEEDOR UNO", "compra")}


def test_resumen_conteos_por_tipo_y_totales_en_pesos(entorno):
    r = _get(entorno, "/resumen")

    assert r["conteos"] == {"I": 38, "E": 1, "T": 0, "N": 1, "P": 1}
    assert r["totales"]["periodo"] == {
        "conteo": 38, "retencion_iva": 0.0, "retencion_ieps": 0.0, "retencion_isr": 0.0,
        "traslado_iva": 10592.0, "traslado_ieps": 100.0, "traslado_isr": 0.0, "total_retenciones": 0.0,
        "subtotal": 66200.0, "descuento": 0.0, "neto": 66200.0, "total": 76792.0,
    }
    acumulado = r["totales"]["acumulado"]
    assert (acumulado["conteo"], acumulado["subtotal"], acumulado["traslado_iva"], acumulado["total"]) == (
        39, 66700.0, 10672.0, 77372.0)
    assert r["advertencias"] == []


def test_resumen_respeta_los_filtros(entorno):
    r = _get(entorno, "/resumen", metodo="PPD")

    assert r["conteos"] == {"I": 2, "E": 0, "T": 0, "N": 0, "P": 0}
    assert (r["totales"]["periodo"]["conteo"], r["totales"]["periodo"]["total"]) == (2, 3480.0)


def test_resumen_sin_cfdi_devuelve_nulos(entorno):
    r = _get(entorno, "/resumen", tipo="T")

    assert r["totales"]["periodo"] == {
        "conteo": 0, "retencion_iva": None, "retencion_ieps": None, "retencion_isr": None,
        "traslado_iva": None, "traslado_ieps": None, "traslado_isr": None, "total_retenciones": None,
        "subtotal": None, "descuento": None, "neto": None, "total": None,
    }
    assert r["totales"]["acumulado"]["conteo"] == 0


def test_advertencia_de_factura_con_anticipo_sin_egreso(entorno):
    db, _client, _headers, empresa_id = entorno
    relacion = json.dumps([{"tipo_relacion": "07", "uuids": [_uuid(1)]}])
    _cfdi(db, empresa_id, 960, fecha_emision="2026-04-10", cfdi_relacionados=relacion)

    r = _get(entorno, "/resumen", periodo="2026-04")
    assert [(a["tipo"], a["uuid_factura"]) for a in r["advertencias"]] == [("sin_egreso_anticipo", _uuid(960))]
    assert _get(entorno, periodo="2026-04")["items"][0]["categoria"] == "factura_con_anticipo"

    egreso = json.dumps([{"tipo_relacion": "07", "uuids": [_uuid(960)]}])
    _cfdi(db, empresa_id, 961, fecha_emision="2026-04-11", tipo_comprobante="E", forma_pago="30",
          cfdi_relacionados=egreso)
    assert _get(entorno, "/resumen", periodo="2026-04")["advertencias"] == []


def test_columnas_publica_el_catalogo_sin_sql(entorno):
    r = _get(entorno, "/columnas")

    assert r["encabezado"][0]["clave"] == "fecha_emision"
    assert all("sql" not in c for c in r["encabezado"] + r["concepto"])
    assert {c["grupo"] for c in r["concepto"]} == {"concepto"}


@pytest.mark.parametrize("ruta", ["", "/resumen", "/columnas"])
def test_usuario_sin_acceso_a_la_empresa_recibe_403(entorno, ruta):
    db, client, _headers, empresa_id = entorno
    db.execute("DELETE FROM usuarios WHERE email = %s", (EMAIL_AJENO,))
    ajeno = headers_usuario_e2e(db, EMAIL_AJENO)

    r = client.get(f"/api/v1/empresas/{empresa_id}/cfdis{ruta}", headers=ajeno,
                   params={"direccion": "emitidos", "periodo": "2026-03", "tipo": "I"})
    assert r.status_code == 403
```

- [ ] **Step 2:** Run: `python -m pytest backend/tests/test_e2e_listado_cfdi.py -q` — Expected: FAIL (404: los endpoints no existen). Las pruebas de esta tarea pasan hasta terminar la Task 6; aquí se implementa la lógica y se verifica al final de la Task 6.

- [ ] **Step 3: Implementación**

<!-- T5:impl anexar backend/cfdi_listado.py -->
```python
# ---------------------------------------------------------------------------
# Consultas
# ---------------------------------------------------------------------------

# Importes del encabezado que se suman en los totales (clave → expresión).
_SUMAS = {
    "retencion_iva": "COALESCE(c.iva_retenido, 0)",
    "retencion_isr": "COALESCE(c.isr_retenido, 0)",
    "traslado_iva": "COALESCE(c.iva_trasladado, 0)",
    "subtotal": "c.subtotal",
    "descuento": "COALESCE(c.descuento, 0)",
    "total": "c.total",
}
# Impuestos que solo viven en cfdi_impuestos (clave → (ámbito, impuesto)).
_SUMAS_IMPUESTOS = {
    "traslado_ieps": ("traslado", "003"),
    "retencion_ieps": ("retencion", "003"),
    "traslado_isr": ("traslado", "001"),
}
_ORDEN_TOTALES = (
    "conteo", "retencion_iva", "retencion_ieps", "retencion_isr", "traslado_iva", "traslado_ieps",
    "traslado_isr", "total_retenciones", "subtotal", "descuento", "neto", "total",
)


def _json(valor: Any) -> Any:
    if isinstance(valor, Decimal):
        return float(valor)
    if isinstance(valor, (datetime, date)):
        return valor.isoformat()
    return valor


def _item(fila: dict) -> dict:
    item = {clave: _json(valor) for clave, valor in fila.items()}
    for derivada, (origen, catalogo) in DESCRIPCIONES.items():
        item[derivada] = catalogos_sat.descripcion(catalogo, fila.get(origen))
    return item


def listar(empresa_id: str, rfc: str, c: Consulta) -> dict:
    """Una página del listado. Primero se recorta la página (orden + límite) y
    solo sobre esas filas se calculan las columnas que dependen de subconsultas."""
    cols = columnas(c.direccion, c.tipo)
    desde, hasta = rango(c.periodo)
    where, params = condiciones(c, empresa_id, rfc, desde=desde, hasta=hasta)

    total = db.query_one(f"SELECT COUNT(*) AS n FROM cfdi c WHERE {where}", tuple(params))["n"]
    orden = next(col.sql for col in cols if col.clave == c.orden)
    direccion = "DESC" if c.dir == "desc" else "ASC"
    seleccion = ", ".join(f'{col.sql} AS "{col.clave}"' for col in cols if col.sql)

    filas = db.query_all(
        f"""
        WITH pagina AS (
            SELECT c.id, ROW_NUMBER() OVER (ORDER BY {orden} {direccion} NULLS LAST, c.id) AS n
            FROM cfdi c
            WHERE {where}
            ORDER BY n
            LIMIT %s OFFSET %s
        )
        SELECT {seleccion}
        FROM pagina p
        JOIN cfdi c ON c.id = p.id
        {LATERALES}
        ORDER BY p.n
        """,
        (*params, c.por_pagina, (c.pagina - 1) * c.por_pagina),
    )
    return {
        "items": [_item(f) for f in filas],
        "total": int(total),
        "pagina": c.pagina,
        "por_pagina": c.por_pagina,
    }


def _bloque(prefijo: str, encabezado: dict, impuestos: dict) -> dict:
    conteo = int(encabezado[f"{prefijo}_conteo"] or 0)
    if conteo == 0:
        return {clave: (0 if clave == "conteo" else None) for clave in _ORDEN_TOTALES}

    def pesos(fila: dict, clave: str) -> Decimal:
        return Decimal(str(fila.get(f"{prefijo}_{clave}") or 0))

    t = {clave: pesos(encabezado, clave) for clave in _SUMAS}
    t.update({clave: pesos(impuestos, clave) for clave in _SUMAS_IMPUESTOS})
    t["neto"] = t["subtotal"] - t["descuento"]
    t["total_retenciones"] = t["retencion_iva"] + t["retencion_isr"] + t["retencion_ieps"]
    bloque = {clave: float(t[clave].quantize(CENTAVOS, rounding=ROUND_HALF_UP)) for clave in _ORDEN_TOTALES[1:]}
    return {"conteo": conteo, **{clave: bloque[clave] for clave in _ORDEN_TOTALES[1:]}}


def _advertencias(empresa_id: str, rfc: str, desde: date, hasta: date) -> list[dict]:
    """Facturas que aplican un anticipo (TipoRelacion 07) sin su CFDI de egreso
    con forma de pago 30 en el periodo."""
    filas = db.query_all(
        """
        SELECT f.uuid
        FROM cfdi f
        WHERE f.empresa_id = %s AND f.rfc_emisor = %s AND f.tipo_comprobante = 'I'
          AND f.fecha_emision >= %s AND f.fecha_emision < %s
          AND COALESCE(f.cfdi_relacionados, '[]'::jsonb) @> '[{"tipo_relacion": "07"}]'::jsonb
          AND NOT EXISTS (
              SELECT 1
              FROM cfdi e, jsonb_array_elements(COALESCE(e.cfdi_relacionados, '[]'::jsonb)) r
              WHERE e.empresa_id = f.empresa_id AND e.rfc_emisor = f.rfc_emisor
                AND e.tipo_comprobante = 'E' AND e.forma_pago = '30'
                AND e.fecha_emision >= %s AND e.fecha_emision < %s
                AND r->'uuids' @> to_jsonb(UPPER(f.uuid))
          )
        ORDER BY f.fecha_emision
        """,
        (empresa_id, rfc, desde, hasta, desde, hasta),
    )
    return [
        {
            "tipo": "sin_egreso_anticipo",
            "uuid_factura": f["uuid"],
            "mensaje": f"La factura {f['uuid'][:8]}... aplica anticipo (TipoRel=07) pero no se encontró "
                       "CFDI Egreso con FormaPago=30 en el periodo",
        }
        for f in filas
    ]


def resumen(empresa_id: str, rfc: str, c: Consulta) -> dict:
    """Conteos por tipo (para las pestañas) y totales en pesos del tipo activo:
    del periodo y del acumulado del ejercicio (enero al mes del periodo)."""
    desde, hasta = rango(c.periodo)
    enero = date(desde.year, 1, 1)

    where, params = condiciones(c, empresa_id, rfc, desde=desde, hasta=hasta, con_tipo=False)
    conteos = {t: 0 for t in TIPOS}
    for fila in db.query_all(
        f"SELECT c.tipo_comprobante AS tipo, COUNT(*) AS n FROM cfdi c WHERE {where} GROUP BY c.tipo_comprobante",
        tuple(params),
    ):
        if fila["tipo"] in conteos:
            conteos[fila["tipo"]] = int(fila["n"])

    where, params = condiciones(c, empresa_id, rfc, desde=enero, hasta=hasta)
    base = f"""
        WITH base AS (
            SELECT c.id, (c.fecha_emision >= %s) AS en_periodo, {A_PESOS} AS tc,
                   {", ".join(f"{expr} AS {clave}" for clave, expr in _SUMAS.items())}
            FROM cfdi c
            WHERE {where}
        )
    """
    sumas = ", ".join(
        f"SUM({clave} * tc) FILTER (WHERE en_periodo) AS p_{clave}, SUM({clave} * tc) AS a_{clave}"
        for clave in _SUMAS
    )
    encabezado = db.query_one(
        f"{base} SELECT COUNT(*) FILTER (WHERE en_periodo) AS p_conteo, COUNT(*) AS a_conteo, {sumas} FROM base",
        (desde, *params),
    )
    sumas = ", ".join(
        f"SUM(i.importe * b.tc) FILTER (WHERE b.en_periodo AND i.ambito = '{ambito}' AND i.impuesto = '{impuesto}')"
        f" AS p_{clave}, "
        f"SUM(i.importe * b.tc) FILTER (WHERE i.ambito = '{ambito}' AND i.impuesto = '{impuesto}') AS a_{clave}"
        for clave, (ambito, impuesto) in _SUMAS_IMPUESTOS.items()
    )
    impuestos = db.query_one(
        f"{base} SELECT {sumas} FROM base b JOIN cfdi_impuestos i ON i.cfdi_id = b.id AND i.impuesto <> '002'",
        (desde, *params),
    )

    return {
        "conteos": conteos,
        "totales": {
            "periodo": _bloque("p", encabezado, impuestos),
            "acumulado": _bloque("a", encabezado, impuestos),
        },
        "advertencias": _advertencias(empresa_id, rfc, desde, hasta) if c.direccion == "emitidos" else [],
    }
```

- [ ] **Step 4:** Run: `python -m pytest backend/tests/test_cfdi_listado.py -q` — Expected: PASS (el módulo sigue importando; las E2E se verifican en la Task 6).

- [ ] **Step 5:** Commit (junto con la Task 6, que es la que deja estas pruebas en verde).

---

### Task 6: Router y documentación

**Files:**
- Create: `backend/routers/cfdis.py`
- Modify: `backend/main_api.py`, `docs/openapi.yaml`
- Test: `backend/tests/test_router_cfdis.py`, `backend/tests/test_e2e_listado_cfdi.py` (Task 5)

**Interfaces:**
- Consumes: `cfdi_listado.validar`, `listar`, `resumen`, `FiltroInvalido`; `cfdi_columnas.columnas`, `columnas_concepto`; `deps.get_current_user`, `validar_acceso_empresa`, `empresa_or_404`.
- Produces: `GET /api/v1/empresas/{empresa_id}/cfdis`, `/cfdis/resumen`, `/cfdis/columnas`.

- [ ] **Step 1: Prueba que falla**

<!-- T6:test crear backend/tests/test_router_cfdis.py -->
```python
"""Router del listado de CFDI (DB mockeada): validación, permisos y delegación."""
import pytest
from fastapi.testclient import TestClient

import backend.main_api as main
from backend import cfdi_listado, db
from backend.deps import get_current_user
from backend.routers import cfdis

client = TestClient(main.app)
BASE = "/api/v1/empresas/emp-1/cfdis"
OK = {"direccion": "emitidos", "periodo": "2026-09"}


@pytest.fixture
def con_acceso(monkeypatch):
    main.app.dependency_overrides[get_current_user] = lambda: {"user_id": "u1"}
    monkeypatch.setattr(cfdis, "validar_acceso_empresa", lambda *a, **k: None)
    monkeypatch.setattr(cfdis, "empresa_or_404", lambda eid: {"id": eid, "rfc": "AAA010101AAA"})
    yield
    main.app.dependency_overrides.clear()


def test_listado_delega_con_la_consulta_validada(con_acceso, monkeypatch):
    recibido = {}

    def _listar(empresa_id, rfc, consulta):
        recibido.update(empresa_id=empresa_id, rfc=rfc, consulta=consulta)
        return {"items": [], "total": 0, "pagina": 2, "por_pagina": 50}

    monkeypatch.setattr(cfdi_listado, "listar", _listar)
    r = client.get(BASE, params={**OK, "tipo": "E", "estado": "todos", "metodo": "PPD", "pago": "pendientes",
                                 "q": " acme ", "orden": "total", "dir": "desc", "pagina": 2, "por_pagina": 50})

    assert r.status_code == 200
    assert r.json() == {"items": [], "total": 0, "pagina": 2, "por_pagina": 50}
    c = recibido["consulta"]
    assert (recibido["empresa_id"], recibido["rfc"]) == ("emp-1", "AAA010101AAA")
    assert (c.tipo, c.estado, c.metodo, c.pago, c.q, c.orden, c.dir, c.pagina, c.por_pagina) == (
        "E", "todos", "PPD", "pendientes", "acme", "total", "desc", 2, 50)


def test_resumen_delega(con_acceso, monkeypatch):
    monkeypatch.setattr(cfdi_listado, "resumen", lambda e, r, c: {"conteos": {}, "totales": {}, "advertencias": []})

    r = client.get(f"{BASE}/resumen", params=OK)

    assert r.status_code == 200
    assert r.json() == {"conteos": {}, "totales": {}, "advertencias": []}


@pytest.mark.parametrize("params", [
    {"direccion": "ambos"},
    {"periodo": "2026-13"},
    {"tipo": "X"},
    {"por_pagina": 31},
    {"pagina": 0},
    {"orden": "fecha_emision; DROP TABLE cfdi"},
    {"dir": "asc; DROP TABLE cfdi"},
    {"filtros": "no es json"},
    {"filtros": '[{"campo": "total", "op": "mayor; DROP TABLE cfdi", "valor": 1}]'},
    {"filtros": '[{"campo": "total) OR (1=1", "op": "igual", "valor": 1}]'},
])
def test_parametros_invalidos_responden_422_sin_tocar_la_base(con_acceso, monkeypatch, params):
    def _no_debe_consultar(*a, **k):
        raise AssertionError("no debe llegar a la base")

    monkeypatch.setattr(db, "query_all", _no_debe_consultar)
    monkeypatch.setattr(db, "query_one", _no_debe_consultar)

    solo_listado = {"por_pagina", "pagina", "orden", "dir"}   # el resumen no pagina ni ordena
    rutas = [""] if solo_listado & set(params) else ["", "/resumen"]
    for ruta in rutas:
        r = client.get(f"{BASE}{ruta}", params={**OK, **params})
        assert r.status_code == 422, (ruta, r.text)


def test_faltan_parametros_obligatorios(con_acceso):
    assert client.get(BASE, params={"periodo": "2026-09"}).status_code == 422
    assert client.get(BASE, params={"direccion": "emitidos"}).status_code == 422


def test_columnas_devuelve_el_catalogo(con_acceso):
    r = client.get(f"{BASE}/columnas", params={"direccion": "recibidos", "tipo": "I"})

    assert r.status_code == 200
    cuerpo = r.json()
    claves = {c["clave"]: c for c in cuerpo["encabezado"]}
    assert claves["rfc_contraparte"]["etiqueta"] == "RFC emisor"
    assert set(cuerpo["encabezado"][0]) == {
        "clave", "etiqueta", "tipo_dato", "grupo", "visible_por_defecto", "ordenable", "filtrable", "opciones"}
    assert cuerpo["concepto"][0]["clave"] == "clave_prod_serv"
    assert client.get(f"{BASE}/columnas", params={"direccion": "ambos"}).status_code == 422


@pytest.mark.parametrize("ruta", ["", "/resumen", "/columnas"])
def test_sin_sesion_responde_401(ruta):
    assert client.get(f"{BASE}{ruta}", params=OK).status_code == 401


@pytest.mark.parametrize("ruta", ["", "/resumen", "/columnas"])
def test_sin_acceso_a_la_empresa_responde_403(monkeypatch, ruta):
    main.app.dependency_overrides[get_current_user] = lambda: {"user_id": "u1"}
    monkeypatch.setattr(db, "query_one", lambda *a, **k: None)   # sin fila en usuario_empresas
    try:
        r = client.get(f"{BASE}{ruta}", params=OK)
    finally:
        main.app.dependency_overrides.clear()

    assert r.status_code == 403
```

- [ ] **Step 2:** Run: `python -m pytest backend/tests/test_router_cfdis.py -q` — Expected: FAIL (`ImportError: cannot import name 'cfdis'`).

- [ ] **Step 3: Router**

<!-- T6:impl crear backend/routers/cfdis.py -->
```python
"""Listado unificado de CFDI (emitidos y recibidos, cualquier tipo): paginado,
filtrado y ordenado en el servidor. La lógica vive en ``cfdi_listado``; aquí
solo se validan permisos y se traducen los errores de validación a 422."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from .. import cfdi_listado
from ..cfdi_columnas import columnas, columnas_concepto
from ..deps import empresa_or_404, get_current_user, validar_acceso_empresa

router = APIRouter(tags=["CFDI"])

_BASE = "/api/v1/empresas/{empresa_id}/cfdis"


def _consulta(**parametros) -> cfdi_listado.Consulta:
    try:
        return cfdi_listado.validar(**parametros)
    except cfdi_listado.FiltroInvalido as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get(_BASE + "/columnas")
async def columnas_cfdi(
    empresa_id: str,
    direccion: str = Query(..., description="emitidos | recibidos"),
    tipo: str = Query("I", description="Tipo de comprobante: I, E, T, N o P"),
    current_user: dict = Depends(get_current_user),
):
    """Catálogo de columnas del listado: qué se puede mostrar, ordenar y filtrar."""
    validar_acceso_empresa(empresa_id, current_user)
    if direccion not in cfdi_listado.DIRECCIONES or tipo not in cfdi_listado.TIPOS:
        raise HTTPException(status_code=422, detail="direccion o tipo inválido")
    return {
        "encabezado": [c.publica() for c in columnas(direccion, tipo)],
        "concepto": [c.publica() for c in columnas_concepto()],
    }


@router.get(_BASE + "/resumen")
async def resumen_cfdi(
    empresa_id: str,
    direccion: str = Query(...),
    periodo: str = Query(..., description="YYYY-MM"),
    tipo: str = Query("I"),
    estado: str = Query("vigente"),
    metodo: str = Query("todos"),
    pago: str = Query("todos"),
    q: Optional[str] = Query(None),
    filtros: Optional[str] = Query(None, description="JSON: lista de {campo, op, valor}"),
    current_user: dict = Depends(get_current_user),
):
    """Conteos por tipo de comprobante y totales (periodo y acumulado del ejercicio)."""
    validar_acceso_empresa(empresa_id, current_user)
    consulta = _consulta(direccion=direccion, periodo=periodo, tipo=tipo, estado=estado,
                         metodo=metodo, pago=pago, q=q, filtros=filtros)
    empresa = empresa_or_404(empresa_id)
    return cfdi_listado.resumen(empresa_id, empresa["rfc"], consulta)


@router.get(_BASE)
async def listar_cfdi(
    empresa_id: str,
    direccion: str = Query(...),
    periodo: str = Query(..., description="YYYY-MM"),
    tipo: str = Query("I"),
    estado: str = Query("vigente"),
    metodo: str = Query("todos"),
    pago: str = Query("todos"),
    q: Optional[str] = Query(None),
    filtros: Optional[str] = Query(None, description="JSON: lista de {campo, op, valor}"),
    orden: str = Query("fecha_emision"),
    direccion_orden: str = Query("asc", alias="dir"),
    pagina: int = Query(1),
    por_pagina: int = Query(30),
    current_user: dict = Depends(get_current_user),
):
    """Una página del listado de CFDI con todas las columnas del catálogo."""
    validar_acceso_empresa(empresa_id, current_user)
    consulta = _consulta(direccion=direccion, periodo=periodo, tipo=tipo, estado=estado,
                         metodo=metodo, pago=pago, q=q, filtros=filtros, orden=orden,
                         dir=direccion_orden, pagina=pagina, por_pagina=por_pagina)
    empresa = empresa_or_404(empresa_id)
    return cfdi_listado.listar(empresa_id, empresa["rfc"], consulta)
```

- [ ] **Step 4: Registrar el router** en `backend/main_api.py`: agregar `cfdis` al `from .routers import ...` y, después de `app.include_router(cfdi.router)`, la línea `app.include_router(cfdis.router)`.

- [ ] **Step 5: Documentar** en `docs/openapi.yaml`, después del bloque `/api/v1/empresas/{empresa_id}/cfdi/nomina:`:

<!-- T6:yaml -->
```yaml
  /api/v1/empresas/{empresa_id}/cfdis:
    get:
      operationId: listarCfdis
      tags: [CFDI]
      summary: Listado paginado de CFDI (emitidos o recibidos, por tipo)
      description: |
        Una pagina del listado con todas las columnas del catalogo. Filtra,
        ordena y pagina en el servidor. `orden`, `dir` y los campos y operadores
        de `filtros` solo aceptan valores del catalogo (`/cfdis/columnas`);
        cualquier otro responde 422.
      parameters:
        - $ref: '#/components/parameters/EmpresaId'
        - { name: direccion, in: query, required: true, schema: { type: string, enum: [emitidos, recibidos] } }
        - { name: periodo, in: query, required: true, schema: { type: string, pattern: '^\d{4}-(0[1-9]|1[0-2])$' }, description: Periodo YYYY-MM por fecha de emision }
        - { name: tipo, in: query, schema: { type: string, enum: [I, E, T, N, P], default: I } }
        - { name: estado, in: query, schema: { type: string, enum: [vigente, cancelado, todos], default: vigente } }
        - { name: metodo, in: query, schema: { type: string, enum: [PUE, PPD, todos], default: todos } }
        - { name: pago, in: query, schema: { type: string, enum: [pendientes, pagadas, todos], default: todos }, description: Solo aplica con metodo=PPD }
        - { name: q, in: query, schema: { type: string, maxLength: 100 }, description: 'Busca en UUID, RFC y nombre de la contraparte, serie y folio' }
        - { name: filtros, in: query, schema: { type: string }, description: 'JSON: lista de hasta 10 objetos {campo, op, valor}' }
        - { name: orden, in: query, schema: { type: string, default: fecha_emision }, description: Clave de una columna ordenable }
        - { name: dir, in: query, schema: { type: string, enum: [asc, desc], default: asc } }
        - { name: pagina, in: query, schema: { type: integer, minimum: 1, default: 1 } }
        - { name: por_pagina, in: query, schema: { type: integer, enum: [30, 50, 100], default: 30 } }
      responses:
        '200':
          description: Pagina del listado
          content:
            application/json:
              schema:
                type: object
                properties:
                  items: { type: array, items: { type: object, additionalProperties: true } }
                  total: { type: integer }
                  pagina: { type: integer }
                  por_pagina: { type: integer }
        '401':
          $ref: '#/components/responses/UnauthorizedError'
        '403':
          $ref: '#/components/responses/ForbiddenError'
        '422':
          description: Parametro fuera del catalogo o mal formado

  /api/v1/empresas/{empresa_id}/cfdis/resumen:
    get:
      operationId: resumenCfdis
      tags: [CFDI]
      summary: Conteos por tipo y totales del listado de CFDI
      description: |
        Con los mismos filtros del listado: numero de CFDI por tipo de
        comprobante y totales en pesos del tipo activo, del periodo y del
        acumulado del ejercicio (enero al mes del periodo). Sin CFDI las cifras
        van en null. Incluye las advertencias de anticipos sin CFDI de egreso.
      parameters:
        - $ref: '#/components/parameters/EmpresaId'
        - { name: direccion, in: query, required: true, schema: { type: string, enum: [emitidos, recibidos] } }
        - { name: periodo, in: query, required: true, schema: { type: string, pattern: '^\d{4}-(0[1-9]|1[0-2])$' } }
        - { name: tipo, in: query, schema: { type: string, enum: [I, E, T, N, P], default: I } }
        - { name: estado, in: query, schema: { type: string, enum: [vigente, cancelado, todos], default: vigente } }
        - { name: metodo, in: query, schema: { type: string, enum: [PUE, PPD, todos], default: todos } }
        - { name: pago, in: query, schema: { type: string, enum: [pendientes, pagadas, todos], default: todos } }
        - { name: q, in: query, schema: { type: string, maxLength: 100 } }
        - { name: filtros, in: query, schema: { type: string } }
      responses:
        '200':
          description: Conteos y totales
          content:
            application/json:
              schema:
                type: object
                properties:
                  conteos: { type: object, additionalProperties: { type: integer } }
                  totales:
                    type: object
                    properties:
                      periodo: { type: object, additionalProperties: true }
                      acumulado: { type: object, additionalProperties: true }
                  advertencias: { type: array, items: { type: object, additionalProperties: true } }
        '401':
          $ref: '#/components/responses/UnauthorizedError'
        '403':
          $ref: '#/components/responses/ForbiddenError'
        '422':
          description: Parametro fuera del catalogo o mal formado

  /api/v1/empresas/{empresa_id}/cfdis/columnas:
    get:
      operationId: columnasCfdis
      tags: [CFDI]
      summary: Catalogo de columnas del listado de CFDI
      description: |
        Columnas de encabezado y de concepto con su etiqueta, tipo de dato,
        visibilidad por defecto y si se pueden ordenar o filtrar.
      parameters:
        - $ref: '#/components/parameters/EmpresaId'
        - { name: direccion, in: query, required: true, schema: { type: string, enum: [emitidos, recibidos] } }
        - { name: tipo, in: query, schema: { type: string, enum: [I, E, T, N, P], default: I } }
      responses:
        '200':
          description: Catalogo de columnas
          content:
            application/json:
              schema:
                type: object
                properties:
                  encabezado: { type: array, items: { type: object, additionalProperties: true } }
                  concepto: { type: array, items: { type: object, additionalProperties: true } }
        '401':
          $ref: '#/components/responses/UnauthorizedError'
        '403':
          $ref: '#/components/responses/ForbiddenError'
        '422':
          description: direccion o tipo invalido
```

- [ ] **Step 6:** Run: `python -m pytest backend/tests/test_router_cfdis.py backend/tests/test_e2e_listado_cfdi.py backend/tests/test_openapi_sync.py -q` — Expected: PASS.

- [ ] **Step 7:** Run: `python -m pytest -q` — Expected: PASS, sin fallas. Commit: `feat: agregar la API del listado de CFDI con resumen y catálogo de columnas`.

---

### Task 7: Prueba de volumen

**Files:**
- Test: `backend/tests/test_volumen_listado_cfdi.py`

**Interfaces:**
- Consumes: los endpoints de la Task 6.

Criterio de la spec: con 100,000 CFDI en una empresa, listado y resumen responden en menos de 500 ms cada uno en el entorno local. La prueba automática usa un umbral de 1.5 s para no ser frágil en CI; el tiempo medido en local se reporta en el PR contra los 500 ms.

- [ ] **Step 1: Prueba**

<!-- T7:test crear backend/tests/test_volumen_listado_cfdi.py -->
```python
"""Volumen: el listado y el resumen de CFDI con 100,000 comprobantes en una
empresa. Requiere Postgres; imprime los tiempos medidos (pytest -s)."""
import time

import pytest

from backend.tests.conftest import db_disponible, headers_usuario_e2e

RFC = "VOL010101E2E"
EMAIL = "e2e-volumen-cfdi@test.local"
N = 100_000
UMBRAL_SEGUNDOS = 1.5   # holgura para CI; el criterio de la spec (0.5 s) se mide en local

pytestmark = [pytest.mark.db, pytest.mark.skipif(not db_disponible(), reason="Postgres no disponible (docker compose up -d db)")]


def _limpiar(db):
    db.execute("DELETE FROM empresas WHERE rfc = %s", (RFC,))
    db.execute("DELETE FROM cfdi WHERE uuid LIKE 'V0L%%'")
    db.execute("DELETE FROM usuarios WHERE email = %s", (EMAIL,))


@pytest.fixture(scope="module")
def entorno():
    from fastapi.testclient import TestClient

    import backend.main_api as main
    from backend import db

    db.init_db()
    _limpiar(db)
    client = TestClient(main.app)
    try:
        headers = headers_usuario_e2e(db, EMAIL)
        r = client.post("/api/v1/mis-empresas", headers=headers, json={"rfc": RFC, "razon_social": "Volumen E2E"})
        assert r.status_code == 201, r.text
        empresa_id = r.json()["empresa_id"]
        # 100,000 ingresos emitidos repartidos en los 12 meses de 2026; uno de cada 50 trae IEPS.
        db.execute(
            """
            INSERT INTO cfdi (empresa_id, uuid, tipo_comprobante, serie, folio, rfc_emisor, nombre_emisor,
                              rfc_receptor, nombre_receptor, fecha_emision, subtotal, iva_trasladado, total,
                              estado, metodo_pago, forma_pago, uso_cfdi, moneda, tipo_cambio)
            SELECT %s, 'V0L' || lpad(i::text, 33, '0'), 'I', 'V', i::text, %s, 'Volumen E2E',
                   'XAXX010101000', 'CLIENTE ' || (i %% 500),
                   DATE '2026-01-01' + ((i %% 365) || ' days')::interval,
                   1000 + i %% 900, (1000 + i %% 900) * 0.16, (1000 + i %% 900) * 1.16,
                   CASE WHEN i %% 40 = 0 THEN 'cancelado' ELSE 'vigente' END,
                   CASE WHEN i %% 3 = 0 THEN 'PPD' ELSE 'PUE' END, '03', 'G03', 'MXN', 1
            FROM generate_series(1, %s) i
            """,
            (empresa_id, RFC, N),
        )
        db.execute(
            """
            INSERT INTO cfdi_impuestos (cfdi_id, ambito, impuesto, tipo_factor, tasa_o_cuota, base, importe)
            SELECT c.id, 'traslado', '003', 'Tasa', 0.08, c.subtotal, c.subtotal * 0.08
            FROM cfdi c WHERE c.empresa_id = %s AND c.folio::int %% 50 = 0
            """,
            (empresa_id,),
        )
        db.execute("ANALYZE cfdi")
        db.execute("ANALYZE cfdi_impuestos")
        yield client, headers, empresa_id
    finally:
        _limpiar(db)


def _medir(client, headers, url, params):
    client.get(url, headers=headers, params=params)          # calienta caché y conexión
    inicio = time.perf_counter()
    r = client.get(url, headers=headers, params=params)
    return r, time.perf_counter() - inicio


@pytest.mark.parametrize("nombre, ruta, params", [
    ("listado de un mes", "", {"periodo": "2026-06"}),
    ("listado ordenado por total, última página", "", {"periodo": "2026-06", "orden": "total", "dir": "desc", "pagina": 200, "por_pagina": 30}),
    ("listado con búsqueda", "", {"periodo": "2026-06", "q": "CLIENTE 42"}),
    ("resumen de diciembre (acumula el año)", "/resumen", {"periodo": "2026-12"}),
])
def test_responde_rapido_con_cien_mil_cfdi(entorno, nombre, ruta, params):
    client, headers, empresa_id = entorno
    r, segundos = _medir(client, headers, f"/api/v1/empresas/{empresa_id}/cfdis{ruta}",
                         {"direccion": "emitidos", **params})

    print(f"\n{nombre}: {segundos * 1000:.0f} ms")
    assert r.status_code == 200, r.text
    assert segundos < UMBRAL_SEGUNDOS, f"{nombre} tardó {segundos:.2f} s"


def test_el_resumen_del_anio_cuadra_con_lo_sembrado(entorno):
    client, headers, empresa_id = entorno
    r = client.get(f"/api/v1/empresas/{empresa_id}/cfdis/resumen", headers=headers,
                   params={"direccion": "emitidos", "periodo": "2026-12", "estado": "todos"})

    assert r.status_code == 200, r.text
    assert r.json()["totales"]["acumulado"]["conteo"] == N
```

- [ ] **Step 2:** Run: `python -m pytest backend/tests/test_volumen_listado_cfdi.py -q -s` — Expected: PASS (5 passed) y los tiempos impresos. Si alguno supera 500 ms en local, revisar el plan de ejecución (`EXPLAIN ANALYZE`) antes de aceptar.

- [ ] **Step 3:** Run: `python -m pytest -q` — Expected: PASS. Commit: `test: agregar prueba de volumen del listado de CFDI`.

---

### Cierre

- [ ] Revisión del agente `migration-validator` sobre la 030 y revisión final de toda la rama por un revisor independiente.
- [ ] Anotar en el PR los tiempos medidos de la prueba de volumen.
- [ ] PR de `feat/f3-1-api-listado-cfdi` y marcar F3.1 en el plan maestro.
