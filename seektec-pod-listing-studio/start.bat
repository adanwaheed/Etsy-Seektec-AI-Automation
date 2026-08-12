@echo off
setlocal
cd /d "%~dp0"

if not exist .venv (
  py -3.13 -m venv .venv 2>nul || py -3.12 -m venv .venv 2>nul || py -3.11 -m venv .venv
)
if errorlevel 1 (
  echo Could not create the Python environment. Install Python 3.11, 3.12, or 3.13.
  pause
  exit /b 1
)

.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 pause & exit /b 1

start "" http://127.0.0.1:8000
.venv\Scripts\python.exe -m uvicorn app.main:app --reload
