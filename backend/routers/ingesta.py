from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

import psycopg2
import psycopg2.extras
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from .. import db
from ..deps import get_current_user, empresa_or_404, validar_acceso_empresa, serializar, validar_upload
from ..schemas import IngestaResponse

_CFDI_EXTENSIONES = (".xml",)
_CFDI_CONTENT_TYPES = ("text/xml", "application/xml", "application/octet-stream")

_BANCO_EXTENSIONES = (".xlsx", ".csv")
_BANCO_CONTENT_TYPES = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # .xlsx
    "text/csv",
    "application/vnd.ms-excel",
    "text/plain",
    "application/octet-stream",
)

_log = logging.getLogger(__name__)

router = APIRouter(tags=["Ingesta"])


def _persistir_complemento_pago(empresa_id: str, resultado) -> None:
    """
    Persiste los nodos pago20:Pago de un CFDI tipo P:
    - Inserta en pagos_cfdi y pagos_relaciones.
    - Actualiza monto_cobrado y estado_pago en los CFDIs de ingreso/egreso relacionados.
    """
    cfdi_row = db.query_one("SELECT id FROM cfdi WHERE uuid = %s", (resultado.uuid,))
    if not cfdi_row:
        return
    cfdi_db_id = str(cfdi_row["id"])

    for pago in resultado.pagos:
        if not pago.fecha_pago or pago.monto <= 0:
            continue

        pago_row = db.execute(
            """
            INSERT INTO pagos_cfdi (empresa_id, cfdi_id, uuid_cfdi_pago, fecha_pago, monto, moneda, tipo_cambio)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (cfdi_id, fecha_pago, monto) DO NOTHING
            RETURNING id
            """,
            (
                empresa_id, cfdi_db_id, resultado.uuid,
                pago.fecha_pago, str(pago.monto),
                pago.moneda, str(pago.tipo_cambio),
            ),
            returning=True,
        )
        if not pago_row:
            # Ya existía (ON CONFLICT DO NOTHING) — recuperar id existente
            pago_row = db.query_one(
                "SELECT id FROM pagos_cfdi WHERE cfdi_id = %s AND fecha_pago = %s AND monto = %s",
                (cfdi_db_id, pago.fecha_pago, str(pago.monto)),
            )
        if not pago_row:
            continue
        pago_db_id = str(pago_row["id"])

        for docto in pago.doctos_relacionados:
            if not docto.uuid:
                continue
            db.execute(
                """
                INSERT INTO pagos_relaciones (pago_id, cfdi_uuid, parcialidad, importe_pagado, saldo_anterior, saldo_restante)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
                """,
                (
                    pago_db_id, docto.uuid, docto.num_parcialidad,
                    str(docto.imp_pagado), str(docto.imp_saldo_ant), str(docto.imp_saldo_insoluto),
                ),
            )
            # Actualizar monto_cobrado y estado_pago en el CFDI relacionado
            db.execute(
                """
                UPDATE cfdi
                SET
                    monto_cobrado = LEAST(total, monto_cobrado + %s),
                    estado_pago = CASE
                        WHEN LEAST(total, monto_cobrado + %s) >= total THEN 'pagado_total'
                        WHEN LEAST(total, monto_cobrado + %s) > 0     THEN 'pagado_parcial'
                        ELSE 'pendiente'
                    END
                WHERE uuid = %s AND empresa_id = %s
                """,
                (
                    str(docto.imp_pagado),
                    str(docto.imp_pagado),
                    str(docto.imp_pagado),
                    docto.uuid,
                    empresa_id,
                ),
            )


def _correr_pipeline(empresa_id: str, periodo: str, rfc_empresa: str) -> None:
    """Ejecuta el motor fiscal completo para un período y persiste los resultados."""
    from ..motor_fiscal import (
        CFDIResumen, MovResumen, PagoResumen,
        MotorConciliacion, MotorRiesgos, MotorScoring,
    )

    año, mes = periodo.split("-")
    inicio = f"{año}-{mes}-01"
    # Último día del mes
    import calendar
    ultimo = calendar.monthrange(int(año), int(mes))[1]
    fin = f"{año}-{mes}-{ultimo:02d}"

    # Cargar CFDIs del período
    cfdi_rows = db.query_all(
        """
        SELECT id, uuid, tipo_comprobante, rfc_emisor, rfc_receptor,
               fecha_emision::date AS fecha, total, metodo_pago, estado,
               monto_cobrado
        FROM cfdi
        WHERE empresa_id = %s AND fecha_emision::date BETWEEN %s AND %s
        """,
        (empresa_id, inicio, fin),
    )
    cfdis = [
        CFDIResumen(
            id=str(r["id"]),
            uuid=r["uuid"],
            tipo=r["tipo_comprobante"],
            rfc_emisor=r["rfc_emisor"],
            rfc_receptor=r["rfc_receptor"],
            fecha=r["fecha"],
            total=Decimal(str(r["total"])),
            metodo_pago=r["metodo_pago"] or "PUE",
            estado=r["estado"],
            monto_cobrado=Decimal(str(r["monto_cobrado"] or 0)),
        )
        for r in cfdi_rows
    ]

    # Cargar movimientos bancarios del período
    mov_rows = db.query_all(
        """
        SELECT id, fecha, concepto, referencia, monto, tipo, rfc_detectado, conciliado
        FROM movimientos_bancarios
        WHERE empresa_id = %s AND fecha BETWEEN %s AND %s
        """,
        (empresa_id, inicio, fin),
    )
    movimientos = [
        MovResumen(
            id=str(r["id"]),
            fecha=r["fecha"],
            concepto=r["concepto"] or "",
            monto=Decimal(str(r["monto"])),
            tipo=r["tipo"],
            rfc_detectado=r["rfc_detectado"],
            conciliado=r["conciliado"],
        )
        for r in mov_rows
    ]

    if not cfdis and not movimientos:
        return

    # Cargar pagos_cfdi del período (±2 días para cubrir desfases entre depósito y fecha de pago)
    import calendar as _cal
    from datetime import timedelta as _td
    _inicio_dt = datetime.strptime(inicio, "%Y-%m-%d") - _td(days=2)
    _fin_dt = datetime.strptime(fin, "%Y-%m-%d") + _td(days=2)

    pago_rows = db.query_all(
        """
        SELECT pc.id, pc.cfdi_id, pc.uuid_cfdi_pago,
               pc.fecha_pago::date AS fecha_pago, pc.monto,
               COALESCE(
                   json_agg(pr.cfdi_uuid) FILTER (WHERE pr.cfdi_uuid IS NOT NULL),
                   '[]'::json
               ) AS cfdis_relacionados
        FROM pagos_cfdi pc
        LEFT JOIN pagos_relaciones pr ON pr.pago_id = pc.id
        WHERE pc.empresa_id = %s
          AND pc.fecha_pago::date BETWEEN %s AND %s
        GROUP BY pc.id, pc.cfdi_id, pc.uuid_cfdi_pago, pc.fecha_pago, pc.monto
        """,
        (empresa_id, _inicio_dt.date(), _fin_dt.date()),
    )
    pagos = [
        PagoResumen(
            id=str(r["id"]),
            cfdi_pago_id=str(r["cfdi_id"]),
            uuid_cfdi_pago=r["uuid_cfdi_pago"],
            fecha_pago=r["fecha_pago"],
            monto=Decimal(str(r["monto"])),
            cfdis_relacionados=list(r["cfdis_relacionados"]) if r["cfdis_relacionados"] else [],
        )
        for r in pago_rows
    ]

    # El motor solo procesa I/E — los tipo P ya fueron resueltos vía complemento
    cfdis_motor = [c for c in cfdis if c.tipo not in ("P",)]

    # Conciliación
    motor_conc = MotorConciliacion()
    conciliaciones = motor_conc.conciliar(movimientos, cfdis_motor, rfc_empresa, pagos=pagos)

    # Guardar conciliaciones (limpiar las existentes del período primero)
    db.execute(
        "DELETE FROM conciliaciones WHERE empresa_id = %s AND periodo = %s",
        (empresa_id, periodo),
    )
    for c in conciliaciones:
        db.execute(
            """
            INSERT INTO conciliaciones (
                empresa_id, movimiento_id, cfdi_id,
                tipo_match, monto_movimiento, monto_cfdi, diferencia, porcentaje_match,
                periodo, notas, confianza
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                empresa_id,
                c.movimiento_id if c.movimiento_id else None,
                c.cfdi_id if c.cfdi_id else None,
                c.tipo_match,
                str(c.monto_movimiento),
                str(c.monto_cfdi) if c.monto_cfdi is not None else None,
                str(c.diferencia),
                str(c.porcentaje_match),
                periodo,
                c.notas,
                c.confianza if c.confianza else None,
            ),
        )

    # Riesgos (solo sobre CFDIs I/E — tipo P no genera riesgos directamente)
    motor_riesgos = MotorRiesgos()
    riesgos = motor_riesgos.detectar_todos(movimientos, cfdis_motor, conciliaciones, rfc_empresa)

    # Guardar detecciones nuevas (no limpiar las existentes resueltas)
    db.execute(
        "DELETE FROM detecciones WHERE empresa_id = %s AND periodo = %s AND estado = 'abierto'",
        (empresa_id, periodo),
    )
    for r in riesgos:
        riesgo_cat = db.query_one("SELECT id FROM riesgos WHERE codigo = %s", (r.codigo,))
        if not riesgo_cat:
            continue
        db.execute(
            """
            INSERT INTO detecciones (
                empresa_id, riesgo_id, periodo,
                cfdi_id, movimiento_id,
                monto_afectado, descripcion, evidencia
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                empresa_id, riesgo_cat["id"], periodo,
                r.cfdi_id if r.cfdi_id else None,
                r.movimiento_id if r.movimiento_id else None,
                str(r.monto_afectado),
                r.descripcion,
                psycopg2.extras.Json(r.evidencia),
            ),
        )

    # Scoring
    motor_scoring = MotorScoring()
    score = motor_scoring.calcular(movimientos, cfdis_motor, conciliaciones, riesgos)

    total_ing = sum(Decimal(str(r["total"])) for r in cfdi_rows if r["tipo_comprobante"] == "I")
    total_egr = sum(Decimal(str(r["total"])) for r in cfdi_rows if r["tipo_comprobante"] == "E")
    total_dep = sum(Decimal(str(r["monto"])) for r in mov_rows if r["tipo"] == "deposito")
    total_car = sum(Decimal(str(r["monto"])).copy_abs() for r in mov_rows if r["tipo"] == "cargo")

    db.execute(
        """
        INSERT INTO scoring_fiscal (
            empresa_id, periodo,
            score_total, clasificacion,
            total_cfdi_ingresos, total_cfdi_egresos, total_movimientos, total_conciliados,
            total_riesgos_criticos, total_riesgos_altos, total_riesgos_medios, total_riesgos_bajos,
            total_ingresos_cfdi, total_egresos_cfdi, total_depositos_banco, total_cargos_banco
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (empresa_id, periodo) DO UPDATE SET
            score_total = EXCLUDED.score_total,
            clasificacion = EXCLUDED.clasificacion,
            total_cfdi_ingresos = EXCLUDED.total_cfdi_ingresos,
            total_cfdi_egresos = EXCLUDED.total_cfdi_egresos,
            total_movimientos = EXCLUDED.total_movimientos,
            total_conciliados = EXCLUDED.total_conciliados,
            total_riesgos_criticos = EXCLUDED.total_riesgos_criticos,
            total_riesgos_altos = EXCLUDED.total_riesgos_altos,
            total_riesgos_medios = EXCLUDED.total_riesgos_medios,
            total_riesgos_bajos = EXCLUDED.total_riesgos_bajos,
            total_ingresos_cfdi = EXCLUDED.total_ingresos_cfdi,
            total_egresos_cfdi = EXCLUDED.total_egresos_cfdi,
            total_depositos_banco = EXCLUDED.total_depositos_banco,
            total_cargos_banco = EXCLUDED.total_cargos_banco,
            calculado_en = NOW()
        """,
        (
            empresa_id, periodo,
            score["score_total"], score["clasificacion"],
            score["total_cfdi_ingresos"], score["total_cfdi_egresos"],
            score["total_movimientos"], score["total_conciliados"],
            score["total_riesgos_criticos"], score["total_riesgos_altos"],
            score["total_riesgos_medios"], score["total_riesgos_bajos"],
            str(total_ing), str(total_egr),
            str(total_dep), str(total_car),
        ),
    )


@router.post("/api/v1/empresas/{empresa_id}/cfdi/upload")
async def subir_cfdi(
    empresa_id: str,
    archivos: list[UploadFile] = File(...),
    periodo: str = Form(...),
    current_user: dict = Depends(get_current_user),
):
    validar_acceso_empresa(empresa_id, current_user)
    empresa = empresa_or_404(empresa_id)
    from ..cfdi_parser import CFDIParser
    parser = CFDIParser()
    procesados = 0
    errores: list[str] = []

    for archivo in archivos:
        try:
            contenido = await archivo.read()
            validar_upload(archivo, contenido, _CFDI_EXTENSIONES, _CFDI_CONTENT_TYPES)
            resultado = parser.parse_xml(contenido)
            # Separar errores bloqueantes de advertencias (prefijo "AVISO:")
            errores_bloqueantes = [e for e in resultado.errores if not e.startswith("AVISO:")]
            avisos = [e for e in resultado.errores if e.startswith("AVISO:")]
            if errores_bloqueantes:
                errores += [f"{archivo.filename}: {e}" for e in errores_bloqueantes]
                continue
            if avisos:
                errores += [f"{archivo.filename}: {e}" for e in avisos]

            # Insertar en DB (ignorar duplicados por UUID)
            db.execute(
                """
                INSERT INTO cfdi (
                    empresa_id, uuid, tipo_comprobante, serie, folio, version,
                    rfc_emisor, nombre_emisor, rfc_receptor, nombre_receptor,
                    fecha_emision, fecha_timbrado,
                    subtotal, descuento, iva_trasladado, iva_retenido, isr_retenido, total,
                    metodo_pago, forma_pago, uso_cfdi, moneda, tipo_cambio, xml_raw,
                    exportacion, lugar_expedicion,
                    domicilio_fiscal_receptor, regimen_fiscal_receptor,
                    cfdi_relacionados, es_anticipo_sat
                ) VALUES (
                    %s,%s,%s,%s,%s,%s,
                    %s,%s,%s,%s,
                    %s,%s,
                    %s,%s,%s,%s,%s,%s,
                    %s,%s,%s,%s,%s,%s,
                    %s,%s,%s,%s,
                    %s,%s
                )
                ON CONFLICT (uuid) DO NOTHING
                """,
                (
                    empresa_id, resultado.uuid, resultado.tipo_comprobante,
                    resultado.serie, resultado.folio, resultado.version,
                    resultado.rfc_emisor, resultado.nombre_emisor,
                    resultado.rfc_receptor, resultado.nombre_receptor,
                    resultado.fecha_emision, resultado.fecha_timbrado,
                    str(resultado.subtotal), str(resultado.descuento),
                    str(resultado.iva_trasladado), str(resultado.iva_retenido),
                    str(resultado.isr_retenido), str(resultado.total),
                    resultado.metodo_pago, resultado.forma_pago,
                    resultado.uso_cfdi, resultado.moneda,
                    str(resultado.tipo_cambio),
                    contenido.decode("utf-8", errors="replace"),
                    resultado.exportacion,
                    resultado.lugar_expedicion,
                    resultado.domicilio_fiscal_receptor,
                    resultado.regimen_fiscal_receptor,
                    json.dumps(resultado.cfdi_relacionados),
                    resultado.es_anticipo_sat,
                ),
            )

            # Si es Complemento de Pago, persistir pagos y actualizar CFDIs relacionados
            if resultado.tipo_comprobante == "P" and resultado.pagos:
                _persistir_complemento_pago(empresa_id, resultado)

            procesados += 1
        except HTTPException:
            # Validación de archivo (extensión/content-type/tamaño): rechazo duro, no error suave
            raise
        except Exception as e:
            errores.append(f"{archivo.filename}: {str(e)}")

    if procesados > 0:
        _correr_pipeline(empresa_id, periodo, empresa["rfc"])

    return IngestaResponse(
        mensaje=f"{procesados} CFDI procesados correctamente",
        registros_procesados=procesados,
        errores=errores,
        periodo=periodo,
    )


@router.post("/api/v1/empresas/{empresa_id}/banco/upload")
async def subir_estado_cuenta(
    empresa_id: str,
    archivo: UploadFile = File(...),
    banco: str = Form(...),
    periodo: str = Form(...),
    current_user: dict = Depends(get_current_user),
):
    validar_acceso_empresa(empresa_id, current_user)
    empresa = empresa_or_404(empresa_id)
    from ..banco_parser import BancoParser
    parser = BancoParser()
    contenido = await archivo.read()
    validar_upload(archivo, contenido, _BANCO_EXTENSIONES, _BANCO_CONTENT_TYPES)

    try:
        if archivo.filename.endswith(".xlsx"):
            resultado = parser.parse_xlsx(contenido, banco=banco)
        else:
            resultado = parser.parse_csv(contenido, banco=banco)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    for mov in resultado.movimientos:
        db.execute(
            """
            INSERT INTO movimientos_bancarios (
                empresa_id, banco, archivo_origen,
                fecha, concepto, referencia, monto, tipo, saldo, rfc_detectado
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                empresa_id, banco, archivo.filename,
                mov.fecha, mov.concepto, mov.referencia,
                str(mov.monto), mov.tipo,
                str(mov.saldo) if mov.saldo is not None else None,
                mov.rfc_detectado,
            ),
        )

    if resultado.movimientos:
        _correr_pipeline(empresa_id, periodo, empresa["rfc"])

    return IngestaResponse(
        mensaje=f"{len(resultado.movimientos)} movimientos procesados",
        registros_procesados=len(resultado.movimientos),
        errores=resultado.errores,
        periodo=periodo,
    )
