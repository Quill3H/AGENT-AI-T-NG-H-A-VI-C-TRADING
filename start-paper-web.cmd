@echo off
setlocal
set "PAPER_PORT=%~1"
if "%PAPER_PORT%"=="" set "PAPER_PORT=8765"
cd /d "%~dp0crypto-paper-agent"
if errorlevel 1 goto failed

if not exist ".venv-paper\Scripts\python.exe" (
  where uv >nul 2>nul
  if errorlevel 1 (
    echo Python environment is missing. Install uv or see docs\operations\LOCAL_PAPER_WEB.md.
    goto failed
  )
  uv venv .venv-paper --python 3.12
  if errorlevel 1 goto failed
  uv pip install --python .venv-paper\Scripts\python.exe pandas numpy requests loguru pyyaml "websocket-client>=1.8,<2"
  if errorlevel 1 goto failed
)
.venv-paper\Scripts\python.exe -c "import websocket" >nul 2>nul
if errorlevel 1 (
  where uv >nul 2>nul
  if errorlevel 1 goto failed
  uv pip install --python .venv-paper\Scripts\python.exe "websocket-client>=1.8,<2"
  if errorlevel 1 goto failed
)

cd web-preview
if not exist "node_modules" (
  call npm ci
  if errorlevel 1 goto failed
)
if not exist "dist\index.html" (
  call npm run build
  if errorlevel 1 goto failed
)
cd ..
.venv-paper\Scripts\python.exe scripts\run_local_paper_web.py --open-browser --port %PAPER_PORT%
if errorlevel 1 goto failed
exit /b 0

:failed
echo Local paper web did not start. No exchange orders were sent.
pause
exit /b 1
