@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title SecureSense exercise Launcher

echo ==============================================================
echo   SecureSense - submission-ready local exercise launcher
echo ==============================================================

if not exist ".venv\Scripts\python.exe" (
    echo [setup] Creating Python virtual environment...
    where py >nul 2>&1
    if not errorlevel 1 (
        py -3 -m venv .venv
    ) else (
        python -m venv .venv
    )
    if errorlevel 1 goto :fail
)

if not exist ".env" (
    copy /Y ".env.example" ".env" >nul
    echo [setup] Created .env from .env.example
)

echo [setup] Checking Python dependencies...
.venv\Scripts\python.exe -m pip install --disable-pip-version-check -q -r requirements.txt
if errorlevel 1 goto :fail

echo [launch] Starting SecureSense, local inbox, SMTP proxy and optional Gophish...
.venv\Scripts\python.exe practice_launcher.py
set "EXITCODE=%ERRORLEVEL%"

echo.
if not "%EXITCODE%"=="0" (
    echo Launcher exited with code %EXITCODE%.
) else (
    echo practice services stopped.
)
pause
exit /b %EXITCODE%

:fail
echo.
echo Setup failed. Review the error above, then run start_practice.bat again.
pause
exit /b 1
