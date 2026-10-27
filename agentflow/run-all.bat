@echo off
echo ========================================================
echo   Launching AgentFlow Stack...
echo ========================================================
start "AgentFlow Backend" cmd /c ""%~dp0run-backend.bat""
timeout /t 2 /nobreak >nul
start "AgentFlow Frontend" cmd /c ""%~dp0run-frontend.bat""
echo.
echo Both servers launched in separate windows!
echo - Backend API:  http://localhost:8000/docs
echo - Frontend UI:   http://localhost:5173
echo.
pause
