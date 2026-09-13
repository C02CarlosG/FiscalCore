import os
from pathlib import Path

import yaml

# La app valida JWT_SECRET al importar deps.py; fijamos valores de prueba.
os.environ.setdefault("JWT_SECRET", "test-secret-para-import")
os.environ.setdefault("ALLOWED_ORIGINS", "http://localhost:8000")

_METODOS_HTTP = {"get", "post", "put", "patch", "delete"}
_OPENAPI_PATH = Path(__file__).parent.parent.parent / "docs" / "openapi.yaml"


def _operaciones(paths: dict) -> set[tuple[str, str]]:
    ops = set()
    for path, metodos in paths.items():
        for metodo in metodos:
            if metodo in _METODOS_HTTP:
                ops.add((path, metodo))
    return ops


def test_openapi_yaml_sincronizado_con_la_app():
    """docs/openapi.yaml es mantenido a mano; este test detecta drift contra las
    rutas reales que expone backend.main_api:app (fuente de verdad) — endpoints
    agregados/eliminados en el código deben reflejarse también en el YAML."""
    import backend.main_api as m

    live_paths = m.app.openapi()["paths"]
    live_ops = _operaciones(live_paths)

    doc = yaml.safe_load(_OPENAPI_PATH.read_text(encoding="utf-8"))
    doc_ops = _operaciones(doc["paths"])

    faltan_en_yaml = live_ops - doc_ops
    sobran_en_yaml = doc_ops - live_ops

    assert not faltan_en_yaml, (
        f"Endpoints en la app pero ausentes en docs/openapi.yaml: {sorted(faltan_en_yaml)}"
    )
    assert not sobran_en_yaml, (
        f"Endpoints en docs/openapi.yaml que ya no existen en la app (stale): {sorted(sobran_en_yaml)}"
    )
