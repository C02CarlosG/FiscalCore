#!/usr/bin/env bash
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

echo ""
echo " FiscalCore — Entorno de desarrollo"
echo " ===================================="
echo ""

# Limpiar procesos al salir con Ctrl+C
cleanup() {
  echo ""
  echo " Deteniendo procesos..."
  kill "$BACKEND_PID" 2>/dev/null
  exit 0
}
trap cleanup INT TERM

PYTHON="${ROOT}/.venv/bin/python"
if [ ! -f "$PYTHON" ]; then
  echo " Creando virtualenv (Python 3.11)..."
  python3.11 -m venv "${ROOT}/.venv"
  "${ROOT}/.venv/bin/pip" install -r "${ROOT}/requirements.txt" -q
fi

echo "[1/1] Iniciando backend (FastAPI puerto 8000)..."
"$PYTHON" -m uvicorn backend.main_api:app --reload --port 8000 &
BACKEND_PID=$!

echo ""
echo " Listo:"
echo "   Backend:  http://localhost:8000/docs"
echo ""
echo " Ctrl+C para detener el proceso."
echo ""

wait
