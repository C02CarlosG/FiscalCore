@echo off
echo.
echo  FiscalCore — Entorno de desarrollo
echo  ====================================
echo.

set ROOT=%~dp0

echo [1/2] Iniciando backend (FastAPI puerto 8000)...
start "FiscalCore - Backend" cmd /k "cd /d %ROOT% && python -m uvicorn backend.main_api:app --reload --port 8000"

echo [2/2] Iniciando frontend (Vite puerto 3001)...
timeout /t 2 /nobreak >nul
start "FiscalCore - Frontend" cmd /k "cd /d %ROOT% && npm run dev"

echo.
echo  Listo. Abriendo navegador en 5 segundos...
echo    Backend:  http://localhost:8000/docs
echo    Frontend: http://localhost:3001
echo.
timeout /t 5 /nobreak >nul
start "" "http://localhost:3001"
