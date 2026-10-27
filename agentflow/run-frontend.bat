@echo off
setlocal
cd /d "%~dp0frontend"
echo ========================================================
echo   Starting AgentFlow Frontend (Vite + React Flow)
echo   UI: http://localhost:5173
echo ========================================================

REM Free port 5173 if occupied
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr ":5173 "') do (
    if not "%%a"=="" if not "%%a"=="0" taskkill /F /PID %%a >nul 2>&1
)

if not exist "node_modules" (
    echo [INFO] node_modules not found. Installing dependencies...
    call npm install
)

npm run dev
pause
