@echo off
echo.
echo  FiscalCore — Entorno de desarrollo
echo  ====================================
echo.

set ROOT=%~dp0

echo [1/1] Iniciando backend (FastAPI puerto 8000)...
start "FiscalCore - Backend" cmd /k "cd /d %ROOT% && python -m uvicorn backend.main_api:app --reload --port 8000"

echo.
echo  Listo. Abriendo navegador en 5 segundos...
echo    Backend:  http://localhost:8000/docs
echo.
timeout /t 5 /nobreak >nul
start "" "http://localhost:8000/docs"
