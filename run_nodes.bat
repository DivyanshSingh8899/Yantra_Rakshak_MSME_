@echo off
REM ============================================================
REM  Yantra Rakshak - start the multi-node simulator fleet
REM  Run AFTER run_cloud.bat
REM  Usage: run_nodes.bat [cloud_url] [interval_seconds]
REM ============================================================
setlocal
set URL=http://127.0.0.1:8000
set INTERVAL=2
if not "%~1"=="" set URL=%~1
if not "%~2"=="" set INTERVAL=%~2

cd /d "%~dp0node"
pip install -q -r requirements.txt
python simulator.py --url %URL% --interval %INTERVAL%
endlocal
