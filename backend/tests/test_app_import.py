import os

# La app valida JWT_SECRET al importar deps.py; fijamos valores de prueba.
os.environ.setdefault("JWT_SECRET", "test-secret-para-import")
os.environ.setdefault("ALLOWED_ORIGINS", "http://localhost:8000")


def test_app_importa_y_registra_rutas():
    """Regresión: la app FastAPI debe importar y montar los 12 routers.

    Protege contra el bug de forward-ref de pydantic con endpoints envueltos por
    @limiter.limit (slowapi) bajo `from __future__ import annotations`.
    """
    import backend.main_api as m

    paths = {getattr(r, "path", "") for r in m.app.routes}
    assert "/api/v1/auth/login" in paths        # endpoint con @limiter.limit + body Pydantic
    assert any(p.startswith("/api/v1/sat") for p in paths)  # endpoints SAT con @limiter.limit
