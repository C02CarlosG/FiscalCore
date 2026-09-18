@echo off
setlocal

echo.
echo  FiscalCore — Entorno de desarrollo
echo  ====================================
echo.

set ROOT=%~dp0
cd /d "%ROOT%"

if not exist "%ROOT%.venv\Scripts\python.exe" (
    echo  Creando virtualenv ^(Python 3.11^)...
    py -3.11 -m venv "%ROOT%.venv"
    "%ROOT%.venv\Scripts\pip" install -r "%ROOT%requirements.txt" -q
)

echo [1/1] Iniciando backend (FastAPI puerto 8000)...
start "FiscalCore - Backend" cmd /k "cd /d %ROOT% && .venv\Scripts\python -m uvicorn backend.main_api:app --reload --port 8000"

echo.
echo  Listo. Abriendo navegador en 5 segundos...
echo    Backend:  http://localhost:8000/docs
echo.
timeout /t 5 /nobreak >nul
start "" "http://localhost:8000/docs"
