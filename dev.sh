#!/usr/bin/env bash
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

echo ""
echo " FiscalCore — Entorno de desarrollo"
echo " ===================================="
echo ""

BACKEND_PID=""
FRONTEND_PID=""
WORKER_PID=""
BACKEND_URL="http://localhost:8000/docs"
FRONTEND_URL="http://localhost:3000"

# Limpieza de procesos de backend, worker y frontend al salir
cleanup() {
  echo ""
  echo " Deteniendo procesos..."
  [ -n "$BACKEND_PID" ] && kill "$BACKEND_PID" 2>/dev/null || true
  [ -n "$WORKER_PID" ] && kill "$WORKER_PID" 2>/dev/null || true
  [ -n "$FRONTEND_PID" ] && kill "$FRONTEND_PID" 2>/dev/null || true
  wait 2>/dev/null || true
  exit 0
}
trap cleanup INT TERM

# ¿Hay algo escuchando ya en el puerto?
port_busy() {
  (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null
}

responde() {
  curl -s -o /dev/null --max-time 2 "$1"
}

PYTHON="${ROOT}/.venv/bin/python"
if [ ! -f "$PYTHON" ]; then
  echo " Creando virtualenv (Python 3.11)..."
  python3.11 -m venv "${ROOT}/.venv"
  "${ROOT}/.venv/bin/pip" install -r "${ROOT}/requirements.txt" -q
fi

echo "[1/4] Asegurando base de datos (docker compose db)..."
if port_busy 5432; then
  echo "       (PostgreSQL ya escucha en 5432)"
elif command -v docker &>/dev/null || command -v podman &>/dev/null || [ -r /var/run/docker.sock ]; then
  if DOCKER_ERR="$(docker compose up -d db 2>&1)"; then
    # Espera hasta 30s a que PostgreSQL acepte conexiones
    for _ in $(seq 1 30); do
      docker compose exec -T db pg_isready -U postgres &>/dev/null && break
      sleep 1
    done
  else
    echo "       AVISO: no se pudo levantar la DB — la API fallará al arrancar:"
    echo "       ${DOCKER_ERR##*$'\n'}"
  fi
else
  echo "       (docker no disponible — omitiendo DB local)"
fi

echo "[2/4] Creando/validando .env desde .env.example..."
if [ ! -f "${ROOT}/.env" ]; then
  cp "${ROOT}/.env.example" "${ROOT}/.env"
  # El JWT_SECRET de la plantilla es público: cada .env local lleva el suyo, aleatorio.
  JWT_LOCAL="$("$PYTHON" -c 'import secrets; print(secrets.token_urlsafe(64))')"
  sed "s|^JWT_SECRET=.*|JWT_SECRET=${JWT_LOCAL}|" "${ROOT}/.env" > "${ROOT}/.env.tmp" && mv "${ROOT}/.env.tmp" "${ROOT}/.env"
  echo "       .env creado desde .env.example (con un JWT_SECRET propio)"
fi

echo "[3/4] Iniciando backend (FastAPI puerto 8000)..."
if port_busy 8000; then
  echo "       (puerto 8000 ya en uso — se reutiliza el proceso existente)"
else
  "$PYTHON" -m uvicorn backend.main_api:app --reload --port 8000 &
  BACKEND_PID=$!
fi

# Worker de descarga automática del SAT (proceso aparte). Necesita FIEL_ENCRYPTION_KEY
# para leer las e.firmas guardadas; sin ella no se levanta.
if grep -qs '^FIEL_ENCRYPTION_KEY=.' "${ROOT}/.env" || [ -n "${FIEL_ENCRYPTION_KEY:-}" ]; then
  "$PYTHON" -m backend.worker &
  WORKER_PID=$!
  echo "       Worker de descarga automática iniciado"
else
  echo "       (worker de descarga automática omitido: define FIEL_ENCRYPTION_KEY en .env;"
  echo "        genérala con: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\")"
fi

echo "[4/4] Iniciando frontend (Next.js puerto 3000)..."
if [ ! -f "${ROOT}/frontend/package.json" ]; then
  echo "       (frontend/ no está en este checkout — omitiendo)"
elif ! command -v npm &>/dev/null; then
  echo "       (npm no disponible — omitiendo frontend)"
elif port_busy 3000; then
  echo "       (puerto 3000 ya en uso — se reutiliza el proceso existente)"
else
  if [ ! -d "${ROOT}/frontend/node_modules" ]; then
    echo "       Instalando dependencias (npm ci)..."
    (cd "${ROOT}/frontend" && npm ci --silent)
  fi
  if [ ! -f "${ROOT}/frontend/.env.local" ] && [ -f "${ROOT}/frontend/.env.local.example" ]; then
    cp "${ROOT}/frontend/.env.local.example" "${ROOT}/frontend/.env.local"
    echo "       frontend/.env.local creado desde .env.local.example"
  fi
  (cd "${ROOT}/frontend" && exec npm run dev -- --port 3000) &
  FRONTEND_PID=$!
fi

echo ""
echo " Esperando a que los servicios respondan..."
# Sondea ambos servicios a la vez, hasta 60s
PENDIENTE_BACKEND="$BACKEND_PID"
PENDIENTE_FRONTEND="$FRONTEND_PID"
for _ in $(seq 1 60); do
  if [ -n "$PENDIENTE_BACKEND" ] && responde "$BACKEND_URL"; then
    echo "   Backend:  $BACKEND_URL"
    PENDIENTE_BACKEND=""
  fi
  if [ -n "$PENDIENTE_FRONTEND" ] && responde "$FRONTEND_URL"; then
    echo "   Frontend: $FRONTEND_URL"
    PENDIENTE_FRONTEND=""
  fi
  [ -z "${PENDIENTE_BACKEND}${PENDIENTE_FRONTEND}" ] && break
  sleep 1
done
if [ -n "$PENDIENTE_BACKEND" ]; then
  echo "   Backend:  NO responde — revisa el log de uvicorn arriba"
fi
if [ -n "$PENDIENTE_FRONTEND" ]; then
  echo "   Frontend: NO responde — revisa el log de Next.js arriba"
fi
echo ""
echo " Ctrl+C para detener los procesos."
echo ""

wait
