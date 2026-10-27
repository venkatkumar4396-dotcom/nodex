@echo off
setlocal
cd /d "%~dp0backend"
echo ========================================================
echo   Starting AgentFlow Backend (FastAPI + SQLite)
echo   API Docs: http://localhost:8000/docs
echo ========================================================

REM Free port 8000 if occupied
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr ":8000 "') do (
    if not "%%a"=="" if not "%%a"=="0" taskkill /F /PID %%a >nul 2>&1
)

if not exist ".\.venv\Scripts\python.exe" (
    echo [ERROR] Python virtual environment not found in %~dp0backend\.venv
    echo Please run setup first or install python dependencies.
    pause
    exit /b 1
)

.\.venv\Scripts\python.exe -m uvicorn agentflow.api.app:app --reload --port 8000
pause
