@echo off
rem Offline smoke test for her face: Ditto renders .run\say.wav onto the portrait -> .run\ditto-test.mp4
rem Run this once by hand; it proves the renderer, the weights and the GPU work before the live sidecar starts.
setlocal
cd /d "%~dp0.."
set "PY=%CD%\sidecars\face\.venv\Scripts\python.exe"
if not exist "%PY%" ( echo face venv missing: see sidecars\face\README.md & exit /b 1 )
if not exist ".run\say.wav" (
  echo making a test line with the voice sidecar...
  curl -s -X POST http://127.0.0.1:5123/say -H "Content-Type: application/json" -d "{\"text\":\"Hey you. I can see you now, can you see me? Good.\",\"emotion\":\"amused\",\"intensity\":0.5}" -o .run\say.wav
)
pushd third_party\ditto-talkinghead
"%PY%" inference.py --data_root "%CD%\..\..\models\ditto\ditto_pytorch" --cfg_pkl "%CD%\..\..\models\ditto\ditto_cfg\v0.4_hubert_cfg_pytorch.pkl" --audio_path "%CD%\..\..\.run\say.wav" --source_path "%CD%\..\..\assets\portrait\unity-likeness.png" --output_path "%CD%\..\..\.run\ditto-test.mp4"
popd
if exist ".run\ditto-test.mp4" ( echo OK: .run\ditto-test.mp4 & start "" ".run\ditto-test.mp4" ) else ( echo FAILED: no output; read the error above )
endlocal
