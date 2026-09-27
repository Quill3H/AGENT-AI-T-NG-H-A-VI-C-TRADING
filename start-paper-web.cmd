@echo off
setlocal
set "PAPER_PORT=%~1"
if "%PAPER_PORT%"=="" set "PAPER_PORT=8765"
cd /d "%~dp0crypto-paper-agent"
if errorlevel 1 goto failed

if not exist ".venv-paper\Scripts\python.exe" (
  where uv >nul 2>nul
  if errorlevel 1 (
    echo Python environment is missing. Install uv or see crypto-paper-agent\docs\operations\LOCAL_PAPER_WEB.md.
    goto failed
  )
  uv venv .venv-paper --python 3.12
  if errorlevel 1 goto failed
  uv pip install --python .venv-paper\Scripts\python.exe pandas numpy requests loguru pyyaml
  if errorlevel 1 goto failed
)

cd web-preview
if not exist "node_modules" (
  call npm ci
  if errorlevel 1 goto failed
)
call npm run build
if errorlevel 1 goto failed
cd ..
.venv-paper\Scripts\python.exe scripts\run_local_paper_web.py --open-browser --port %PAPER_PORT% --watchdog
if errorlevel 1 goto failed
exit /b 0

:failed
echo Local paper web did not start. No exchange orders were sent.
pause
exit /b 1
