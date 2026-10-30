@echo off
rem Agent Gen dev bring-up (M2): voice sidecar, speech sidecar, hub. Each in its own window.
rem PY310 = the interpreter that has torch + misaki 0.9.4 + faster-whisper (the lab's known-good is Python 3.10).
setlocal
cd /d "%~dp0.."
if "%PY310%"=="" set "PY310=C:\Program Files\Python310\python.exe"
if not exist "%PY310%" set "PY310=python"

start "agent-gen voice"  "%PY310%" sidecars\voice\server.py
start "agent-gen speech" "%PY310%" sidecars\speech\server.py --preload
if exist "sidecars\face\.venv\Scripts\python.exe" if exist "models\ditto\ditto_cfg" start "agent-gen face" "sidecars\face\.venv\Scripts\python.exe" sidecars\face\server.py
pushd hub
if not exist node_modules call npm install --no-audit --no-fund
start "agent-gen hub" node server.mjs
popd
timeout /t 3 >nul
start "" http://127.0.0.1:4646/
echo voice :5123  speech :5125  hub :4646  (close the three windows to stop)
endlocal
