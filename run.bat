@echo off
setlocal
cd /d "%~dp0"
title EE-Solver

echo ========================================
echo   EE-Solver starting
echo ========================================
echo.

:: Python check (prefer launcher if available)
set "PYTHON="
set "PY_ARGS="

where py >nul 2>&1
if %errorlevel%==0 (
    set "PYTHON=py"
    set "PY_ARGS=-3"
) else (
    if exist "%LOCALAPPDATA%\Programs\Python\Launcher\py.exe" (
        set "PYTHON=%LOCALAPPDATA%\Programs\Python\Launcher\py.exe"
        set "PY_ARGS=-3"
    ) else (
        where python >nul 2>&1
        if %errorlevel%==0 set "PYTHON=python"
    )
)

if not defined PYTHON (
    for /f "delims=" %%D in ('dir /b /ad "%LOCALAPPDATA%\Programs\Python\Python*" 2^>nul ^| sort /R') do (
        if exist "%LOCALAPPDATA%\Programs\Python\%%D\python.exe" (
            set "PYTHON=%LOCALAPPDATA%\Programs\Python\%%D\python.exe"
            goto :python_found
        )
    )
)
:python_found
if not defined PYTHON (
    echo [ERROR] Python is not installed or not on PATH.
    echo Install it from https://www.python.org/downloads/
    echo Make sure "Add Python to PATH" is checked.
    echo If Python Launcher is available, run: py -3 --version
    pause
    exit /b 1
)

%PYTHON% %PY_ARGS% --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python execution check failed.
    echo Try: python --version or py -3 --version
    pause
    exit /b 1
)

%PYTHON% %PY_ARGS% -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python 3.10+ is required.
    pause
    exit /b 1
)

:: Create virtual environment on first run
if not exist ".venv" (
    echo [1/3] Creating virtual environment...
    %PYTHON% %PY_ARGS% -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment
        pause
        exit /b 1
    )
    echo       Done.
) else (
    echo [1/3] Virtual environment already exists
)

:: Activate virtual environment
call .venv\Scripts\activate.bat
set "PYTHON=.venv\Scripts\python.exe"
set "PY_ARGS="

:: Install packages
echo [2/3] Checking dependencies...
%PYTHON% -m pip install -r requirements.txt -q
if errorlevel 1 (
    echo [ERROR] Package installation failed
    pause
    exit /b 1
)
echo       Done.

:: Create .env if missing or empty
set "ENV_MISSING="
if not exist ".env" set "ENV_MISSING=1"
if exist ".env" for %%A in (".env") do if %%~zA==0 set "ENV_MISSING=1"
if defined ENV_MISSING (
    echo.
    echo ========================================
    echo   Gemini API key setup is required.
    echo   https://aistudio.google.com/apikey
    echo ========================================
    echo.
    set /p API_KEY="Enter your Gemini API key: "
    echo GEMINI_API_KEY=%API_KEY%> .env
    echo GEMINI_MODEL=gemini-3-flash-preview>> .env
    echo.
    echo .env created.
)

:: Start server
echo [3/3] Starting server...
echo.
echo ========================================
echo   Browser will open at:
echo   http://127.0.0.1:8100
echo.
echo   Close this window or press Ctrl+C to stop.
echo ========================================
echo.

start http://127.0.0.1:8100
%PYTHON% -m uvicorn server:app --port 8100

pause
