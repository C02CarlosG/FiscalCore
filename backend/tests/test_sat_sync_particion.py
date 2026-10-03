"""crear_solicitud_ventana: alta de la solicitud al SAT y partición por volumen. DB y SAT simulados."""
import re
from datetime import date

import psycopg2.errors
import pytest

from backend import db, sat_sync
from backend.sat_fiel import FIELError, SolicitudRechazada

EMPRESA = {"id": "emp-1", "rfc": "AAA010101AAA"}


class _BD:
    """Tabla sat_solicitudes en memoria, lo justo para el alta y el cierre de solicitudes."""

    def __init__(self):
        self.filas = {}
        self.reglas_unicas = []
        self.sqls = []

    def execute(self, sql, params=(), returning=False):
        self.sqls.append(" ".join(sql.split()))
        s = " ".join(sql.split())
        if s.startswith("INSERT INTO sat_solicitudes"):
            columnas = [c.strip() for c in re.search(r"\(([^)]*)\) VALUES", s).group(1).split(",")]
            fila = dict(zip(columnas, params))
            clave = (fila.get("fecha_inicio"), fila.get("fecha_fin"), fila.get("tipo"))
            activas = [f for f in self.filas.values()
                       if f["estado"] in sat_sync_activas and
                       (f.get("fecha_inicio"), f.get("fecha_fin"), f.get("tipo")) == clave]
            if activas:
                raise psycopg2.errors.UniqueViolation("duplicada")
            fila["id"] = f"sol-{len(self.filas) + 1}"
            fila["estado"] = "pendiente"
            self.filas[fila["id"]] = fila
            return dict(fila) if returning else None
        sol_id = params[-1]
        fila = self.filas[sol_id]
        if "estado='fallo'" in s:
            fila["estado"] = "fallo"
            fila["error_msg"] = params[0]
        elif "id_solicitud_sat=%s" in s and "estado='solicitado'" in s:
            fila["id_solicitud_sat"] = params[0]
            fila["estado"] = "solicitado"
        elif "intentos = intentos + 1" in s:
            fila["intentos"] = fila.get("intentos", 0) + 1
            fila["error_msg"] = params[0]
            return {"intentos": fila["intentos"], "estado": fila["estado"]} if returning else None
        return None


sat_sync_activas = ("pendiente", "solicitado", "en_proceso", "terminado")


@pytest.fixture()
def bd(monkeypatch):
    fake = _BD()
    monkeypatch.setattr(db, "execute", fake.execute)
    return fake


def _sat(monkeypatch, respuestas):
    """``respuestas``: lista de id_sat (str) o excepción, una por llamada a solicitar_descarga."""
    llamadas = []

    def _solicitar(creds, rfc, tipo, inicio, fin, **kw):
        llamadas.append({"rfc": rfc, "tipo": tipo, "inicio": inicio, "fin": fin, **kw})
        r = respuestas[len(llamadas) - 1]
        if isinstance(r, Exception):
            raise r
        return r
    monkeypatch.setattr(sat_sync, "solicitar_descarga", _solicitar)
    return llamadas


def _crear(**kw):
    kw.setdefault("origen", "inicial")
    return sat_sync.crear_solicitud_ventana(
        object(), EMPRESA, "emitidos", date(2026, 9, 1), date(2026, 9, 30), **kw)


def test_el_sat_acepta_deja_una_solicitud_solicitada_con_sus_datos(bd, monkeypatch):
    llamadas = _sat(monkeypatch, ["SAT-1"])

    filas = _crear(origen="diaria", estado_comprobante="Vigente", tipo_solicitud="CFDI")

    assert [(f["estado"], f["id_solicitud_sat"]) for f in filas] == [("solicitado", "SAT-1")]
    fila = bd.filas["sol-1"]
    assert (fila["origen"], fila["estado_comprobante"], fila["tipo_solicitud"]) == ("diaria", "Vigente", "CFDI")
    assert (fila["empresa_id"], fila["tipo"], fila["periodo_inicio"], fila["periodo_fin"]) == (
        "emp-1", "emitidos", "2026-09", "2026-09")
    assert (fila["fecha_inicio"], fila["fecha_fin"]) == (date(2026, 9, 1), date(2026, 9, 30))
    assert llamadas == [{"rfc": "AAA010101AAA", "tipo": "emitidos", "inicio": date(2026, 9, 1),
                         "fin": date(2026, 9, 30), "tipo_solicitud": "CFDI", "estado_comprobante": "Vigente"}]


def test_acepta_usuario_para_las_solicitudes_manuales(bd, monkeypatch):
    _sat(monkeypatch, ["SAT-1"])
    _crear(origen="manual", usuario_id="u1")
    assert bd.filas["sol-1"]["usuario_id"] == "u1"


def test_tope_maximo_5003_parte_el_mes_en_dos_mitades(bd, monkeypatch):
    llamadas = _sat(monkeypatch, [SolicitudRechazada("tope", codigo="5003"), "SAT-A", "SAT-B"])

    filas = _crear()

    assert bd.filas["sol-1"]["estado"] == "fallo"
    assert "5003" in bd.filas["sol-1"]["error_msg"] and "partió" in bd.filas["sol-1"]["error_msg"]
    assert [(f["fecha_inicio"], f["fecha_fin"], f["estado"]) for f in filas] == [
        (date(2026, 9, 1), date(2026, 9, 15), "solicitado"),
        (date(2026, 9, 16), date(2026, 9, 30), "solicitado"),
    ]
    assert [(c["inicio"], c["fin"]) for c in llamadas][1:] == [
        (date(2026, 9, 1), date(2026, 9, 15)), (date(2026, 9, 16), date(2026, 9, 30))]


def test_una_mitad_que_vuelve_a_rebasar_el_tope_se_parte_otra_vez(bd, monkeypatch):
    _sat(monkeypatch, [
        SolicitudRechazada("tope", codigo="5003"),   # mes
        SolicitudRechazada("tope", codigo="5003"),   # 1-15
        "SAT-1", "SAT-2",                            # 1-7, 8-15
        "SAT-3",                                     # 16-30
    ])

    filas = _crear()

    rangos = [(f["fecha_inicio"], f["fecha_fin"]) for f in filas]
    assert rangos == [(date(2026, 9, 1), date(2026, 9, 7)), (date(2026, 9, 8), date(2026, 9, 15)),
                      (date(2026, 9, 16), date(2026, 9, 30))]
    # sin huecos ni solapes
    for (_, fin), (ini, _) in zip(rangos, rangos[1:]):
        assert (ini - fin).days == 1


def test_un_dia_que_sigue_rebasando_el_tope_queda_en_fallo_sin_bucle(bd, monkeypatch):
    llamadas = _sat(monkeypatch, [SolicitudRechazada("El SAT rechazó (código 5003): Tope máximo", codigo="5003")] * 50)

    filas = sat_sync.crear_solicitud_ventana(
        object(), EMPRESA, "emitidos", date(2026, 9, 1), date(2026, 9, 1), origen="inicial",
        tolerar_transitorios=True)

    assert len(llamadas) == 1
    assert [f["estado"] for f in filas] == ["fallo"]
    assert "5003" in filas[0]["error_msg"]


@pytest.mark.parametrize("codigo", ["5002", "5005", "301"])
def test_otros_rechazos_del_sat_son_definitivos_y_no_se_parten(bd, monkeypatch, codigo):
    llamadas = _sat(monkeypatch, [SolicitudRechazada(f"rechazo {codigo}", codigo=codigo)])

    filas = _crear(tolerar_transitorios=True)

    assert len(llamadas) == 1
    assert [f["estado"] for f in filas] == ["fallo"]
    assert codigo in filas[0]["error_msg"]


def test_rechazo_definitivo_sin_tolerancia_marca_fallo_y_relanza(bd, monkeypatch):
    _sat(monkeypatch, [SolicitudRechazada("rechazo 5002", codigo="5002")])

    with pytest.raises(SolicitudRechazada):
        _crear()
    assert bd.filas["sol-1"]["estado"] == "fallo"


def test_error_transitorio_sin_tolerancia_marca_fallo_y_relanza(bd, monkeypatch):
    _sat(monkeypatch, [FIELError("sin red")])

    with pytest.raises(FIELError, match="sin red"):
        _crear()
    assert bd.filas["sol-1"]["estado"] == "fallo"
    assert "sin red" in bd.filas["sol-1"]["error_msg"]


def test_error_transitorio_con_tolerancia_queda_pendiente_para_reintentar(bd, monkeypatch):
    _sat(monkeypatch, [FIELError("sin red")])

    filas = _crear(tolerar_transitorios=True)

    assert [f["estado"] for f in filas] == ["pendiente"]
    assert bd.filas["sol-1"]["intentos"] == 1


def test_ventana_activa_repetida_levanta_solicitud_activa(bd, monkeypatch):
    _sat(monkeypatch, ["SAT-1", "SAT-2"])
    _crear()

    with pytest.raises(sat_sync.SolicitudActiva):
        _crear()
    assert len(bd.filas) == 1


def test_la_fila_original_se_cierra_antes_de_insertar_las_mitades(bd, monkeypatch):
    """Si no, las mitades chocarían con la original en el índice único de ventanas activas."""
    _sat(monkeypatch, [SolicitudRechazada("tope", codigo="5003"), "SAT-A", "SAT-B"])

    _crear()

    indice_fallo = next(i for i, q in enumerate(bd.sqls) if "estado='fallo'" in q)
    segundo_insert = [i for i, q in enumerate(bd.sqls) if q.startswith("INSERT")][1]
    assert indice_fallo < segundo_insert
