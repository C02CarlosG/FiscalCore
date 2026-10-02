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
