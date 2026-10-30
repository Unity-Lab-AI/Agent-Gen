@echo off
REM launcher.bat -- U3E-2.199b. ONE DOUBLE-CLICK: switchboard up, page open.
REM
REM   Gee: "so the person can just open this one page and do everything".
REM   index.html opens over file:// and a file:// page cannot start a process,
REM   so something has to hold the shell. This starts that something and then
REM   opens the page, which finds it and grows on/off switches on every card.
REM
REM   It is idempotent: if the switchboard is already on :8799 it is NOT started
REM   twice, it just opens the page.

setlocal
cd /d "%~dp0"

netstat -ano -p TCP | findstr /C:"127.0.0.1:8799" | findstr /C:"LISTENING" >nul 2>&1
if %errorlevel%==0 (
  echo   switchboard already running on :8799
) else (
  echo   starting switchboard on 127.0.0.1:8799 ...
  start "U3E switchboard" /min cmd /c "node serve\launcher.mjs > .launcher.log 2>&1"
  REM give it a moment to bind before the page asks
  ping -n 3 127.0.0.1 >nul
)

echo   opening index.html
start "" "%~dp0index.html"
endlocal
