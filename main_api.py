"""
API FastAPI — Plataforma de Auditoría Fiscal Preventiva
Conectada a PostgreSQL via db.py
"""
from __future__ import annotations

import json
import os
import uuid as _uuid
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Optional

import psycopg2
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, field_validator

try:
    from jose import JWTError, jwt
    JWT_OK = True
except ImportError:
    JWT_OK = False

try:
    import bcrypt as _bcrypt
    BCRYPT_OK = True
except ImportError:
    BCRYPT_OK = False

import db

# ─── JWT config ──────────────────────────────────────────────
JWT_SECRET    = os.environ.get("JWT_SECRET", "fiscalcore-dev-secret-change-in-prod")
JWT_ALGORITHM = "HS256"
JWT_EXP_HOURS = 8

_bearer = HTTPBearer(auto_error=False)

UPLOADS_DIR = Path("uploads/constancias")
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

# ─── App ─────────────────────────────────────────────────────
app = FastAPI(
    title="Plataforma de Auditoría Fiscal Preventiva",
    version="1.0.0",
    description="Sistema de detección automática de riesgos fiscales (SAT interno)",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://auditoria-fiscal.vercel.app"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Schemas ─────────────────────────────────────────────────

class EmpresaCreate(BaseModel):
    rfc: str
    razon_social: str
    regimen_fiscal: Optional[str] = None
    email: Optional[str] = None

    @field_validator("rfc")
    @classmethod
    def rfc_upper(cls, v: str) -> str:
        return v.strip().upper()


class IngestaResponse(BaseModel):
    mensaje: str
    registros_procesados: int
    errores: list[str]
    periodo: Optional[str]


class RegisterRequest(BaseModel):
    email: str
    password: str
    nombre: Optional[str] = None
    rfc: str
    razon_social: str
    regimen_fiscal: Optional[str] = None
    cp_fiscal: Optional[str] = None
    curp: Optional[str] = None
    obligaciones: Optional[list] = None

    @field_validator("rfc")
    @classmethod
    def rfc_upper(cls, v: str) -> str:
        return v.strip().upper()


class LoginRequest(BaseModel):
    email: str
    password: str


# ─── Helpers JWT ─────────────────────────────────────────────

def _crear_token(payload: dict) -> str:
    if not JWT_OK:
        raise HTTPException(status_code=500, detail="python-jose no instalado")
    data = payload.copy()
    data["exp"] = datetime.utcnow() + timedelta(hours=JWT_EXP_HOURS)
    return jwt.encode(data, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _verificar_token(token: str) -> dict:
    if not JWT_OK:
        raise HTTPException(status_code=500, detail="python-jose no instalado")
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")


def _get_current_user(creds: HTTPAuthorizationCredentials = Depends(_bearer)) -> dict:
    if not creds:
        raise HTTPException(status_code=401, detail="Se requiere autenticación")
    return _verificar_token(creds.credentials)


def _hash_password(plain: str) -> str:
    if not BCRYPT_OK:
        raise HTTPException(status_code=500, detail="bcrypt no instalado")
    return _bcrypt.hashpw(plain.encode(), _bcrypt.gensalt()).decode()


def _verify_password(plain: str, hashed: str) -> bool:
    if not BCRYPT_OK:
        return False
    return _bcrypt.checkpw(plain.encode(), hashed.encode())


# ─── Helpers DB ──────────────────────────────────────────────

def _empresa_or_404(empresa_id: str) -> dict:
    row = db.query_one("SELECT * FROM empresas WHERE id = %s", (empresa_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")
    return row


def _serializar(obj: dict) -> dict:
    """Convierte Decimal y datetime a tipos JSON-serializables."""
    result = {}
    for k, v in obj.items():
        if isinstance(v, Decimal):
            result[k] = float(v)
        elif isinstance(v, datetime):
            result[k] = v.isoformat()
        else:
            result[k] = v
    return result


# ─── Endpoints ───────────────────────────────────────────────

@app.get("/", tags=["Sistema"])
async def raiz():
    return {
        "sistema": "Plataforma de Auditoría Fiscal Preventiva",
        "version": "1.0.0",
        "estado": "operativo",
    }


# ── Auth ─────────────────────────────────────────────────────

@app.post("/api/v1/auth/register", status_code=status.HTTP_201_CREATED, tags=["Auth"])
async def registrar(data: RegisterRequest):
    """Crea una empresa y su usuario asociado. Retorna JWT."""
    # Validar que RFC no exista
    existente = db.query_one("SELECT id FROM empresas WHERE rfc = %s", (data.rfc,))
    if existente:
        raise HTTPException(status_code=409, detail=f"El RFC {data.rfc} ya está registrado")

    email_existente = db.query_one("SELECT id FROM usuarios WHERE email = %s", (data.email,))
    if email_existente:
        raise HTTPException(status_code=409, detail="El correo ya está registrado")

    try:
        empresa = db.execute(
            """
            INSERT INTO empresas (rfc, razon_social, regimen_fiscal, email, cp_fiscal, curp, obligaciones)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                data.rfc, data.razon_social, data.regimen_fiscal,
                data.email, data.cp_fiscal, data.curp,
                json.dumps(data.obligaciones) if data.obligaciones else None,
            ),
            returning=True,
        )
    except psycopg2.errors.UniqueViolation:
        raise HTTPException(status_code=409, detail=f"RFC {data.rfc} ya existe")

    password_hash = _hash_password(data.password)
    usuario = db.execute(
        """
        INSERT INTO usuarios (empresa_id, email, password_hash, nombre)
        VALUES (%s, %s, %s, %s)
        RETURNING *
        """,
        (str(empresa["id"]), data.email, password_hash, data.nombre),
        returning=True,
    )

    token = _crear_token({
        "user_id":    str(usuario["id"]),
        "empresa_id": str(empresa["id"]),
        "email":      data.email,
    })

    return {
        "access_token": token,
        "token_type": "bearer",
        "empresa_id": str(empresa["id"]),
        "rfc": empresa["rfc"],
        "razon_social": empresa["razon_social"],
    }


@app.post("/api/v1/auth/login", tags=["Auth"])
async def login(data: LoginRequest):
    """Autentica un usuario y retorna JWT."""
    usuario = db.query_one(
        "SELECT u.*, e.rfc, e.razon_social FROM usuarios u JOIN empresas e ON e.id = u.empresa_id WHERE u.email = %s AND u.activo = TRUE",
        (data.email,),
    )
    if not usuario or not _verify_password(data.password, usuario["password_hash"]):
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")

    token = _crear_token({
        "user_id":    str(usuario["id"]),
        "empresa_id": str(usuario["empresa_id"]),
        "email":      data.email,
    })

    return {
        "access_token": token,
        "token_type": "bearer",
        "empresa_id": str(usuario["empresa_id"]),
        "rfc": usuario["rfc"],
        "razon_social": usuario["razon_social"],
    }


@app.get("/api/v1/auth/me", tags=["Auth"])
async def me(current_user: dict = Depends(_get_current_user)):
    """Retorna info del usuario autenticado."""
    usuario = db.query_one(
        "SELECT u.id, u.email, u.nombre, u.empresa_id, e.rfc, e.razon_social, e.regimen_fiscal FROM usuarios u JOIN empresas e ON e.id = u.empresa_id WHERE u.id = %s",
        (current_user["user_id"],),
    )
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return _serializar(usuario)


# ── Constancia ────────────────────────────────────────────────

@app.post("/api/v1/constancia/parsear", tags=["Constancia"])
async def parsear_constancia_pdf(archivo: UploadFile = File(...)):
    """Extrae datos fiscales de la Constancia de Situación Fiscal (PDF SAT)."""
    if not archivo.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="El archivo debe ser PDF")

    contenido = await archivo.read()

    try:
        from constancia_parser import parsear_constancia
        datos = parsear_constancia(contenido)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"No se pudo leer el PDF: {str(e)}")

    # Guardar PDF
    nombre_archivo = f"{_uuid.uuid4()}.pdf"
    ruta = UPLOADS_DIR / nombre_archivo
    ruta.write_bytes(contenido)
    datos["constancia_path"] = nombre_archivo

    return datos


# ── Empresas ─────────────────────────────────────────────────

@app.get("/api/v1/empresas", tags=["Empresas"])
async def listar_empresas():
    rows = db.query_all("SELECT * FROM empresas WHERE activo = TRUE ORDER BY created_at DESC")
    return [_serializar(r) for r in rows]


@app.post("/api/v1/empresas", status_code=status.HTTP_201_CREATED, tags=["Empresas"])
async def crear_empresa(data: EmpresaCreate):
    try:
        row = db.execute(
            """
            INSERT INTO empresas (rfc, razon_social, regimen_fiscal, email)
            VALUES (%s, %s, %s, %s)
            RETURNING *
            """,
            (data.rfc, data.razon_social, data.regimen_fiscal, data.email),
            returning=True,
        )
    except psycopg2.errors.UniqueViolation:
        raise HTTPException(status_code=409, detail=f"RFC {data.rfc} ya existe")
    return {"mensaje": "Empresa creada", "empresa": _serializar(row)}


@app.get("/api/v1/empresas/{empresa_id}", tags=["Empresas"])
async def obtener_empresa(empresa_id: str):
    return _serializar(_empresa_or_404(empresa_id))


# ── Dashboard ─────────────────────────────────────────────────

@app.get("/api/v1/dashboard/{empresa_id}", tags=["Dashboard"])
async def dashboard(empresa_id: str, periodo: Optional[str] = None):
    empresa = _empresa_or_404(empresa_id)

    # Scoring más reciente (o del período solicitado)
    if periodo:
        score_row = db.query_one(
            "SELECT * FROM scoring_fiscal WHERE empresa_id = %s AND periodo = %s",
            (empresa_id, periodo),
        )
    else:
        score_row = db.query_one(
            "SELECT * FROM scoring_fiscal WHERE empresa_id = %s ORDER BY periodo DESC LIMIT 1",
            (empresa_id,),
        )

    periodo_actual = periodo or (score_row["periodo"] if score_row else None)

    # Riesgos abiertos del período
    if periodo_actual:
        riesgos_rows = db.query_all(
            """
            SELECT d.id, r.codigo, r.nombre, r.severidad,
                   d.monto_afectado, d.descripcion,
                   d.cfdi_id, d.movimiento_id, d.estado, d.periodo, d.created_at
            FROM detecciones d
            JOIN riesgos r ON r.id = d.riesgo_id
            WHERE d.empresa_id = %s AND d.estado = 'abierto' AND d.periodo = %s
            ORDER BY
                CASE r.severidad WHEN 'critico' THEN 1 WHEN 'alto' THEN 2
                                 WHEN 'medio' THEN 3 ELSE 4 END
            """,
            (empresa_id, periodo_actual),
        )
    else:
        riesgos_rows = db.query_all(
            """
            SELECT d.id, r.codigo, r.nombre, r.severidad,
                   d.monto_afectado, d.descripcion,
                   d.cfdi_id, d.movimiento_id, d.estado, d.periodo, d.created_at
            FROM detecciones d
            JOIN riesgos r ON r.id = d.riesgo_id
            WHERE d.empresa_id = %s AND d.estado = 'abierto'
            ORDER BY
                CASE r.severidad WHEN 'critico' THEN 1 WHEN 'alto' THEN 2
                                 WHEN 'medio' THEN 3 ELSE 4 END
            LIMIT 50
            """,
            (empresa_id,),
        )

    riesgos = [_serializar(r) for r in riesgos_rows]

    resumen = {
        "critico": sum(1 for r in riesgos if r["severidad"] == "critico"),
        "alto":    sum(1 for r in riesgos if r["severidad"] == "alto"),
        "medio":   sum(1 for r in riesgos if r["severidad"] == "medio"),
        "bajo":    sum(1 for r in riesgos if r["severidad"] == "bajo"),
        "monto_total_en_riesgo": sum(r.get("monto_afectado") or 0 for r in riesgos),
    }

    # Tendencia de scores
    tendencia = db.query_all(
        "SELECT periodo, score_total AS score FROM scoring_fiscal WHERE empresa_id = %s ORDER BY periodo",
        (empresa_id,),
    )

    score_out = _serializar(score_row) if score_row else None
    indicadores = {}
    if score_row:
        dep = float(score_row.get("total_depositos_banco") or 0)
        car = float(score_row.get("total_cargos_banco") or 0)
        ing = float(score_row.get("total_ingresos_cfdi") or 0)
        egr = float(score_row.get("total_egresos_cfdi") or 0)
        tot = score_row.get("total_movimientos") or 0
        con = score_row.get("total_conciliados") or 0
        indicadores = {
            "ingresos_cfdi": ing,
            "egresos_cfdi": egr,
            "depositos_banco": dep,
            "cargos_banco": car,
            "brecha_ingresos": dep - ing,
            "brecha_egresos": car - egr,
            "pct_conciliacion": round(con / tot * 100, 1) if tot > 0 else 0,
        }

    return {
        "empresa": _serializar(empresa),
        "score_actual": score_out,
        "riesgos_abiertos": riesgos,
        "resumen_riesgos": resumen,
        "tendencia_score": tendencia,
        "indicadores": indicadores,
    }


# ── Ingesta CFDI ─────────────────────────────────────────────

@app.post("/api/v1/empresas/{empresa_id}/cfdi/upload", tags=["Ingesta"])
async def subir_cfdi(
    empresa_id: str,
    archivos: list[UploadFile] = File(...),
    periodo: str = Form(...),
):
    empresa = _empresa_or_404(empresa_id)
    from cfdi_parser import CFDIParser
    parser = CFDIParser()
    procesados = 0
    errores: list[str] = []

    for archivo in archivos:
        try:
            contenido = await archivo.read()
            resultado = parser.parse_xml(contenido)
            if resultado.errores:
                errores += [f"{archivo.filename}: {e}" for e in resultado.errores]
                continue

            # Insertar en DB (ignorar duplicados por UUID)
            db.execute(
                """
                INSERT INTO cfdi (
                    empresa_id, uuid, tipo_comprobante, serie, folio, version,
                    rfc_emisor, nombre_emisor, rfc_receptor, nombre_receptor,
                    fecha_emision, fecha_timbrado,
                    subtotal, descuento, iva_trasladado, iva_retenido, isr_retenido, total,
                    metodo_pago, forma_pago, uso_cfdi, moneda, tipo_cambio, xml_raw
                ) VALUES (
                    %s,%s,%s,%s,%s,%s,
                    %s,%s,%s,%s,
                    %s,%s,
                    %s,%s,%s,%s,%s,%s,
                    %s,%s,%s,%s,%s,%s
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
                ),
            )
            procesados += 1
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


# ── Ingesta bancaria ─────────────────────────────────────────

@app.post("/api/v1/empresas/{empresa_id}/banco/upload", tags=["Ingesta"])
async def subir_estado_cuenta(
    empresa_id: str,
    archivo: UploadFile = File(...),
    banco: str = Form(...),
    periodo: str = Form(...),
):
    empresa = _empresa_or_404(empresa_id)
    from banco_parser import BancoParser
    parser = BancoParser()
    contenido = await archivo.read()

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


# ── Pipeline fiscal (conciliación → riesgos → scoring) ───────

def _correr_pipeline(empresa_id: str, periodo: str, rfc_empresa: str) -> None:
    """Ejecuta el motor fiscal completo para un período y persiste los resultados."""
    from motor_fiscal import (
        CFDIResumen, MovResumen,
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

    # Conciliación
    motor_conc = MotorConciliacion()
    conciliaciones = motor_conc.conciliar(movimientos, cfdis, rfc_empresa)

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
                tipo_match, monto_movimiento, monto_cfdi, diferencia, porcentaje_match, periodo, notas
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
            ),
        )

    # Riesgos
    motor_riesgos = MotorRiesgos()
    riesgos = motor_riesgos.detectar_todos(movimientos, cfdis, conciliaciones, rfc_empresa)

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
    score = motor_scoring.calcular(movimientos, cfdis, conciliaciones, riesgos)

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


# ── Riesgos ──────────────────────────────────────────────────

@app.get("/api/v1/empresas/{empresa_id}/riesgos", tags=["Riesgos"])
async def listar_riesgos(
    empresa_id: str,
    periodo: Optional[str] = None,
    severidad: Optional[str] = None,
    estado: str = "abierto",
):
    _empresa_or_404(empresa_id)

    sql = """
        SELECT d.id, r.codigo, r.nombre, r.severidad,
               d.monto_afectado, d.descripcion,
               d.cfdi_id, d.movimiento_id, d.estado, d.periodo, d.created_at
        FROM detecciones d
        JOIN riesgos r ON r.id = d.riesgo_id
        WHERE d.empresa_id = %s
    """
    params: list = [empresa_id]

    if estado:
        sql += " AND d.estado = %s"
        params.append(estado)
    if periodo:
        sql += " AND d.periodo = %s"
        params.append(periodo)
    if severidad:
        sql += " AND r.severidad = %s"
        params.append(severidad)

    sql += """
        ORDER BY CASE r.severidad WHEN 'critico' THEN 1 WHEN 'alto' THEN 2
                                   WHEN 'medio' THEN 3 ELSE 4 END, d.created_at DESC
    """

    rows = db.query_all(sql, tuple(params))
    riesgos = [_serializar(r) for r in rows]
    return {"total": len(riesgos), "riesgos": riesgos}


@app.patch("/api/v1/riesgos/{riesgo_id}/resolver", tags=["Riesgos"])
async def resolver_riesgo(riesgo_id: str, notas: str = ""):
    row = db.execute(
        """
        UPDATE detecciones
        SET estado = 'resuelto', resuelto_en = NOW(), notas_resolucion = %s
        WHERE id = %s
        RETURNING id, estado
        """,
        (notas, riesgo_id),
        returning=True,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Riesgo no encontrado")
    return {"mensaje": "Riesgo marcado como resuelto", "riesgo_id": riesgo_id, "estado": "resuelto"}


# ── Scoring ───────────────────────────────────────────────────

@app.get("/api/v1/empresas/{empresa_id}/scoring", tags=["Scoring"])
async def obtener_scoring(empresa_id: str, periodo: Optional[str] = None):
    _empresa_or_404(empresa_id)
    if periodo:
        row = db.query_one(
            "SELECT * FROM scoring_fiscal WHERE empresa_id = %s AND periodo = %s",
            (empresa_id, periodo),
        )
    else:
        row = db.query_one(
            "SELECT * FROM scoring_fiscal WHERE empresa_id = %s ORDER BY periodo DESC LIMIT 1",
            (empresa_id,),
        )
    if not row:
        raise HTTPException(status_code=404, detail="Sin scoring para este período")
    return _serializar(row)


@app.get("/api/v1/empresas/{empresa_id}/scoring/historial", tags=["Scoring"])
async def historial_scoring(empresa_id: str):
    _empresa_or_404(empresa_id)
    rows = db.query_all(
        "SELECT periodo, score_total AS score, clasificacion FROM scoring_fiscal WHERE empresa_id = %s ORDER BY periodo",
        (empresa_id,),
    )
    return {"historial": rows}


# ── Conciliación ──────────────────────────────────────────────

@app.get("/api/v1/empresas/{empresa_id}/conciliaciones", tags=["Conciliación"])
async def listar_conciliaciones(empresa_id: str, periodo: Optional[str] = None):
    _empresa_or_404(empresa_id)

    sql = "SELECT tipo_match, COUNT(*) AS total FROM conciliaciones WHERE empresa_id = %s"
    params: list = [empresa_id]
    if periodo:
        sql += " AND periodo = %s"
        params.append(periodo)
    sql += " GROUP BY tipo_match"

    rows = db.query_all(sql, tuple(params))
    conteos = {r["tipo_match"]: r["total"] for r in rows}

    total = sum(conteos.values())
    conciliados = conteos.get("exacto", 0) + conteos.get("parcial", 0)
    pct = round(conciliados / total * 100, 1) if total > 0 else 0.0

    return {
        "total": total,
        "exacto": conteos.get("exacto", 0),
        "parcial": conteos.get("parcial", 0),
        "sin_cfdi": conteos.get("sin_cfdi", 0),
        "sin_movimiento": conteos.get("sin_movimiento", 0),
        "pct_conciliado": pct,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
