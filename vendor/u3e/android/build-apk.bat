@echo off
REM build-apk.bat - build the U3E Android app on Windows.
REM
REM Reuses the sibling projects android-toolchain rather than installing a
REM second 1.5GB copy. A BUILD-TIME tool dependency, not a runtime one -
REM nothing from that project ends up inside this APK.
REM
REM CRLF line endings are REQUIRED: an LF-only .bat breaks `goto` with
REM "cannot find the batch label specified". That cost a real debugging
REM session in the sibling project.
setlocal
cd /d "%~dp0"
set "HERE=%CD%"
for %%I in ("%HERE%\..\..") do set "SIBLING=%%~fI\android-toolchain"

echo.
echo   U3E - BUILD THE ANDROID APP (.apk)
echo   ==================================================

if not defined ANDROID_HOME if exist "%SIBLING%\sdk" set "ANDROID_HOME=%SIBLING%\sdk"
if not defined JAVA_HOME  if exist "%SIBLING%\jdk" set "JAVA_HOME=%SIBLING%\jdk"
set "GRADLE_BIN=%SIBLING%\gradle\bin\gradle.bat"
if not exist "%GRADLE_BIN%" set "GRADLE_BIN=gradle"

if not defined ANDROID_HOME goto :notoolchain
if not exist "%ANDROID_HOME%" goto :notoolchain

set "ANDROID_SDK_ROOT=%ANDROID_HOME%"
echo   java   : %JAVA_HOME%
echo   sdk    : %ANDROID_HOME%
echo   gradle : %GRADLE_BIN%
echo.
echo   [*] building...
call "%GRADLE_BIN%" --project-dir "%HERE%" assembleRelease --no-daemon
if errorlevel 1 goto :failed

set "APK=%HERE%\app\build\outputs\apk\release\app-release.apk"
if not exist "%APK%" goto :noartifact
copy /Y "%APK%" "%HERE%\..\Unity3D.apk" >nul
echo.
echo   [ok] built: %HERE%\..\Unity3D.apk
echo.
echo   TO INSTALL
echo     1. node serve\server.mjs --host 0.0.0.0   (it prints the LAN address)
echo     2. Copy Unity3D.apk to the phone and open it
echo     3. On first launch, paste the address the server printed
echo.
goto :eof

:notoolchain
echo.
echo   [!] No Android SDK found.
echo       This project does NOT install its own toolchain. Run the sibling
echo       installer once, then re-run this:
echo         ..\..\windows\build_apk.bat
echo       Or set ANDROID_HOME and JAVA_HOME yourself.
exit /b 1

:failed
echo.
echo   [!] build failed. The output above is the real error; do not guess.
exit /b 1

:noartifact
echo.
echo   [!] gradle succeeded but produced no APK. Verify the artifact, not the exit code.
exit /b 1
