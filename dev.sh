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
  kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null
  exit 0
}
trap cleanup INT TERM

echo "[1/2] Iniciando backend (FastAPI puerto 8000)..."
python -m uvicorn backend.main_api:app --reload --port 8000 &
BACKEND_PID=$!

sleep 2

echo "[2/2] Iniciando frontend (Vite puerto 3001)..."
npm run dev &
FRONTEND_PID=$!

echo ""
echo " Listo:"
echo "   Backend:  http://localhost:8000/docs"
echo "   Frontend: http://localhost:3001"
echo ""
echo " Ctrl+C para detener ambos procesos."
echo ""

wait
