"""Tests para la funcionalidad de cierre de períodos."""
import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from uuid import uuid4

from backend import cierre as cierre_logic, db
from backend.routers.cierre import router as cierre_router


@pytest.mark.db
class TestValidacionesBloqueantes:
    """Validaciones que impiden cerrar el período."""

    def test_validacion_al_menos_un_ingreso(self, setup_empresa_con_cfdi):
        """La validación V1 requiere al menos 1 CFDI de ingreso."""
        empresa_id, periodo = setup_empresa_con_cfdi
        validaciones = cierre_logic.validaciones_bloqueantes(empresa_id, periodo)

        v1 = next((v for v in validaciones if "ingreso" in v["nombre"].lower()), None)
        assert v1 is not None
        assert v1["pasó"] is True
        assert v1["bloquea"] is True

    def test_validacion_ingresos_mayores_a_cero(self, setup_empresa_con_cfdi):
        """La validación V2 requiere ingresos > 0."""
        empresa_id, periodo = setup_empresa_con_cfdi
        validaciones = cierre_logic.validaciones_bloqueantes(empresa_id, periodo)

        v2 = next((v for v in validaciones if "Total ingreso" in v["nombre"]), None)
        assert v2 is not None
        assert v2["pasó"] is True
        assert v2["bloquea"] is True

    def test_validacion_sin_cfdi_cancelados(self, setup_empresa_con_cfdi):
        """La validación V3 detecta CFDI cancelados después del período."""
        empresa_id, periodo = setup_empresa_con_cfdi
        validaciones = cierre_logic.validaciones_bloqueantes(empresa_id, periodo)

        v3 = next((v for v in validaciones if "CFDI cancelado" in v["nombre"]), None)
        assert v3 is not None
        assert v3["bloquea"] is True

    def test_puede_cerrar_cuando_todas_pasan(self, setup_empresa_con_cfdi):
        """puede_cerrar retorna True cuando todas las validaciones pasan."""
        empresa_id, periodo = setup_empresa_con_cfdi
        assert cierre_logic.puede_cerrar(empresa_id, periodo) is True

    def test_no_puede_cerrar_si_validacion_falla(self, setup_empresa_sin_ingresos):
        """puede_cerrar retorna False si alguna validación bloqueante falla."""
        empresa_id, periodo = setup_empresa_sin_ingresos
        assert cierre_logic.puede_cerrar(empresa_id, periodo) is False


@pytest.mark.db
class TestCierrePeriodo:
    """Operaciones de cierre y reapertura de períodos."""

    def test_cerrar_periodo_exitosamente(self, setup_empresa_con_cfdi, current_user):
        """Se puede cerrar un período cuando todas las validaciones pasan."""
        empresa_id, periodo = setup_empresa_con_cfdi
        user_id = current_user["user_id"]

        cierre_logic.cerrar_periodo(empresa_id, periodo, user_id)

        assert cierre_logic.periodo_esta_cerrado(empresa_id, periodo) is True

    def test_cerrar_periodo_falla_si_validacion_bloqueada(self, setup_empresa_sin_ingresos, current_user):
        """cerrar_periodo falla con PeriodoNoPuedeCerrar si una validación no pasa."""
        empresa_id, periodo = setup_empresa_sin_ingresos
        user_id = current_user["user_id"]

        with pytest.raises(cierre_logic.PeriodoNoPuedeCerrar):
            cierre_logic.cerrar_periodo(empresa_id, periodo, user_id)

    def test_reabrir_periodo(self, setup_empresa_con_cfdi, current_user):
        """Se puede reabrir un período cerrado."""
        empresa_id, periodo = setup_empresa_con_cfdi
        user_id = current_user["user_id"]

        cierre_logic.cerrar_periodo(empresa_id, periodo, user_id)
        assert cierre_logic.periodo_esta_cerrado(empresa_id, periodo) is True

        cierre_logic.reabrir_periodo(empresa_id, periodo, user_id)
        assert cierre_logic.periodo_esta_cerrado(empresa_id, periodo) is False

    def test_periodo_esta_cerrado_retorna_false_si_reabierto(self, setup_empresa_con_cfdi, current_user):
        """periodo_esta_cerrado retorna False si el período fue reabierto."""
        empresa_id, periodo = setup_empresa_con_cfdi
        user_id = current_user["user_id"]

        cierre_logic.cerrar_periodo(empresa_id, periodo, user_id)
        cierre_logic.reabrir_periodo(empresa_id, periodo, user_id)

        assert cierre_logic.periodo_esta_cerrado(empresa_id, periodo) is False

    def test_registra_evento_al_cerrar(self, setup_empresa_con_cfdi, current_user):
        """Se registra un evento en la auditoría al cerrar."""
        empresa_id, periodo = setup_empresa_con_cfdi
        user_id = current_user["user_id"]

        cierre_logic.cerrar_periodo(empresa_id, periodo, user_id)

        # Verificar que se registró el evento
        eventos = db.query_all(
            "SELECT * FROM auditoria WHERE usuario_id = %s AND tipo_evento = 'periodo_cerrado'",
            (user_id,)
        )
        assert len(eventos) > 0


@pytest.mark.db
class TestEndpointsCierre:
    """Tests de los endpoints REST."""

    def test_get_validaciones(self, client, setup_empresa_con_cfdi):
        """GET /validaciones retorna validaciones del período."""
        empresa_id, periodo = setup_empresa_con_cfdi
        response = client.get(f"/api/v1/empresas/{empresa_id}/periodos/{periodo}/validaciones")

        assert response.status_code == 200
        data = response.json()
        assert "validaciones" in data
        assert "puede_cerrar" in data
        assert isinstance(data["validaciones"], list)

    def test_get_estado_cierre(self, client, setup_empresa_con_cfdi):
        """GET /estado-cierre retorna estado del período."""
        empresa_id, periodo = setup_empresa_con_cfdi
        response = client.get(f"/api/v1/empresas/{empresa_id}/periodos/{periodo}/estado-cierre")

        assert response.status_code == 200
        data = response.json()
        assert "cerrado" in data

    def test_post_cerrar_exitoso(self, client, setup_empresa_con_cfdi):
        """POST /cerrar cierra el período exitosamente."""
        empresa_id, periodo = setup_empresa_con_cfdi
        response = client.post(f"/api/v1/empresas/{empresa_id}/periodos/{periodo}/cerrar")

        assert response.status_code == 200
        data = response.json()
        assert "mensaje" in data

    def test_post_cerrar_falla_si_validacion_no_pasa(self, client, setup_empresa_sin_ingresos):
        """POST /cerrar retorna 422 si una validación falla."""
        empresa_id, periodo = setup_empresa_sin_ingresos
        response = client.post(f"/api/v1/empresas/{empresa_id}/periodos/{periodo}/cerrar")

        assert response.status_code == 422

    def test_get_papel_trabajo(self, client, setup_empresa_con_cfdi):
        """GET /papel-trabajo retorna archivo XLSX."""
        empresa_id, periodo = setup_empresa_con_cfdi
        response = client.get(f"/api/v1/empresas/{empresa_id}/periodos/{periodo}/papel-trabajo")

        assert response.status_code == 200
        assert "spreadsheet" in response.headers.get("content-type", "").lower()
