@echo off
setlocal
title Trading terminal - frontend
cd /d "%~dp0frontend"

where node >nul 2>nul
if errorlevel 1 (
  echo Node.js not found. Install the LTS version from nodejs.org, then run this file again.
  pause & exit /b 1
)

if not exist "node_modules" (
  echo Installing packages ^(first run only^)...
  call npm install
  if errorlevel 1 (
    echo npm install failed. Copy the error above and send it over.
    pause & exit /b 1
  )
)

echo.
echo Frontend: http://localhost:5173   ^(start run_backend.bat first^). Press Ctrl+C to stop.
echo.
call npm run dev -- --open
pause
