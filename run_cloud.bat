@echo off
REM ============================================================
REM  Yantra Rakshak - start the Cloud (laptop) service
REM  Dashboard: http://localhost:8000
REM ============================================================
setlocal
set PORT=8000
if not "%~1"=="" set PORT=%~1

cd /d "%~dp0backend"
pip install -q -r requirements.txt
echo.
echo  YANTRA RAKSHAK CLOUD  ^|  http://localhost:%PORT%
echo.
python -m uvicorn main:app --host 0.0.0.0 --port %PORT%
endlocal
