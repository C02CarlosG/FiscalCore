"""Confianza en el proxy: IP real del cliente solo cuando el proxy está declarado."""
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from backend.proxy import hosts_confiables, instalar_proxy


def _app():
    app = FastAPI()

    @app.get("/ip")
    async def ip(request: Request):
        return {"ip": request.client.host, "scheme": request.url.scheme}

    return app


def _llamar(app):
    return TestClient(app).get("/ip", headers={"X-Forwarded-For": "9.9.9.9, 203.0.113.7", "X-Forwarded-Proto": "https"}).json()


def test_hosts_confiables_separa_por_comas_y_ignora_vacios():
    assert hosts_confiables(" 10.0.0.1, ,10.0.0.2 ") == ["10.0.0.1", "10.0.0.2"]
    assert hosts_confiables("") == []


def test_sin_variable_no_se_confia_en_x_forwarded_for(monkeypatch):
    monkeypatch.delenv("TRUSTED_PROXY_IPS", raising=False)
    app = _app()
    instalar_proxy(app)
    assert _llamar(app)["ip"] == "testclient"


def test_con_proxy_declarado_toma_la_ip_a_la_derecha_del_proxy(monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXY_IPS", "testclient,203.0.113.7")
    app = _app()
    instalar_proxy(app)
    cuerpo = _llamar(app)
    assert cuerpo["ip"] == "9.9.9.9" and cuerpo["scheme"] == "https"


def test_un_cliente_que_no_es_el_proxy_no_puede_falsear_su_ip(monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXY_IPS", "10.1.1.1")
    app = _app()
    instalar_proxy(app)
    assert _llamar(app)["ip"] == "testclient"
