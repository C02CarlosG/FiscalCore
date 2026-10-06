"""Confianza en el proxy inverso (Railway, nginx…): de dónde sale la IP real del cliente.

Sin `TRUSTED_PROXY_IPS` no se confía en ningún encabezado `X-Forwarded-*` (comportamiento
seguro: nadie puede falsear su IP para esquivar los límites de tasa). Con la variable
definida (IPs separadas por comas del proxy que está delante de la app), uvicorn toma como
cliente la primera IP de `X-Forwarded-For` que no sea de un proxy de confianza, contando
desde la derecha. `*` confía en cualquier origen y toma la IP más a la izquierda, que el
propio cliente puede falsear: solo para pruebas.
"""
import logging
import os

from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

_log = logging.getLogger(__name__)


def hosts_confiables(valor: str | None = None) -> list[str]:
    crudo = os.environ.get("TRUSTED_PROXY_IPS", "") if valor is None else valor
    return [h.strip() for h in crudo.split(",") if h.strip()]


def instalar_proxy(app) -> None:
    """Agrega ProxyHeadersMiddleware solo si hay proxies de confianza configurados."""
    hosts = hosts_confiables()
    if not hosts:
        return
    if "*" in hosts:
        _log.warning("TRUSTED_PROXY_IPS=* confía en cualquier X-Forwarded-For: la IP del cliente se puede falsear. "
                     "Usa las IPs reales del proxy.")
    app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=hosts)
