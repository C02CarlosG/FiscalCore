"""
API FastAPI — Plataforma de Auditoría Fiscal Preventiva
Conectada a PostgreSQL via db.py
"""
from __future__ import annotations

import json
import logging
import os
import uuid as _uuid
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Optional

import psycopg2
import psycopg2.extras
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, field_validator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
_log = logging.getLogger(__name__)

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
_JWT_INSECURE_DEFAULT = "fiscalcore-dev-secret-change-in-prod"
JWT_SECRET    = os.environ.get("JWT_SECRET", _JWT_INSECURE_DEFAULT)
JWT_ALGORITHM = "HS256"
JWT_EXP_HOURS = 8

_bearer = HTTPBearer(auto_error=False)

UPLOADS_DIR = Path("uploads/constancias")
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

# ─── CORS ────────────────────────────────────────────────────
# Configura ALLOWED_ORIGINS en Railway con los dominios del frontend separados por coma.
# Ejemplo: https://fiscalcore.vercel.app,https://app.fiscalcore.mx
_ALLOWED_ORIGINS = [
    o.strip()
    for o in os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:5173,http://localhost:3000",
    ).split(",")
    if o.strip()
]

# ─── App ─────────────────────────────────────────────────────
app = FastAPI(
    title="Plataforma de Auditoría Fiscal Preventiva",
    version="1.0.0",
    description="Sistema de detección automática de riesgos fiscales (SAT interno)",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def _startup() -> None:
    if JWT_SECRET == _JWT_INSECURE_DEFAULT:
        _log.warning("JWT_SECRET no configurado — usando clave de desarrollo (inseguro en producción)")
    _log.info("CORS permitido para: %s", _ALLOWED_ORIGINS)
    _log.info("Inicializando schema de base de datos...")
    db.init_db()
    _log.info("FiscalCore API lista")


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


class AgregarEmpresaRequest(BaseModel):
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


def _validar_acceso_empresa(empresa_id: str, current_user: dict) -> None:
    row = db.query_one(
        "SELECT 1 FROM usuario_empresas WHERE usuario_id = %s AND empresa_id = %s",
        (current_user["user_id"], empresa_id),
    )
    if not row:
        raise HTTPException(status_code=403, detail="Sin acceso a esta empresa")


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
    """Registra un contador (usuario). Retorna JWT. Las empresas se agregan después con POST /mis-empresas."""
    email_existente = db.query_one("SELECT id FROM usuarios WHERE email = %s", (data.email,))
    if email_existente:
        raise HTTPException(status_code=409, detail="El correo ya está registrado")

    password_hash = _hash_password(data.password)
    usuario = db.execute(
        "INSERT INTO usuarios (email, password_hash, nombre) VALUES (%s, %s, %s) RETURNING *",
        (data.email, password_hash, data.nombre),
        returning=True,
    )

    token = _crear_token({"user_id": str(usuario["id"]), "email": data.email})

    return {
        "access_token": token,
        "token_type":   "bearer",
        "user_id":      str(usuario["id"]),
        "email":        data.email,
        "nombre":       data.nombre,
        "empresas":     [],
    }


@app.post("/api/v1/auth/login", tags=["Auth"])
async def login(data: LoginRequest):
    """Autentica un contador y retorna JWT + lista de empresas que administra."""
    usuario = db.query_one(
        "SELECT * FROM usuarios WHERE email = %s AND activo = TRUE",
        (data.email,),
    )
    if not usuario or not _verify_password(data.password, usuario["password_hash"]):
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")

    empresas = db.query_all(
        """
        SELECT e.id AS empresa_id, e.rfc, e.razon_social, e.regimen_fiscal
        FROM empresas e
        JOIN usuario_empresas ue ON ue.empresa_id = e.id
        WHERE ue.usuario_id = %s AND e.activo = TRUE
        ORDER BY ue.created_at ASC
        """,
        (str(usuario["id"]),),
    )

    token = _crear_token({"user_id": str(usuario["id"]), "email": data.email})

    return {
        "access_token": token,
        "token_type":   "bearer",
        "user_id":      str(usuario["id"]),
        "nombre":       usuario.get("nombre"),
        "empresas":     [_serializar(e) for e in empresas],
    }


@app.get("/api/v1/auth/me", tags=["Auth"])
async def me(current_user: dict = Depends(_get_current_user)):
    """Retorna info del usuario autenticado y sus empresas."""
    usuario = db.query_one(
        "SELECT id, email, nombre FROM usuarios WHERE id = %s",
        (current_user["user_id"],),
    )
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    empresas = db.query_all(
        """
        SELECT e.id AS empresa_id, e.rfc, e.razon_social, e.regimen_fiscal
        FROM empresas e
        JOIN usuario_empresas ue ON ue.empresa_id = e.id
        WHERE ue.usuario_id = %s AND e.activo = TRUE
        ORDER BY ue.created_at ASC
        """,
        (current_user["user_id"],),
    )

    return {**_serializar(usuario), "empresas": [_serializar(e) for e in empresas]}


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
async def listar_empresas(current_user: dict = Depends(_get_current_user)):
    """Retorna las empresas que administra el contador autenticado."""
    rows = db.query_all(
        """
        SELECT e.* FROM empresas e
        JOIN usuario_empresas ue ON ue.empresa_id = e.id
        WHERE ue.usuario_id = %s AND e.activo = TRUE
        ORDER BY ue.created_at ASC
        """,
        (current_user["user_id"],),
    )
    return [_serializar(r) for r in rows]


@app.post("/api/v1/mis-empresas", status_code=status.HTTP_201_CREATED, tags=["Empresas"])
async def agregar_empresa(
    data: AgregarEmpresaRequest,
    current_user: dict = Depends(_get_current_user),
):
    """Crea (o encuentra por RFC) una empresa y la vincula al contador autenticado."""
    # Si ya existe empresa con ese RFC, reutilizarla
    empresa = db.query_one("SELECT * FROM empresas WHERE rfc = %s", (data.rfc,))

    if not empresa:
        try:
            empresa = db.execute(
                """
                INSERT INTO empresas (rfc, razon_social, regimen_fiscal, cp_fiscal, curp, obligaciones)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING *
                """,
                (
                    data.rfc, data.razon_social, data.regimen_fiscal,
                    data.cp_fiscal, data.curp,
                    json.dumps(data.obligaciones) if data.obligaciones else None,
                ),
                returning=True,
            )
        except psycopg2.errors.UniqueViolation:
            empresa = db.query_one("SELECT * FROM empresas WHERE rfc = %s", (data.rfc,))

    # Vincular al usuario (idempotente)
    ya_vinculada = db.query_one(
        "SELECT 1 FROM usuario_empresas WHERE usuario_id = %s AND empresa_id = %s",
        (current_user["user_id"], str(empresa["id"])),
    )
    if not ya_vinculada:
        db.execute(
            "INSERT INTO usuario_empresas (usuario_id, empresa_id) VALUES (%s, %s)",
            (current_user["user_id"], str(empresa["id"])),
        )

    return {
        "mensaje":    "Empresa vinculada correctamente",
        "empresa_id": str(empresa["id"]),
        "rfc":        empresa["rfc"],
        "razon_social": empresa["razon_social"],
    }


@app.get("/api/v1/empresas/{empresa_id}", tags=["Empresas"])
async def obtener_empresa(empresa_id: str, current_user: dict = Depends(_get_current_user)):
    _validar_acceso_empresa(empresa_id, current_user)
    return _serializar(_empresa_or_404(empresa_id))


# ── Dashboard ─────────────────────────────────────────────────

@app.get("/api/v1/dashboard/{empresa_id}", tags=["Dashboard"])
async def dashboard(empresa_id: str, periodo: Optional[str] = None, current_user: dict = Depends(_get_current_user)):
    _validar_acceso_empresa(empresa_id, current_user)
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
    current_user: dict = Depends(_get_current_user),
):
    _validar_acceso_empresa(empresa_id, current_user)
    empresa = _empresa_or_404(empresa_id)
    from cfdi_parser import CFDIParser
    parser = CFDIParser()
    procesados = 0
    errores: list[str] = []

    for archivo in archivos:
        try:
            contenido = await archivo.read()
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
                    domicilio_fiscal_receptor, regimen_fiscal_receptor
                ) VALUES (
                    %s,%s,%s,%s,%s,%s,
                    %s,%s,%s,%s,
                    %s,%s,
                    %s,%s,%s,%s,%s,%s,
                    %s,%s,%s,%s,%s,%s,
                    %s,%s,%s,%s
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
                ),
            )

            # Si es Complemento de Pago, persistir pagos y actualizar CFDIs relacionados
            if resultado.tipo_comprobante == "P" and resultado.pagos:
                _persistir_complemento_pago(empresa_id, resultado)

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


# ── Complemento de Pago 2.0 ──────────────────────────────────

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


# ── Ingesta bancaria ─────────────────────────────────────────

@app.post("/api/v1/empresas/{empresa_id}/banco/upload", tags=["Ingesta"])
async def subir_estado_cuenta(
    empresa_id: str,
    archivo: UploadFile = File(...),
    banco: str = Form(...),
    periodo: str = Form(...),
    current_user: dict = Depends(_get_current_user),
):
    _validar_acceso_empresa(empresa_id, current_user)
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


# ── Riesgos ──────────────────────────────────────────────────

@app.get("/api/v1/empresas/{empresa_id}/riesgos", tags=["Riesgos"])
async def listar_riesgos(
    empresa_id: str,
    periodo: Optional[str] = None,
    severidad: Optional[str] = None,
    estado: str = "abierto",
    current_user: dict = Depends(_get_current_user),
):
    _validar_acceso_empresa(empresa_id, current_user)
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
async def obtener_scoring(empresa_id: str, periodo: Optional[str] = None, current_user: dict = Depends(_get_current_user)):
    _validar_acceso_empresa(empresa_id, current_user)
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
async def historial_scoring(empresa_id: str, current_user: dict = Depends(_get_current_user)):
    _validar_acceso_empresa(empresa_id, current_user)
    _empresa_or_404(empresa_id)
    rows = db.query_all(
        "SELECT periodo, score_total AS score, clasificacion FROM scoring_fiscal WHERE empresa_id = %s ORDER BY periodo",
        (empresa_id,),
    )
    return {"historial": rows}


# ── Conciliación ──────────────────────────────────────────────

@app.get("/api/v1/empresas/{empresa_id}/conciliaciones", tags=["Conciliación"])
async def listar_conciliaciones(empresa_id: str, periodo: Optional[str] = None, current_user: dict = Depends(_get_current_user)):
    _validar_acceso_empresa(empresa_id, current_user)
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


# ── Acciones granulares ───────────────────────────────────────

ACCION_ESTADO = {
    "marcar_revisado": "en_revision",
    "solicitar_cfdi":  "en_espera_cfdi",
    "emitir_cfdi":     "en_espera_cfdi",
    "confirmar_match": "confirmado",
    "descartar":       "descartado",
    "resolver":        "resuelto",
}


class AccionRequest(BaseModel):
    tipo: str
    notas: Optional[str] = None


@app.post("/api/v1/acciones/{deteccion_id}/ejecutar", tags=["Acciones"])
async def ejecutar_accion(deteccion_id: str, body: AccionRequest):
    """Ejecuta una acción sobre una detección y actualiza su estado."""
    det = db.query_one("SELECT estado FROM detecciones WHERE id = %s", (deteccion_id,))
    if not det:
        raise HTTPException(status_code=404, detail="Detección no encontrada")

    nuevo_estado = ACCION_ESTADO.get(body.tipo)
    if not nuevo_estado:
        raise HTTPException(status_code=400, detail=f"Tipo de acción desconocido: {body.tipo}")

    db.execute(
        """
        UPDATE detecciones
        SET estado = %s, updated_at = NOW(), notas_resolucion = %s,
            resuelto_en = CASE WHEN %s IN ('resuelto','descartado','confirmado') THEN NOW() ELSE resuelto_en END
        WHERE id = %s
        """,
        (nuevo_estado, body.notas or "", nuevo_estado, deteccion_id),
    )

    return {
        "deteccion_id": deteccion_id,
        "estado_anterior": det["estado"],
        "estado_nuevo": nuevo_estado,
    }


# ── Vista de cierre mensual ───────────────────────────────────

@app.get("/api/v1/empresas/{empresa_id}/cierre/{periodo}", tags=["Cierre"])
async def vista_cierre(empresa_id: str, periodo: str, current_user: dict = Depends(_get_current_user)):
    """
    Vista consolidada para el cierre mensual.
    Responde: ¿Puedo cerrar? / ¿Qué me falta? / ¿Qué hago hoy?
    """
    _validar_acceso_empresa(empresa_id, current_user)
    _empresa_or_404(empresa_id)

    # Detecciones accionables (abierto, pendiente, en_revision, en_espera_cfdi)
    detecciones_rows = db.query_all(
        """
        SELECT
            d.id, d.estado, d.monto_afectado, d.descripcion, d.periodo,
            d.cfdi_id, d.movimiento_id, d.created_at,
            r.codigo, r.nombre, r.severidad, r.accion_sugerida,
            c.uuid        AS cfdi_uuid,
            c.fecha_emision AS cfdi_fecha,
            c.rfc_emisor  AS cfdi_rfc_emisor,
            c.rfc_receptor AS cfdi_rfc_receptor,
            c.total       AS cfdi_total,
            m.fecha       AS mov_fecha,
            m.concepto    AS mov_concepto,
            m.monto       AS mov_monto,
            m.rfc_detectado AS mov_rfc
        FROM detecciones d
        JOIN riesgos r ON r.id = d.riesgo_id
        LEFT JOIN cfdi c ON c.id = d.cfdi_id
        LEFT JOIN movimientos_bancarios m ON m.id = d.movimiento_id
        WHERE d.empresa_id = %s
          AND d.periodo = %s
          AND d.estado IN ('abierto','pendiente','en_revision','en_espera_cfdi')
        ORDER BY
            CASE r.severidad WHEN 'critico' THEN 1 WHEN 'alto' THEN 2
                             WHEN 'medio' THEN 3 ELSE 4 END,
            d.monto_afectado DESC NULLS LAST
        """,
        (empresa_id, periodo),
    )

    acciones = []
    for row in detecciones_rows:
        item = _serializar(row)
        # Contexto mínimo para el ítem de acción
        item["contexto"] = {}
        if row["cfdi_uuid"]:
            item["contexto"] = {
                "tipo": "cfdi",
                "uuid":  row["cfdi_uuid"],
                "fecha": row["cfdi_fecha"].isoformat() if row["cfdi_fecha"] else None,
                "rfc":   row["cfdi_rfc_emisor"] or row["cfdi_rfc_receptor"],
                "total": float(row["cfdi_total"] or 0),
            }
        elif row["mov_fecha"]:
            item["contexto"] = {
                "tipo":    "movimiento",
                "fecha":   row["mov_fecha"].isoformat() if row["mov_fecha"] else None,
                "concepto": (row["mov_concepto"] or "")[:80],
                "monto":   float(row["mov_monto"] or 0),
                "rfc":     row["mov_rfc"],
            }
        acciones.append(item)

    bloqueadores = [a for a in acciones if a["severidad"] in ("critico", "alto")]

    # Conciliación del período
    conc_rows = db.query_all(
        """
        SELECT tipo_match, COUNT(*) AS total
        FROM conciliaciones
        WHERE empresa_id = %s AND periodo = %s
        GROUP BY tipo_match
        """,
        (empresa_id, periodo),
    )
    conc = {r["tipo_match"]: r["total"] for r in conc_rows}
    total_mov = sum(conc.values())

    # Heurísticos de alta confianza: consulta separada porque necesitamos filtrar por confianza
    heur_alta = db.query_one(
        """
        SELECT COUNT(*) AS total FROM conciliaciones
        WHERE empresa_id = %s AND periodo = %s
          AND tipo_match = 'heuristico' AND confianza = 'alta'
        """,
        (empresa_id, periodo),
    )
    conciliados = (
        conc.get("exacto", 0)
        + conc.get("parcial", 0)
        + conc.get("complemento_pago", 0)
        + conc.get("agrupado", 0)
        + conc.get("parcial_multiple", 0)
        + (heur_alta["total"] if heur_alta else 0)
    )
    pct_conciliado = round(conciliados / total_mov * 100, 1) if total_mov else 0.0
    matches_debiles = conc.get("parcial", 0) + conc.get("parcial_multiple", 0)

    # Score más reciente del período
    score_row = db.query_one(
        "SELECT score_total FROM scoring_fiscal WHERE empresa_id = %s AND periodo = %s",
        (empresa_id, periodo),
    )
    score = float(score_row["score_total"]) if score_row else None

    puede_cerrar = len(bloqueadores) == 0 and pct_conciliado >= 80.0

    razon_bloqueo = None
    if not puede_cerrar:
        razones = []
        if bloqueadores:
            razones.append(f"{len(bloqueadores)} riesgo{'s' if len(bloqueadores)>1 else ''} crítico{'s' if len(bloqueadores)>1 else ''}/alto{'s' if len(bloqueadores)>1 else ''} abierto{'s' if len(bloqueadores)>1 else ''}")
        if pct_conciliado < 80.0:
            razones.append(f"conciliación al {pct_conciliado}% (mínimo 80%)")
        razon_bloqueo = " · ".join(razones)

    return {
        "periodo": periodo,
        "puede_cerrar": puede_cerrar,
        "razon_bloqueo": razon_bloqueo,
        "score": score,
        "bloqueadores": bloqueadores,
        "acciones": acciones,
        "conciliacion": {
            "sin_cfdi":       conc.get("sin_cfdi", 0),
            "sin_movimiento": conc.get("sin_movimiento", 0),
            "matches_debiles": matches_debiles,
            "pct_conciliado": pct_conciliado,
            "total":          total_mov,
        },
    }


# ── Conciliaciones accionables ────────────────────────────────

@app.get("/api/v1/empresas/{empresa_id}/conciliaciones/accionables", tags=["Conciliación"])
async def conciliaciones_accionables(empresa_id: str, periodo: Optional[str] = None, current_user: dict = Depends(_get_current_user)):
    """Pares sin_cfdi y parciales con contexto del movimiento bancario."""
    _validar_acceso_empresa(empresa_id, current_user)
    _empresa_or_404(empresa_id)

    sql = """
        SELECT
            con.id, con.tipo_match, con.monto_movimiento, con.monto_cfdi,
            con.diferencia, con.porcentaje_match, con.periodo,
            m.id    AS movimiento_id,
            m.fecha AS mov_fecha,
            m.concepto,
            m.monto AS mov_monto,
            m.tipo  AS mov_tipo,
            m.rfc_detectado
        FROM conciliaciones con
        LEFT JOIN movimientos_bancarios m ON m.id = con.movimiento_id
        WHERE con.empresa_id = %s
          AND con.tipo_match IN ('sin_cfdi','parcial')
    """
    params: list = [empresa_id]
    if periodo:
        sql += " AND con.periodo = %s"
        params.append(periodo)
    sql += " ORDER BY con.monto_movimiento DESC NULLS LAST LIMIT 100"

    rows = db.query_all(sql, tuple(params))
    return {"total": len(rows), "pares": [_serializar(r) for r in rows]}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
