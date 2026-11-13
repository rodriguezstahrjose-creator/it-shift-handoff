@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  py -3 -m venv .venv
  if errorlevel 1 goto failed
  .venv\Scripts\python.exe -m pip install -r requirements.txt
  if errorlevel 1 goto failed
)
.venv\Scripts\python.exe -m handoff init
if errorlevel 1 goto failed
echo Open http://127.0.0.1:5055 in your browser. Keep this window open.
.venv\Scripts\python.exe -m handoff run
goto :eof
:failed
echo Setup failed. Install Python 3.11 or newer and follow README.md.
pause
