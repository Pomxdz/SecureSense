@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title SecureSense Viva Campaign Seeder

if not exist ".venv\Scripts\python.exe" (
    echo SecureSense environment is not ready yet.
    echo Run start_practice.bat first, then leave it running and run this file again.
    pause
    exit /b 1
)

echo ==============================================================
echo   SecureSense - Gophish viva campaign showcase
echo   Five localhost-only campaigns / fictional .test recipients
echo ==============================================================
.venv\Scripts\python.exe seed_viva_gophish.py --open
set "EXITCODE=%ERRORLEVEL%"
if not "%EXITCODE%"=="0" (
    echo.
    echo Campaign setup did not complete. Review the message above.
)
pause
exit /b %EXITCODE%
