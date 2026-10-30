@echo off
REM ===========================================================================
REM  install_voice.bat - her voice and her ears, one time.
REM
REM  Installs piper (text to speech) and faster-whisper (speech to text), then
REM  downloads the two models they need. Nothing is downloaded at speak time
REM  afterwards, and nothing is ever sent off this machine.
REM
REM  TWO TRAPS ARE HANDLED HERE AND BOTH COST REAL TIME TO FIND:
REM
REM  1. faster-whisper does NOT use torch's CUDA. It runs on CTranslate2, which
REM     resolves cuBLAS and cuDNN by name at first inference - so a machine with
REM     working torch still fails with "cublas64_12.dll is not found". The
REM     nvidia-* wheels below provide those DLLs; voice_server.py puts their bin
REM     folders on PATH at start up.
REM
REM  2. The HuggingFace cache SYMLINKS its blobs, and creating a symlink on
REM     Windows needs a privilege a normal account does not have - it dies with
REM     "WinError 1314". HF_HUB_DISABLE_SYMLINKS is not honoured by every
REM     version, so the model is fetched into a plain folder instead.
REM ===========================================================================
setlocal
cd /d "%~dp0.."

echo.
echo   UNITY - voice setup (one time)
echo   ---------------------------------------------
echo   Downloads about 550MB: a voice and a listener.
echo.

where python >nul 2>&1
if errorlevel 1 (
  echo   [!] python is not installed or not on PATH
  echo       https://www.python.org/downloads/   ^(tick "Add python.exe to PATH"^)
  exit /b 1
)

echo   [*] installing piper + faster-whisper...
python -m pip install --upgrade piper-tts faster-whisper
if errorlevel 1 (
  echo   [!] pip install failed - check the connection and run this again.
  exit /b 1
)

REM CTranslate2 needs these; torch's own copies are not visible to it.
echo   [*] installing CUDA runtime libraries for the listener...
python -m pip install --upgrade nvidia-cublas-cu12 nvidia-cudnn-cu12
if errorlevel 1 (
  echo   [!] CUDA libraries failed to install.
  echo       The listener needs a GPU - there is deliberately no CPU fallback,
  echo       because a silent CPU downgrade turns a broken install into
  echo       mysterious latency months later.
  exit /b 1
)

if not exist "models\piper" mkdir "models\piper"
if not exist "models\piper\en_US-hfc_female-medium.onnx" (
  echo   [*] downloading her voice ^(~63MB^)...
  curl -L --fail -o "models\piper\en_US-hfc_female-medium.onnx" "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/hfc_female/medium/en_US-hfc_female-medium.onnx"
  curl -L --fail -o "models\piper\en_US-hfc_female-medium.onnx.json" "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/hfc_female/medium/en_US-hfc_female-medium.onnx.json"
  if errorlevel 1 (
    echo   [!] voice download failed - run this again.
    exit /b 1
  )
) else (
  echo   [*] her voice is already here.
)

if not exist "models\whisper-small\model.bin" (
  echo   [*] downloading the listener ^(~480MB^)...
  REM local_dir_use_symlinks=False - see trap 2 in the header.
  python -c "from huggingface_hub import snapshot_download; snapshot_download('Systran/faster-whisper-small', local_dir='models/whisper-small', local_dir_use_symlinks=False)"
  if errorlevel 1 (
    echo   [!] listener download failed - run this again.
    exit /b 1
  )
) else (
  echo   [*] the listener is already here.
)

echo.
echo   [*] voice setup complete.
echo.
endlocal
