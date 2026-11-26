@echo off
setlocal
title Trading terminal - backend
cd /d "%~dp0backend"

where py >nul 2>nul
if errorlevel 1 (
  echo Python launcher not found. Install Python 3.12 from python.org and tick "Add python.exe to PATH".
  pause & exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Creating virtual environment with Python 3.12...
  py -3.12 -m venv .venv
  if errorlevel 1 (
    echo Could not create the environment. Run "py -0" to check that Python 3.12 is installed.
    pause & exit /b 1
  )
)
call ".venv\Scripts\activate.bat"

python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)"
if errorlevel 1 (
  echo This environment uses an old Python. Delete the backend\.venv folder and run this file again.
  pause & exit /b 1
)

if not exist ".venv\.deps_installed" (
  echo Installing packages ^(first run only, takes a few minutes^)...
  python -m pip install --upgrade pip
  pip install -r requirements.txt
  if errorlevel 1 (
    echo Package install failed. Copy the error above and send it over.
    pause & exit /b 1
  )
  echo done> ".venv\.deps_installed"
)

if not exist ".env" copy ".env.example" ".env" >nul

echo.
echo Backend: http://127.0.0.1:8000   API docs: http://127.0.0.1:8000/docs
echo Keep MetaTrader 5 open and logged into your DEMO account. Press Ctrl+C to stop.
echo.
python -m uvicorn app.main:app --reload
pause
