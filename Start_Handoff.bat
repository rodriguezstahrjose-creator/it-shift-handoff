@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  py -3 -m venv .venv
  if errorlevel 1 goto failed
)
.venv\Scripts\python.exe -c "import sys; sys.exit(sys.version_info < (3, 11))"
if errorlevel 1 goto failed
.venv\Scripts\python.exe scripts\check_runtime.py
if errorlevel 1 (
  .venv\Scripts\python.exe -m pip install -r requirements.txt
  if errorlevel 1 goto failed
)
.venv\Scripts\python.exe -m handoff init
if errorlevel 1 goto failed
echo Open http://127.0.0.1:5055 in your browser. Keep this window open.
.venv\Scripts\python.exe -m handoff run
if errorlevel 1 goto failed
goto :eof
:failed
echo Setup or startup failed. Read the error above. Python 3.11 or newer is required.
echo Initial setup or dependency repair needs internet. See README.md for manual setup.
pause
