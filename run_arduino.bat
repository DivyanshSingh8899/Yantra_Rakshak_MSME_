@echo off
REM ============================================================
REM  Yantra Rakshak - Arduino USB bridge
REM  Reads JSON from the Arduino UNO Q over USB Serial and
REM  forwards to the cloud dashboard.
REM
REM  Usage:
REM    run_arduino.bat              (auto-detect COM port)
REM    run_arduino.bat COM3         (specify port)
REM    run_arduino.bat COM3 8010    (specify port + cloud port)
REM  Cloud port here MUST match the port run_cloud.bat is using (8000
REM  by default) or the bridge will silently fail to reach the cloud.
REM ============================================================
setlocal
set COMPORT=
set CLOUDPORT=8000
if not "%~1"=="" set COMPORT=--port %~1
if not "%~2"=="" set CLOUDPORT=%~2

cd /d "%~dp0node"
pip install -q -r requirements.txt

echo.
echo ============================================================
echo   YANTRA RAKSHAK - Arduino Bridge
echo   Make sure run_cloud.bat is already running!
echo ============================================================
python arduino_bridge.py %COMPORT% --url http://127.0.0.1:%CLOUDPORT%
endlocal
