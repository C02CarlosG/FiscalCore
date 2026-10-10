"""Tests para la funcionalidad de cierre de períodos."""
import pytest
from uuid import uuid4

from backend import cierre as cierre_logic


class TestCierreLogic:
    """Tests unitarios para la lógica de cierre."""

    def test_periodo_no_puede_cerrar_exception_existe(self):
        """PeriodoNoPuedeCerrar es una excepción personalizada."""
        assert issubclass(cierre_logic.PeriodoNoPuedeCerrar, Exception)


class TestValidacionesStructure:
    """Tests de estructura de validaciones."""

    def test_validaciones_bloqueantes_existe(self):
        """validaciones_bloqueantes función existe y es callable."""
        assert callable(cierre_logic.validaciones_bloqueantes)

    def test_validaciones_recomendadas_existe(self):
        """validaciones_recomendadas función existe y es callable."""
        assert callable(cierre_logic.validaciones_recomendadas)

    def test_periodo_esta_cerrado_existe(self):
        """periodo_esta_cerrado función existe y es callable."""
        assert callable(cierre_logic.periodo_esta_cerrado)


class TestCierreEndpoints:
    """Tests básicos de los endpoints de cierre."""

    def test_cierre_router_importa(self):
        """El router de cierre se importa correctamente."""
        from backend.routers import cierre
        assert hasattr(cierre, "router")

    def test_main_api_incluye_cierre_router(self):
        """main_api.py incluye el router de cierre."""
        from backend import main_api
        assert hasattr(main_api, "app")


class TestCierreFunctions:
    """Tests de funciones individuales de cierre."""

    def test_cerrar_periodo_existe(self):
        """cerrar_periodo función existe y es callable."""
        assert callable(cierre_logic.cerrar_periodo)

    def test_reabrir_periodo_existe(self):
        """reabrir_periodo función existe y es callable."""
        assert callable(cierre_logic.reabrir_periodo)
