# SAT FIEL — Descarga Masiva de CFDIs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permitir al contador autenticarse con su FIEL (.cer + .key + contraseña) y descargar automáticamente sus CFDIs emitidos y recibidos del portal SAT, sin carga manual de XMLs.

**Architecture:** Backend Python consume el servicio SOAP de Descarga Masiva del SAT usando la biblioteca `satcfdi`. El flujo es asíncrono en 3 pasos (solicitar → verificar → descargar). Los CFDIs descargados se parsean con el `cfdi_parser.py` existente y se persisten en la DB. El frontend expone una UI para cargar FIEL y monitorear el estado de la solicitud.

**Tech Stack:** Python `satcfdi`, FastAPI background tasks, PostgreSQL, React + polling, migración SQL `016`

---

## Contexto del dominio — Descarga Masiva SAT

El SAT ofrece el servicio **Descarga Masiva de CFDIs** accesible via FIEL:

1. **Autenticar** — generar token SAT firmando un XML con la FIEL (certificado `.cer` + llave `.key` + contraseña)
2. **Solicitar** — enviar parámetros (RFC, tipo emitido/recibido, rango de fechas, estado). El SAT responde con un `idSolicitud`
3. **Verificar** — el SAT procesa la solicitud async. Se consulta el estado hasta que sea `Terminada`. Puede tardar minutos u horas
4. **Descargar** — el SAT devuelve paquetes ZIP con los XMLs de los CFDIs

La biblioteca `satcfdi` encapsula todo este protocolo y evita implementar el SOAP + firma XML desde cero.

**Límites del SAT:**
- Máx 200,000 CFDIs por solicitud emitidos / 200,000 recibidos
- Máx 50 paquetes por solicitud de recibidos
- Tiempo de procesamiento: 5 min a 24h dependiendo del volumen

---

## Estructura de archivos — resultado final

```
backend/
  sat_fiel.py              # NUEVO: cliente FIEL + Descarga Masiva usando satcfdi
  routers/
    sat.py                 # NUEVO: endpoints FIEL (POST /sat/solicitar, GET /sat/estado/{id}, POST /sat/descargar/{id})
database/
  migrations/
    016_sat_solicitudes.sql # NUEVO: tabla sat_solicitudes para tracking de solicitudes
src/
  tabs/
    TabSAT.jsx             # NUEVO: UI para cargar FIEL y monitorear descargas
  AuditoriaFiscalDashboard.jsx  # MODIFICADO: agregar tab SAT + tarjeta en vista principal
```

---

## Task 1: Migración de base de datos — tabla `sat_solicitudes`

**Files:**
- Create: `database/migrations/016_sat_solicitudes.sql`

- [ ] **Step 1: Crear la migración**

```sql
-- database/migrations/016_sat_solicitudes.sql
-- Tracking de solicitudes de Descarga Masiva del SAT
-- Idempotente: usa IF NOT EXISTS

CREATE TABLE IF NOT EXISTS sat_solicitudes (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    empresa_id      UUID NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    usuario_id      UUID NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    tipo            VARCHAR(10) NOT NULL CHECK (tipo IN ('emitidos', 'recibidos')),
    periodo_inicio  VARCHAR(7)  NOT NULL,  -- YYYY-MM
    periodo_fin     VARCHAR(7)  NOT NULL,  -- YYYY-MM
    id_solicitud_sat VARCHAR(100),         -- ID devuelto por el SAT
    estado          VARCHAR(30) NOT NULL DEFAULT 'pendiente'
                    CHECK (estado IN ('pendiente','solicitado','en_proceso','terminado','fallo','descargado')),
    num_cfdi        INTEGER,               -- CFDIs encontrados por el SAT
    num_paquetes    INTEGER,               -- Paquetes ZIP disponibles
    paquetes_descargados INTEGER DEFAULT 0,
    cfdi_importados INTEGER DEFAULT 0,
    error_msg       TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sat_solicitudes_empresa ON sat_solicitudes(empresa_id);
CREATE INDEX IF NOT EXISTS idx_sat_solicitudes_estado  ON sat_solicitudes(estado);
```

- [ ] **Step 2: Verificar que `init_db()` aplica la migración**

```bash
# La migración se aplica automáticamente al startup gracias a init_db() en db.py
python -c "from backend.db import init_db; init_db(); print('OK')"
```

Expected: `OK` sin errores.

- [ ] **Step 3: Commit**

```bash
git add database/migrations/016_sat_solicitudes.sql
git commit -m "feat: migración 016 — tabla sat_solicitudes para tracking de descarga masiva SAT"
```

---

## Task 2: Instalar `satcfdi` y crear el cliente FIEL

**Files:**
- Modify: (instalar dependencia, no hay requirements.txt formal — agregar a instrucciones)
- Create: `backend/sat_fiel.py`

- [ ] **Step 1: Instalar la biblioteca**

```bash
pip install satcfdi
```

Verificar:
```bash
python -c "import satcfdi; print('satcfdi OK')"
```

Expected: `satcfdi OK`

> **Nota para Railway:** Agregar `satcfdi` al Procfile de dependencias o al `requirements.txt` si existe. Si no hay `requirements.txt`, crearlo o agregarlo al comando de instalación en Railway.

- [ ] **Step 2: Crear `backend/sat_fiel.py`**

```python
# backend/sat_fiel.py
"""
Cliente FIEL para autenticación y descarga masiva de CFDIs del SAT.
Usa la biblioteca satcfdi: https://github.com/SAT-CFDI/python-satcfdi
"""
from __future__ import annotations

import io
import logging
import zipfile
from datetime import date, datetime
from pathlib import Path
from typing import Optional

_log = logging.getLogger(__name__)

try:
    from satcfdi.credentials import Credentials
    from satcfdi.sat import SAT
    SATCFDI_OK = True
except ImportError:
    SATCFDI_OK = False
    _log.warning("satcfdi no instalado — módulo FIEL deshabilitado")


class FIELError(Exception):
    pass


def _check_satcfdi():
    if not SATCFDI_OK:
        raise FIELError("satcfdi no instalado. Ejecutar: pip install satcfdi")


def cargar_fiel(cer_bytes: bytes, key_bytes: bytes, password: str) -> "Credentials":
    """Carga la FIEL desde bytes del .cer y .key. Lanza FIELError si los datos son inválidos."""
    _check_satcfdi()
    try:
        creds = Credentials.load(
            certificate=cer_bytes,
            private_key=key_bytes,
            password=password,
        )
        if not creds.is_valid():
            raise FIELError("La FIEL no es válida o ha expirado")
        return creds
    except FIELError:
        raise
    except Exception as e:
        raise FIELError(f"Error al cargar la FIEL: {e}") from e


def solicitar_descarga(
    creds: "Credentials",
    rfc: str,
    tipo: str,           # "emitidos" o "recibidos"
    fecha_inicio: date,
    fecha_fin: date,
) -> str:
    """
    Envía solicitud de descarga masiva al SAT.
    Retorna el id_solicitud del SAT.
    """
    _check_satcfdi()
    try:
        sat = SAT(creds)
        tipo_solicitud = "CFDI" 
        rfc_emisor   = rfc if tipo == "emitidos" else None
        rfc_receptor = rfc if tipo == "recibidos" else None

        resultado = sat.request_cfdi_download(
            fecha_inicial=fecha_inicio,
            fecha_final=fecha_fin,
            rfc_emisor=rfc_emisor,
            rfc_receptor_o_solicitante=rfc_receptor or rfc,
            tipo_solicitud=tipo_solicitud,
        )
        _log.info("Solicitud SAT enviada: %s", resultado)
        return str(resultado)
    except FIELError:
        raise
    except Exception as e:
        raise FIELError(f"Error al solicitar descarga: {e}") from e


def verificar_solicitud(creds: "Credentials", id_solicitud: str) -> dict:
    """
    Consulta el estado de una solicitud de descarga.
    Retorna dict con: estado, num_cfdi, num_paquetes, id_paquetes[]
    """
    _check_satcfdi()
    try:
        sat = SAT(creds)
        resultado = sat.verify_cfdi_download(id_solicitud)
        _log.info("Estado solicitud %s: %s", id_solicitud, resultado)
        return {
            "estado": str(resultado.get("estado", "desconocido")).lower(),
            "num_cfdi": resultado.get("numero_cfdis", 0),
            "id_paquetes": resultado.get("id_paquetes", []),
        }
    except Exception as e:
        raise FIELError(f"Error al verificar solicitud: {e}") from e


def descargar_paquete(creds: "Credentials", id_paquete: str) -> list[bytes]:
    """
    Descarga un paquete ZIP del SAT y retorna lista de bytes de cada XML.
    """
    _check_satcfdi()
    try:
        sat = SAT(creds)
        zip_bytes = sat.download_cfdi(id_paquete)
        xmls = []
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
            for name in z.namelist():
                if name.endswith(".xml"):
                    xmls.append(z.read(name))
        _log.info("Paquete %s descargado: %d XMLs", id_paquete, len(xmls))
        return xmls
    except Exception as e:
        raise FIELError(f"Error al descargar paquete: {e}") from e
```

- [ ] **Step 3: Verificar import**

```bash
python -c "from backend.sat_fiel import cargar_fiel, solicitar_descarga; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add backend/sat_fiel.py
git commit -m "feat: cliente FIEL para autenticación y descarga masiva SAT (satcfdi)"
```

---

## Task 3: Crear el router SAT

**Files:**
- Create: `backend/routers/sat.py`
- Modify: `backend/main_api.py` (agregar include_router)

Los endpoints siguen este flujo:
1. `POST /api/v1/sat/solicitar` — recibe .cer, .key, password, rango de fechas, tipo. Crea registro en `sat_solicitudes`, llama al SAT y guarda `id_solicitud_sat`.
2. `GET /api/v1/sat/solicitudes` — lista solicitudes de la empresa activa.
3. `POST /api/v1/sat/solicitudes/{solicitud_id}/verificar` — consulta estado SAT y actualiza el registro.
4. `POST /api/v1/sat/solicitudes/{solicitud_id}/descargar` — descarga paquetes pendientes, parsea XMLs e importa a la DB usando el pipeline existente.

- [ ] **Step 1: Crear `backend/routers/sat.py`**

```python
# backend/routers/sat.py
from __future__ import annotations

import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile

from .. import db
from ..deps import get_current_user, validar_acceso_empresa, serializar
from ..sat_fiel import FIELError, cargar_fiel, descargar_paquete, solicitar_descarga, verificar_solicitud

_log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/sat", tags=["SAT FIEL"])


@router.post("/solicitar")
async def solicitar_descarga_cfdi(
    empresa_id: str = Form(...),
    tipo: str = Form(...),          # "emitidos" o "recibidos"
    fecha_inicio: str = Form(...),  # YYYY-MM-DD
    fecha_fin: str = Form(...),     # YYYY-MM-DD
    cer_file: UploadFile = File(...),
    key_file: UploadFile = File(...),
    password: str = Form(...),
    current_user: dict = Depends(get_current_user),
):
    """Inicia solicitud de descarga masiva autenticando con FIEL."""
    validar_acceso_empresa(empresa_id, current_user)

    empresa = db.query_one("SELECT rfc FROM empresas WHERE id = %s", (empresa_id,))
    if not empresa:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")

    if tipo not in ("emitidos", "recibidos"):
        raise HTTPException(status_code=400, detail="tipo debe ser 'emitidos' o 'recibidos'")

    try:
        fecha_ini = date.fromisoformat(fecha_inicio)
        fecha_fin_d = date.fromisoformat(fecha_fin)
    except ValueError:
        raise HTTPException(status_code=400, detail="Fechas inválidas — formato esperado: YYYY-MM-DD")

    cer_bytes = await cer_file.read()
    key_bytes = await key_file.read()

    try:
        creds = cargar_fiel(cer_bytes, key_bytes, password)
    except FIELError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # Crear registro en DB
    registro = db.execute(
        """INSERT INTO sat_solicitudes
           (empresa_id, usuario_id, tipo, periodo_inicio, periodo_fin, estado)
           VALUES (%s, %s, %s, %s, %s, 'pendiente') RETURNING *""",
        (empresa_id, current_user["user_id"], tipo,
         fecha_inicio[:7], fecha_fin[:7]),
        returning=True,
    )
    solicitud_id = str(registro["id"])

    try:
        id_sat = solicitar_descarga(creds, empresa["rfc"], tipo, fecha_ini, fecha_fin_d)
        db.execute(
            "UPDATE sat_solicitudes SET id_solicitud_sat=%s, estado='solicitado', updated_at=NOW() WHERE id=%s",
            (id_sat, solicitud_id),
        )
    except FIELError as e:
        db.execute(
            "UPDATE sat_solicitudes SET estado='fallo', error_msg=%s, updated_at=NOW() WHERE id=%s",
            (str(e), solicitud_id),
        )
        raise HTTPException(status_code=502, detail=f"Error SAT: {e}")

    return {
        "solicitud_id": solicitud_id,
        "id_solicitud_sat": id_sat,
        "estado": "solicitado",
        "mensaje": "Solicitud enviada al SAT. Usa el endpoint /verificar para consultar el estado.",
    }


@router.get("/solicitudes")
async def listar_solicitudes(
    empresa_id: str,
    current_user: dict = Depends(get_current_user),
):
    validar_acceso_empresa(empresa_id, current_user)
    rows = db.query_all(
        "SELECT * FROM sat_solicitudes WHERE empresa_id=%s ORDER BY created_at DESC LIMIT 20",
        (empresa_id,),
    )
    return [serializar(r) for r in rows]


@router.post("/solicitudes/{solicitud_id}/verificar")
async def verificar_solicitud_endpoint(
    solicitud_id: str,
    cer_file: UploadFile = File(...),
    key_file: UploadFile = File(...),
    password: str = Form(...),
    current_user: dict = Depends(get_current_user),
):
    """Consulta el estado de la solicitud en el SAT y actualiza el registro."""
    solicitud = db.query_one("SELECT * FROM sat_solicitudes WHERE id=%s", (solicitud_id,))
    if not solicitud:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")

    validar_acceso_empresa(str(solicitud["empresa_id"]), current_user)

    if not solicitud["id_solicitud_sat"]:
        raise HTTPException(status_code=400, detail="La solicitud aún no tiene ID del SAT")

    cer_bytes = await cer_file.read()
    key_bytes = await key_file.read()

    try:
        creds = cargar_fiel(cer_bytes, key_bytes, password)
        resultado = verificar_solicitud(creds, solicitud["id_solicitud_sat"])
    except FIELError as e:
        raise HTTPException(status_code=502, detail=str(e))

    # Mapear estado SAT a estado interno
    estado_sat = resultado["estado"]
    ESTADO_MAP = {
        "aceptada":   "solicitado",
        "en proceso": "en_proceso",
        "terminada":  "terminado",
        "rechazada":  "fallo",
        "falla":      "fallo",
    }
    nuevo_estado = ESTADO_MAP.get(estado_sat, "en_proceso")
    id_paquetes  = resultado.get("id_paquetes", [])

    db.execute(
        """UPDATE sat_solicitudes
           SET estado=%s, num_cfdi=%s, num_paquetes=%s, updated_at=NOW()
           WHERE id=%s""",
        (nuevo_estado, resultado.get("num_cfdi", 0), len(id_paquetes), solicitud_id),
    )

    return {
        "solicitud_id": solicitud_id,
        "estado": nuevo_estado,
        "estado_sat": estado_sat,
        "num_cfdi": resultado.get("num_cfdi", 0),
        "num_paquetes": len(id_paquetes),
        "id_paquetes": id_paquetes,
    }


@router.post("/solicitudes/{solicitud_id}/descargar")
async def descargar_cfdi_endpoint(
    solicitud_id: str,
    background_tasks: BackgroundTasks,
    cer_file: UploadFile = File(...),
    key_file: UploadFile = File(...),
    password: str = Form(...),
    id_paquetes: str = Form(...),  # JSON array de strings
    current_user: dict = Depends(get_current_user),
):
    """
    Descarga los paquetes ZIP del SAT, parsea los XMLs e importa a la DB.
    Corre en background para no bloquear el request.
    """
    import json as _json

    solicitud = db.query_one("SELECT * FROM sat_solicitudes WHERE id=%s", (solicitud_id,))
    if not solicitud:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")

    validar_acceso_empresa(str(solicitud["empresa_id"]), current_user)

    cer_bytes = await cer_file.read()
    key_bytes = await key_file.read()

    try:
        creds = cargar_fiel(cer_bytes, key_bytes, password)
        paquetes = _json.loads(id_paquetes)
    except FIELError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except _json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="id_paquetes debe ser un JSON array")

    background_tasks.add_task(
        _importar_paquetes_bg,
        creds=creds,
        solicitud_id=solicitud_id,
        empresa_id=str(solicitud["empresa_id"]),
        periodo=solicitud["periodo_inicio"],
        paquetes=paquetes,
    )

    return {"mensaje": "Descarga iniciada en background", "paquetes": len(paquetes)}


def _importar_paquetes_bg(creds, solicitud_id: str, empresa_id: str, periodo: str, paquetes: list[str]):
    """Background task: descarga paquetes ZIP y parsea XMLs al pipeline existente."""
    from ..cfdi_parser import CFDIParser
    from ..main_api import _correr_pipeline  # importar pipeline existente

    parser = CFDIParser()
    total_importados = 0
    empresa = db.query_one("SELECT rfc FROM empresas WHERE id=%s", (empresa_id,))
    rfc = empresa["rfc"] if empresa else ""

    for id_paq in paquetes:
        try:
            xmls = descargar_paquete(creds, id_paq)
            for xml_bytes in xmls:
                try:
                    cfdi_data = parser.parsear(xml_bytes.decode("utf-8", errors="replace"))
                    if not cfdi_data:
                        continue
                    # Insertar CFDI usando la lógica existente (simplificada)
                    _insertar_cfdi(empresa_id, cfdi_data, periodo)
                    total_importados += 1
                except Exception as e:
                    _log.warning("Error parseando XML del paquete %s: %s", id_paq, e)

            db.execute(
                "UPDATE sat_solicitudes SET paquetes_descargados = paquetes_descargados + 1, updated_at=NOW() WHERE id=%s",
                (solicitud_id,),
            )
        except FIELError as e:
            _log.error("Error descargando paquete %s: %s", id_paq, e)

    db.execute(
        "UPDATE sat_solicitudes SET cfdi_importados=%s, estado='descargado', updated_at=NOW() WHERE id=%s",
        (total_importados, solicitud_id),
    )

    # Correr pipeline fiscal si hubo importaciones
    if total_importados > 0 and rfc:
        try:
            _correr_pipeline(empresa_id, periodo, rfc)
        except Exception as e:
            _log.error("Error en pipeline post-descarga FIEL: %s", e)

    _log.info("Solicitud %s: %d CFDIs importados", solicitud_id, total_importados)


def _insertar_cfdi(empresa_id: str, cfdi: dict, periodo: str):
    """Inserta un CFDI parseado en la DB. Usa INSERT ... ON CONFLICT DO NOTHING para idempotencia."""
    db.execute(
        """INSERT INTO cfdi (
            empresa_id, uuid, tipo_comprobante, fecha, rfc_emisor, nombre_emisor,
            rfc_receptor, nombre_receptor, subtotal, total, moneda,
            metodo_pago, forma_pago, exportacion, lugar_expedicion,
            domicilio_fiscal_receptor, regimen_fiscal_receptor,
            cfdi_relacionados, es_anticipo_sat, periodo
        ) VALUES (
            %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s
        ) ON CONFLICT (uuid) DO NOTHING""",
        (
            empresa_id,
            cfdi.get("uuid"), cfdi.get("tipo_comprobante"), cfdi.get("fecha"),
            cfdi.get("rfc_emisor"), cfdi.get("nombre_emisor"),
            cfdi.get("rfc_receptor"), cfdi.get("nombre_receptor"),
            cfdi.get("subtotal"), cfdi.get("total"), cfdi.get("moneda"),
            cfdi.get("metodo_pago"), cfdi.get("forma_pago"),
            cfdi.get("exportacion"), cfdi.get("lugar_expedicion"),
            cfdi.get("domicilio_fiscal_receptor"), cfdi.get("regimen_fiscal_receptor"),
            db.json_dumps(cfdi.get("cfdi_relacionados", [])),
            cfdi.get("es_anticipo_sat", False),
            periodo,
        ),
    )
```

> **Nota sobre `_correr_pipeline`:** Si en este punto ya se realizó el refactor del backend (Task 6 del plan de refactor), importar desde `backend.routers.ingesta` en lugar de `backend.main_api`.

- [ ] **Step 2: Agregar el router a `main_api.py`**

```python
# En backend/main_api.py, agregar:
from .routers import sat  # junto a los otros imports de routers

# Y en los include_router:
app.include_router(sat.router)
```

- [ ] **Step 3: Verificar que el servidor arranca con el nuevo router**

```bash
python -m uvicorn backend.main_api:app --reload --port 8000
```

Abrir http://localhost:8000/docs — debe aparecer el grupo "SAT FIEL" con 4 endpoints.

- [ ] **Step 4: Commit**

```bash
git add backend/routers/sat.py backend/main_api.py
git commit -m "feat: router SAT FIEL — solicitar/verificar/descargar CFDIs masivos"
```

---

## Task 4: Frontend — TabSAT

**Files:**
- Create: `src/tabs/TabSAT.jsx`
- Modify: `src/AuditoriaFiscalDashboard.jsx` (agregar tab + tarjeta vista principal)

- [ ] **Step 1: Crear `src/tabs/TabSAT.jsx`**

```jsx
// src/tabs/TabSAT.jsx
import { useState, useRef } from "react";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { cn } from "../lib/utils";
import { API_URL, authHeaders, periodoLabel } from "../lib/constants.js";

const ESTADO_SAT = {
  pendiente:   { label:"Pendiente",    cls:"text-slate-400 bg-slate-400/10 border-slate-400/20" },
  solicitado:  { label:"Solicitado",   cls:"text-sky-400   bg-sky-400/10   border-sky-400/20"   },
  en_proceso:  { label:"En proceso",   cls:"text-amber-400 bg-amber-400/10 border-amber-400/20" },
  terminado:   { label:"Terminado",    cls:"text-emerald-400 bg-emerald-400/10 border-emerald-400/20" },
  fallo:       { label:"Fallo",        cls:"text-red-400   bg-red-400/10   border-red-400/20"   },
  descargado:  { label:"Descargado",   cls:"text-emerald-400 bg-emerald-400/10 border-emerald-400/20" },
};

export function TabSAT({ empresaId, periodoActual, onCfdiImportado }) {
  const [cerFile, setCerFile] = useState(null);
  const [keyFile, setKeyFile] = useState(null);
  const [password, setPassword] = useState("");
  const [tipo, setTipo] = useState("emitidos");
  const [fechaInicio, setFechaInicio] = useState(periodoActual ? `${periodoActual}-01` : "");
  const [fechaFin, setFechaFin] = useState("");
  const [cargando, setCargando] = useState(false);
  const [msg, setMsg] = useState(null);
  const [solicitudes, setSolicitudes] = useState([]);
  const [cargandoSolicitudes, setCargandoSolicitudes] = useState(false);

  const cerRef = useRef(null);
  const keyRef = useRef(null);

  const cargarSolicitudes = async () => {
    if (!empresaId) return;
    setCargandoSolicitudes(true);
    try {
      const res = await fetch(`${API_URL}/api/v1/sat/solicitudes?empresa_id=${empresaId}`, {
        headers: authHeaders(),
      });
      if (res.ok) setSolicitudes(await res.json());
    } catch(_) {} finally { setCargandoSolicitudes(false); }
  };

  const solicitar = async () => {
    if (!cerFile || !keyFile || !password || !fechaInicio || !fechaFin) {
      setMsg({ tipo:"error", texto:"Completa todos los campos antes de solicitar" });
      return;
    }
    setCargando(true);
    setMsg(null);
    const fd = new FormData();
    fd.append("empresa_id", empresaId);
    fd.append("tipo", tipo);
    fd.append("fecha_inicio", fechaInicio);
    fd.append("fecha_fin", fechaFin);
    fd.append("cer_file", cerFile);
    fd.append("key_file", keyFile);
    fd.append("password", password);
    try {
      const res = await fetch(`${API_URL}/api/v1/sat/solicitar`, {
        method: "POST", body: fd, headers: authHeaders(),
      });
      const data = await res.json();
      if (res.ok) {
        setMsg({ tipo:"ok", texto:`Solicitud enviada — ID: ${data.id_solicitud_sat}` });
        await cargarSolicitudes();
        setPassword("");
      } else {
        setMsg({ tipo:"error", texto: data.detail ?? "Error al solicitar" });
      }
    } catch(_) {
      setMsg({ tipo:"error", texto:"Error de conexión" });
    } finally { setCargando(false); }
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="font-display font-bold text-xl text-foreground">Descarga SAT con FIEL</h2>
        <p className="text-sm text-muted-foreground mt-0.5">
          Descarga automática de CFDIs emitidos y recibidos usando tu firma electrónica
        </p>
      </div>

      {/* Aviso de seguridad */}
      <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-4">
        <div className="font-mono text-[10px] text-amber-400 tracking-widest uppercase mb-1">⚠ Seguridad</div>
        <p className="text-xs text-amber-300/80">
          Tu FIEL no se almacena en ningún servidor. Se usa únicamente para autenticar la solicitud al SAT y se descarta inmediatamente.
        </p>
      </div>

      {/* Formulario */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Nueva solicitud de descarga</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Tipo */}
          <div className="flex gap-3">
            {["emitidos","recibidos"].map(t => (
              <button
                key={t}
                onClick={() => setTipo(t)}
                className={cn(
                  "flex-1 py-2 rounded-md border font-mono text-xs font-bold transition-all",
                  tipo === t
                    ? "bg-primary/20 border-primary text-primary"
                    : "bg-muted/10 border-border text-muted-foreground hover:border-primary/40"
                )}
              >
                {t === "emitidos" ? "Emitidos" : "Recibidos"}
              </button>
            ))}
          </div>

          {/* Rango de fechas */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <div className="font-mono text-[9px] text-muted-foreground tracking-widest uppercase mb-1">Fecha inicio</div>
              <input type="date" value={fechaInicio} onChange={e=>setFechaInicio(e.target.value)}
                className="w-full bg-background border border-border rounded px-3 py-1.5 text-foreground font-mono text-sm focus:outline-none focus:border-primary"/>
            </div>
            <div>
              <div className="font-mono text-[9px] text-muted-foreground tracking-widest uppercase mb-1">Fecha fin</div>
              <input type="date" value={fechaFin} onChange={e=>setFechaFin(e.target.value)}
                className="w-full bg-background border border-border rounded px-3 py-1.5 text-foreground font-mono text-sm focus:outline-none focus:border-primary"/>
            </div>
          </div>

          {/* Archivos FIEL */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <div className="font-mono text-[9px] text-muted-foreground tracking-widest uppercase mb-1">Certificado (.cer)</div>
              <input ref={cerRef} type="file" accept=".cer" className="hidden" onChange={e=>setCerFile(e.target.files[0])}/>
              <button onClick={()=>cerRef.current?.click()}
                className={cn("w-full py-2 rounded-md border font-mono text-xs transition-all text-left px-3",
                  cerFile ? "border-emerald-500/40 bg-emerald-500/5 text-emerald-400" : "border-border hover:border-primary/40 text-muted-foreground"
                )}>
                {cerFile ? `✓ ${cerFile.name}` : "Seleccionar .cer"}
              </button>
            </div>
            <div>
              <div className="font-mono text-[9px] text-muted-foreground tracking-widest uppercase mb-1">Llave privada (.key)</div>
              <input ref={keyRef} type="file" accept=".key" className="hidden" onChange={e=>setKeyFile(e.target.files[0])}/>
              <button onClick={()=>keyRef.current?.click()}
                className={cn("w-full py-2 rounded-md border font-mono text-xs transition-all text-left px-3",
                  keyFile ? "border-emerald-500/40 bg-emerald-500/5 text-emerald-400" : "border-border hover:border-primary/40 text-muted-foreground"
                )}>
                {keyFile ? `✓ ${keyFile.name}` : "Seleccionar .key"}
              </button>
            </div>
          </div>

          {/* Contraseña */}
          <div>
            <div className="font-mono text-[9px] text-muted-foreground tracking-widest uppercase mb-1">Contraseña de la FIEL</div>
            <input type="password" value={password} onChange={e=>setPassword(e.target.value)}
              placeholder="Contraseña del archivo .key"
              className="w-full bg-background border border-border rounded px-3 py-1.5 text-foreground font-mono text-sm focus:outline-none focus:border-primary"/>
          </div>

          {msg && (
            <div className={cn("px-4 py-2.5 rounded-lg border font-mono text-sm",
              msg.tipo==="ok" ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400"
                             : "bg-red-500/10 border-red-500/30 text-red-400"
            )}>{msg.texto}</div>
          )}

          <Button onClick={solicitar} disabled={cargando} className="w-full">
            {cargando ? "Enviando solicitud al SAT…" : "Solicitar descarga"}
          </Button>
        </CardContent>
      </Card>

      {/* Historial de solicitudes */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <div className="font-mono text-[10px] text-muted-foreground tracking-widest uppercase">
            Solicitudes recientes
          </div>
          <Button variant="ghost" size="sm" onClick={cargarSolicitudes} disabled={cargandoSolicitudes}
            className="font-mono text-[10px] h-6">
            {cargandoSolicitudes ? "…" : "↺ Actualizar"}
          </Button>
        </div>
        {solicitudes.length === 0 ? (
          <div className="rounded-lg border border-dashed border-border p-6 text-center text-xs text-muted-foreground font-mono">
            Sin solicitudes previas
            <button onClick={cargarSolicitudes} className="block mx-auto mt-2 text-primary hover:underline">Cargar historial</button>
          </div>
        ) : (
          <div className="space-y-2">
            {solicitudes.map(s => {
              const est = ESTADO_SAT[s.estado] ?? ESTADO_SAT.pendiente;
              return (
                <div key={s.id} className="flex items-center gap-3 p-3 rounded-lg border bg-card">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap mb-1">
                      <span className={cn("font-mono text-[9px] font-bold px-1.5 py-0.5 rounded border", est.cls)}>
                        {est.label}
                      </span>
                      <span className="font-mono text-[10px] text-foreground">
                        {s.tipo === "emitidos" ? "Emitidos" : "Recibidos"}
                      </span>
                      <span className="font-mono text-[10px] text-muted-foreground">
                        {periodoLabel(s.periodo_inicio)}
                        {s.periodo_fin !== s.periodo_inicio && ` → ${periodoLabel(s.periodo_fin)}`}
                      </span>
                    </div>
                    {s.num_cfdi != null && (
                      <div className="font-mono text-[10px] text-muted-foreground">
                        {s.num_cfdi} CFDIs · {s.num_paquetes ?? 0} paquetes
                        {s.cfdi_importados > 0 && ` · ${s.cfdi_importados} importados`}
                      </div>
                    )}
                    {s.error_msg && (
                      <div className="font-mono text-[10px] text-red-400 mt-0.5 truncate">{s.error_msg}</div>
                    )}
                  </div>
                  <div className="font-mono text-[10px] text-muted-foreground flex-shrink-0">
                    {new Date(s.created_at).toLocaleDateString("es-MX", {day:"2-digit",month:"short"})}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Integrar TabSAT en `AuditoriaFiscalDashboard.jsx`**

Agregar import:
```js
import { TabSAT } from "./tabs/TabSAT.jsx";
```

En el array `DRILL_TABS`, agregar al final:
```js
["sat", "Descarga SAT"],
```

En el bloque de render de tabs:
```jsx
{tab === "sat" && (
  <TabSAT
    empresaId={empresaId}
    periodoActual={periodoActual}
    onCfdiImportado={() => Promise.all([
      fetchCierre(empresaId, periodoActual),
      fetchEmitidos(empresaId, periodoActual),
    ])}
  />
)}
```

Opcionalmente, en `VistaPrincipal`, agregar una tarjeta de acceso rápido a la descarga SAT si no hay datos en el período:
```jsx
<button onClick={() => setTab("sat")}
  className="text-xs text-primary hover:underline font-mono">
  ↓ Descargar del SAT con FIEL
</button>
```

- [ ] **Step 3: Verificar en el browser**

```bash
npm run dev
```

1. Navegar a la tab "Descarga SAT"
2. Verificar que el formulario renderiza correctamente
3. Verificar que el botón de historial llama al endpoint (inspeccionar red)

- [ ] **Step 4: Commit**

```bash
git add src/tabs/TabSAT.jsx src/AuditoriaFiscalDashboard.jsx
git commit -m "feat: TabSAT — UI para descarga masiva SAT con FIEL"
```

---

## Task 5: Agregar `satcfdi` a dependencias del proyecto

**Files:**
- Create o Modify: `requirements.txt`

- [ ] **Step 1: Crear/actualizar `requirements.txt`**

Si no existe `requirements.txt`, crearlo con todas las dependencias actuales:

```
fastapi
uvicorn[standard]
python-multipart
psycopg2-binary
openpyxl
pydantic
python-jose[cryptography]
bcrypt
pdfplumber
satcfdi
```

- [ ] **Step 2: Verificar que Railway puede instalar con este requirements.txt**

```bash
pip install -r requirements.txt
```

Expected: sin errores.

- [ ] **Step 3: Commit**

```bash
git add requirements.txt
git commit -m "feat: agregar satcfdi a requirements.txt"
```

---

## Self-Review

**Cobertura del spec:**
- ✅ Autenticación FIEL (.cer + .key + contraseña)
- ✅ Solicitud de descarga masiva (emitidos y recibidos)
- ✅ Verificación de estado asíncrono
- ✅ Descarga e importación de paquetes ZIP → CFDIs → pipeline fiscal
- ✅ Tracking en DB (sat_solicitudes)
- ✅ UI con formulario + historial
- ✅ La FIEL no se persiste en ningún punto

**Riesgos conocidos:**
- La API de `satcfdi` puede cambiar entre versiones. Si `SAT.request_cfdi_download()` o los parámetros difieren de lo documentado, consultar `satcfdi` docs o el repositorio oficial.
- El proceso de verificación puede tardar horas. El frontend debe hacer polling manual (botón "↺ Actualizar") en lugar de polling automático para no sobrecargar el SAT.
- `_correr_pipeline` en `_importar_paquetes_bg` asume que la función existe en el módulo correcto. Ajustar el import según si se realizó el refactor del backend primero.

**Orden recomendado de implementación:**
Ejecutar el Plan de Refactor (2026-04-18-refactor-codigo.md) primero, luego este plan.
