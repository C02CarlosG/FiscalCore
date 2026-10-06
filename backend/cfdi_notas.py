"""Etiquetas, comentarios y evidencias de los CFDI (F3.6).

Todo se enlaza por ``cfdi.id`` y se acota a la empresa de la sesión: un UUID, una
etiqueta o una evidencia de otra empresa se trata igual que uno inexistente
(``None`` o ``NoEncontrado``; el router responde 404). Un reproceso del XML solo
reescribe el detalle extraído, así que nada de esto se pierde.
"""
from __future__ import annotations

import hashlib
import io
import re
import zipfile
from typing import Any, Optional

import psycopg2

from . import db

MAX_ETIQUETAS_EMPRESA = 100
MAX_LOTE_CFDI = 500
MAX_LOTE_ETIQUETAS = 10
MAX_COMENTARIO = 2000
MAX_EVIDENCIA_BYTES = 5 * 1024 * 1024
MAX_EVIDENCIAS_CFDI = 20
MAX_NOMBRE_ARCHIVO = 120

_COLOR_RE = re.compile(r"#[0-9a-fA-F]{6}")
_UUID_RE = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")


class NoEncontrado(LookupError):
    """El recurso no existe o es de otra empresa."""


class Invalido(ValueError):
    """Entrada mal formada (422)."""


class Excede(ValueError):
    """Pasa un tope de tamaño (413)."""


class Conflicto(ValueError):
    """Choca con algo existente (409)."""


class SinPermiso(PermissionError):
    """Solo quien lo creó o un administrador de la empresa puede hacerlo (403)."""


def es_uuid(valor: Any) -> bool:
    return isinstance(valor, str) and _UUID_RE.fullmatch(valor) is not None


def _json(fila: dict) -> dict:
    return {k: (str(v) if k.endswith("id") and v is not None else (v.isoformat() if hasattr(v, "isoformat") else v))
            for k, v in fila.items()}


def _cfdi_id(empresa_id: str, uuid: str) -> str:
    fila = db.query_one("SELECT id FROM cfdi WHERE empresa_id = %s AND uuid = %s", (empresa_id, uuid)) if len(uuid) <= 36 else None
    if fila is None:
        raise NoEncontrado("CFDI no encontrado")
    return str(fila["id"])


def _es_administrador(empresa_id: str, usuario_id: str) -> bool:
    return db.query_one(
        "SELECT 1 FROM usuario_empresas WHERE empresa_id = %s AND usuario_id = %s AND rol = 'administrador'",
        (empresa_id, usuario_id)) is not None


def _puede_borrar(empresa_id: str, usuario_id: str, autor_id: Optional[Any]) -> bool:
    return (autor_id is not None and str(autor_id) == str(usuario_id)) or _es_administrador(empresa_id, usuario_id)


# ---------------------------------------------------------------------------
# Etiquetas
# ---------------------------------------------------------------------------

def _nombre_etiqueta(nombre: Any) -> str:
    if not isinstance(nombre, str):
        raise Invalido("El nombre de la etiqueta es obligatorio")
    nombre = " ".join(nombre.split())
    if not nombre or len(nombre) > 40 or any(ord(c) < 32 for c in nombre):
        raise Invalido("El nombre de la etiqueta debe tener entre 1 y 40 caracteres")
    return nombre


def _color(color: Any) -> str:
    if not isinstance(color, str) or not _COLOR_RE.fullmatch(color):
        raise Invalido("El color debe ser #RRGGBB")
    return color.lower()


def listar_etiquetas(empresa_id: str) -> list[dict]:
    filas = db.query_all(
        """
        SELECT e.id, e.nombre, e.color,
               (SELECT COUNT(*) FROM cfdi_etiquetas ce WHERE ce.etiqueta_id = e.id) AS cfdis
        FROM etiquetas e WHERE e.empresa_id = %s ORDER BY lower(e.nombre)
        """, (empresa_id,))
    return [{"id": str(f["id"]), "nombre": f["nombre"], "color": f["color"], "cfdis": int(f["cfdis"])} for f in filas]


def crear_etiqueta(empresa_id: str, nombre: Any, color: Any = "#64748b") -> dict:
    nombre, color = _nombre_etiqueta(nombre), _color(color)
    existentes = db.query_one("SELECT COUNT(*) AS n FROM etiquetas WHERE empresa_id = %s", (empresa_id,))["n"]
    if existentes >= MAX_ETIQUETAS_EMPRESA:
        raise Excede(f"Una empresa admite hasta {MAX_ETIQUETAS_EMPRESA} etiquetas")
    try:
        fila = db.query_one(
            "INSERT INTO etiquetas (empresa_id, nombre, color) VALUES (%s, %s, %s) RETURNING id",
            (empresa_id, nombre, color))
    except psycopg2.errors.UniqueViolation:
        raise Conflicto("Ya existe una etiqueta con ese nombre")
    return {"id": str(fila["id"]), "nombre": nombre, "color": color, "cfdis": 0}


def _etiqueta_o_404(empresa_id: str, etiqueta_id: str) -> dict:
    fila = db.query_one("SELECT id, nombre, color FROM etiquetas WHERE id = %s AND empresa_id = %s",
                        (etiqueta_id, empresa_id)) if es_uuid(etiqueta_id) else None
    if fila is None:
        raise NoEncontrado("Etiqueta no encontrada")
    return fila


def editar_etiqueta(empresa_id: str, etiqueta_id: str, nombre: Any = None, color: Any = None) -> dict:
    actual = _etiqueta_o_404(empresa_id, etiqueta_id)
    nuevo_nombre = _nombre_etiqueta(nombre) if nombre is not None else actual["nombre"]
    nuevo_color = _color(color) if color is not None else actual["color"]
    try:
        db.execute("UPDATE etiquetas SET nombre = %s, color = %s WHERE id = %s",
                   (nuevo_nombre, nuevo_color, etiqueta_id))
    except psycopg2.errors.UniqueViolation:
        raise Conflicto("Ya existe una etiqueta con ese nombre")
    return {"id": str(actual["id"]), "nombre": nuevo_nombre, "color": nuevo_color}


def borrar_etiqueta(empresa_id: str, etiqueta_id: str) -> dict:
    actual = _etiqueta_o_404(empresa_id, etiqueta_id)
    db.execute("DELETE FROM etiquetas WHERE id = %s AND empresa_id = %s", (etiqueta_id, empresa_id))
    return {"id": str(actual["id"]), "nombre": actual["nombre"]}


def etiquetar_lote(empresa_id: str, usuario_id: str, uuids: Any, agregar: Any, quitar: Any) -> dict:
    """Agrega o quita etiquetas a varios CFDI. Los UUID de otra empresa o inexistentes
    se ignoran sin avisar cuáles (no se filtra qué existe en otras empresas). Es
    idempotente: repetir la llamada no cambia el resultado."""
    uuids, agregar, quitar = (x if x is not None else [] for x in (uuids, agregar, quitar))
    if not all(isinstance(x, list) for x in (uuids, agregar, quitar)):
        raise Invalido("uuids, agregar y quitar deben ser listas")
    if not uuids or not (agregar or quitar):
        raise Invalido("Indica al menos un CFDI y una etiqueta por agregar o quitar")
    if len(uuids) > MAX_LOTE_CFDI:
        raise Excede(f"Un lote admite hasta {MAX_LOTE_CFDI} CFDI")
    if len(agregar) + len(quitar) > MAX_LOTE_ETIQUETAS:
        raise Excede(f"Un lote admite hasta {MAX_LOTE_ETIQUETAS} etiquetas")
    if not all(isinstance(u, str) and len(u) <= 36 for u in uuids):
        raise Invalido("uuids inválidos")
    agregar, quitar = list(dict.fromkeys(agregar)), list(dict.fromkeys(quitar))
    if set(agregar) & set(quitar):
        raise Invalido("Una etiqueta no puede agregarse y quitarse a la vez")
    for etiqueta_id in (*agregar, *quitar):
        _etiqueta_o_404(empresa_id, etiqueta_id)    # una etiqueta ajena es 404 para todo el lote

    ids = [str(f["id"]) for f in db.query_all(
        "SELECT id FROM cfdi WHERE empresa_id = %s AND uuid = ANY(%s)", (empresa_id, list(dict.fromkeys(uuids))))]
    agregados = quitados = 0
    with db.get_conn() as conn, conn.cursor() as cur:
        if ids and agregar:
            cur.execute(
                """
                INSERT INTO cfdi_etiquetas (cfdi_id, etiqueta_id, usuario_id)
                SELECT c, e, %s FROM unnest(%s::uuid[]) c CROSS JOIN unnest(%s::uuid[]) e
                ON CONFLICT DO NOTHING
                """, (usuario_id, ids, agregar))
            agregados = cur.rowcount
        if ids and quitar:
            cur.execute("DELETE FROM cfdi_etiquetas WHERE cfdi_id = ANY(%s::uuid[]) AND etiqueta_id = ANY(%s::uuid[])",
                        (ids, quitar))
            quitados = cur.rowcount
    return {"cfdis": len(ids), "agregados": agregados, "quitados": quitados}


# ---------------------------------------------------------------------------
# Comentarios
# ---------------------------------------------------------------------------

_SELECT_COMENTARIO = """
    SELECT k.id, k.texto, k.created_at, k.usuario_id, u.email AS autor
    FROM cfdi_comentarios k LEFT JOIN usuarios u ON u.id = k.usuario_id
"""


def _comentario(fila: dict, empresa_id: str, usuario_id: str) -> dict:
    return {"id": str(fila["id"]), "texto": fila["texto"], "creado": fila["created_at"].isoformat(),
            "autor": fila["autor"], "puede_borrar": _puede_borrar(empresa_id, usuario_id, fila["usuario_id"])}


def listar_comentarios(empresa_id: str, usuario_id: str, uuid: str) -> list[dict]:
    cfdi_id = _cfdi_id(empresa_id, uuid)
    filas = db.query_all(_SELECT_COMENTARIO + " WHERE k.cfdi_id = %s ORDER BY k.created_at, k.id", (cfdi_id,))
    return [_comentario(f, empresa_id, usuario_id) for f in filas]


def crear_comentario(empresa_id: str, usuario_id: str, uuid: str, texto: Any) -> dict:
    cfdi_id = _cfdi_id(empresa_id, uuid)
    if not isinstance(texto, str) or not texto.strip():
        raise Invalido("El comentario no puede estar vacío")
    texto = texto.strip()
    if len(texto) > MAX_COMENTARIO:
        raise Invalido(f"El comentario admite hasta {MAX_COMENTARIO} caracteres")
    fila = db.query_one(
        "INSERT INTO cfdi_comentarios (cfdi_id, empresa_id, usuario_id, texto) VALUES (%s, %s, %s, %s) RETURNING id",
        (cfdi_id, empresa_id, usuario_id, texto))
    return _comentario(db.query_one(_SELECT_COMENTARIO + " WHERE k.id = %s", (fila["id"],)), empresa_id, usuario_id)


def borrar_comentario(empresa_id: str, usuario_id: str, uuid: str, comentario_id: str) -> None:
    cfdi_id = _cfdi_id(empresa_id, uuid)
    fila = db.query_one("SELECT usuario_id FROM cfdi_comentarios WHERE id = %s AND cfdi_id = %s AND empresa_id = %s",
                        (comentario_id, cfdi_id, empresa_id)) if es_uuid(comentario_id) else None
    if fila is None:
        raise NoEncontrado("Comentario no encontrado")
    if not _puede_borrar(empresa_id, usuario_id, fila["usuario_id"]):
        raise SinPermiso("Solo quien lo escribió o un administrador puede borrarlo")
    db.execute("DELETE FROM cfdi_comentarios WHERE id = %s", (comentario_id,))


# ---------------------------------------------------------------------------
# Etiquetas de un CFDI (selector del visor)
# ---------------------------------------------------------------------------

def etiquetas_de(empresa_id: str, uuid: str) -> list[dict]:
    cfdi_id = _cfdi_id(empresa_id, uuid)
    filas = db.query_all(
        "SELECT e.id, e.nombre, e.color FROM cfdi_etiquetas ce JOIN etiquetas e ON e.id = ce.etiqueta_id "
        "WHERE ce.cfdi_id = %s ORDER BY lower(e.nombre)", (cfdi_id,))
    return [{"id": str(f["id"]), "nombre": f["nombre"], "color": f["color"]} for f in filas]


# ---------------------------------------------------------------------------
# Evidencias
# ---------------------------------------------------------------------------

# extensión → (tipo MIME que se guarda y se sirve, verificación por contenido). El tipo
# que declara el cliente y la extensión se ignoran para decidir: manda el contenido.
def _es_pdf(b: bytes) -> bool:
    return b.startswith(b"%PDF-")


def _es_png(b: bytes) -> bool:
    return b.startswith(b"\x89PNG\r\n\x1a\n")


def _es_jpeg(b: bytes) -> bool:
    return b.startswith(b"\xff\xd8\xff")


def _es_xlsx(b: bytes) -> bool:
    if not b.startswith(b"PK\x03\x04"):
        return False
    try:
        with zipfile.ZipFile(io.BytesIO(b)) as z:
            nombres = set(z.namelist())
    except zipfile.BadZipFile:
        return False
    return "[Content_Types].xml" in nombres and "xl/workbook.xml" in nombres


def _es_xml(b: bytes) -> bool:
    inicio = b.lstrip(b"\xef\xbb\xbf \t\r\n")[:64].lower()
    return inicio.startswith(b"<?xml") and b"\x00" not in b[:4096]


def _es_texto(b: bytes) -> bool:
    if b"\x00" in b:
        return False
    try:
        b.decode("utf-8")
    except UnicodeDecodeError:
        try:
            b.decode("cp1252")
        except UnicodeDecodeError:
            return False
    return True


TIPOS_EVIDENCIA = {
    "pdf": ("application/pdf", _es_pdf),
    "png": ("image/png", _es_png),
    "jpg": ("image/jpeg", _es_jpeg),
    "jpeg": ("image/jpeg", _es_jpeg),
    "xlsx": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", _es_xlsx),
    "xml": ("application/xml", _es_xml),
    "txt": ("text/plain", _es_texto),
    "csv": ("text/csv", _es_texto),
}


def nombre_seguro(nombre: Optional[str], extension: str) -> str:
    """Nombre sin carpetas, controles ni caracteres raros, con la extensión del tipo detectado."""
    base = re.split(r"[\\/]", nombre or "")[-1]
    base = base.rsplit(".", 1)[0] if "." in base else base
    base = re.sub(r"[^\w .()\-]", "_", base, flags=re.ASCII).strip(" ._") or "evidencia"
    base = re.sub(r"\s+", " ", base)[: MAX_NOMBRE_ARCHIVO - len(extension) - 1].rstrip(" ._") or "evidencia"
    return f"{base}.{extension}"


def validar_evidencia(nombre: Optional[str], contenido: bytes) -> tuple[str, str]:
    """(nombre saneado, tipo MIME). Lanza ``Invalido`` o ``Excede``."""
    if not contenido:
        raise Invalido("El archivo está vacío")
    if len(contenido) > MAX_EVIDENCIA_BYTES:
        raise Excede(f"El archivo excede el máximo de {MAX_EVIDENCIA_BYTES // (1024 * 1024)} MB")
    extension = (nombre or "").rsplit(".", 1)[-1].lower() if "." in (nombre or "") else ""
    tipo = TIPOS_EVIDENCIA.get(extension)
    if tipo is None:
        raise Invalido("Tipo de archivo no permitido; se aceptan: " + ", ".join(sorted(TIPOS_EVIDENCIA)))
    if not tipo[1](contenido):
        raise Invalido("El contenido del archivo no corresponde a su extensión")
    return nombre_seguro(nombre, extension), tipo[0]


def _evidencia(fila: dict, empresa_id: str, usuario_id: str) -> dict:
    return {"id": str(fila["id"]), "nombre": fila["nombre"], "tipo": fila["tipo_mime"], "tamano": fila["tamano"],
            "creado": fila["created_at"].isoformat(), "autor": fila["autor"],
            "puede_borrar": _puede_borrar(empresa_id, usuario_id, fila["usuario_id"])}


_SELECT_EVIDENCIA = """
    SELECT v.id, v.nombre, v.tipo_mime, v.tamano, v.created_at, v.usuario_id, u.email AS autor
    FROM cfdi_evidencias v LEFT JOIN usuarios u ON u.id = v.usuario_id
"""


def listar_evidencias(empresa_id: str, usuario_id: str, uuid: str) -> list[dict]:
    cfdi_id = _cfdi_id(empresa_id, uuid)
    filas = db.query_all(_SELECT_EVIDENCIA + " WHERE v.cfdi_id = %s ORDER BY v.created_at, v.id", (cfdi_id,))
    return [_evidencia(f, empresa_id, usuario_id) for f in filas]


def subir_evidencia(empresa_id: str, usuario_id: str, uuid: str, nombre: Optional[str], contenido: bytes) -> dict:
    cfdi_id = _cfdi_id(empresa_id, uuid)
    nombre, tipo = validar_evidencia(nombre, contenido)
    with db.get_conn() as conn, conn.cursor() as cur:
        # El tope por CFDI se comprueba bajo candado: dos subidas simultáneas no lo rebasan.
        cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (f"cfdi_evidencias:{cfdi_id}",))
        cur.execute("SELECT COUNT(*) FROM cfdi_evidencias WHERE cfdi_id = %s", (cfdi_id,))
        if cur.fetchone()[0] >= MAX_EVIDENCIAS_CFDI:
            raise Excede(f"Un CFDI admite hasta {MAX_EVIDENCIAS_CFDI} evidencias")
        cur.execute(
            """
            INSERT INTO cfdi_evidencias (cfdi_id, empresa_id, usuario_id, nombre, tipo_mime, tamano, sha256, contenido)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
            """,
            (cfdi_id, empresa_id, usuario_id, nombre, tipo, len(contenido),
             hashlib.sha256(contenido).hexdigest(), psycopg2.Binary(contenido)))
        nuevo = cur.fetchone()[0]
    return _evidencia(db.query_one(_SELECT_EVIDENCIA + " WHERE v.id = %s", (nuevo,)), empresa_id, usuario_id)


def _evidencia_o_404(empresa_id: str, uuid: str, evidencia_id: str) -> dict:
    cfdi_id = _cfdi_id(empresa_id, uuid)
    fila = db.query_one(
        "SELECT id, nombre, tipo_mime, usuario_id FROM cfdi_evidencias WHERE id = %s AND cfdi_id = %s AND empresa_id = %s",
        (evidencia_id, cfdi_id, empresa_id)) if es_uuid(evidencia_id) else None
    if fila is None:
        raise NoEncontrado("Evidencia no encontrada")
    return fila


def descargar_evidencia(empresa_id: str, uuid: str, evidencia_id: str) -> dict:
    meta = _evidencia_o_404(empresa_id, uuid, evidencia_id)
    fila = db.query_one("SELECT contenido FROM cfdi_evidencias WHERE id = %s", (evidencia_id,))
    return {"nombre": meta["nombre"], "tipo": meta["tipo_mime"], "contenido": bytes(fila["contenido"])}


def borrar_evidencia(empresa_id: str, usuario_id: str, uuid: str, evidencia_id: str) -> dict:
    meta = _evidencia_o_404(empresa_id, uuid, evidencia_id)
    if not _puede_borrar(empresa_id, usuario_id, meta["usuario_id"]):
        raise SinPermiso("Solo quien la subió o un administrador puede borrarla")
    db.execute("DELETE FROM cfdi_evidencias WHERE id = %s", (evidencia_id,))
    return {"id": str(meta["id"]), "nombre": meta["nombre"]}
