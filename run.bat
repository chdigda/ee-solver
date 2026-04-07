@echo off
chcp 65001 >nul
title EE-Solver

echo ========================================
echo   EE-Solver 시작
echo ========================================
echo.

:: Python 확인
python --version >nul 2>&1
if errorlevel 1 (
    echo [오류] Python이 설치되어 있지 않습니다.
    echo https://www.python.org/downloads/ 에서 설치해주세요.
    echo 설치 시 "Add Python to PATH" 체크를 꼭 해주세요.
    pause
    exit /b 1
)

:: 가상환경 생성 (최초 1회)
if not exist ".venv" (
    echo [1/3] 가상환경 생성 중...
    python -m venv .venv
    if errorlevel 1 (
        echo [오류] 가상환경 생성 실패
        pause
        exit /b 1
    )
    echo       완료!
) else (
    echo [1/3] 가상환경 확인... 이미 존재
)

:: 가상환경 활성화
call .venv\Scripts\activate.bat

:: 패키지 설치
echo [2/3] 패키지 설치 확인 중...
pip install -r requirements.txt -q
if errorlevel 1 (
    echo [오류] 패키지 설치 실패
    pause
    exit /b 1
)
echo       완료!

:: .env 파일 확인
if not exist ".env" (
    echo.
    echo ========================================
    echo   Gemini API 키 설정이 필요합니다.
    echo   https://aistudio.google.com/apikey
    echo ========================================
    echo.
    set /p API_KEY="Gemini API 키를 입력하세요: "
    echo GEMINI_API_KEY=%API_KEY%> .env
    echo GEMINI_MODEL=gemini-3-flash-preview>> .env
    echo.
    echo .env 파일이 생성되었습니다.
)

:: 서버 시작
echo [3/3] 서버 시작 중...
echo.
echo ========================================
echo   브라우저에서 열립니다:
echo   http://127.0.0.1:8100
echo.
echo   종료하려면 이 창을 닫거나 Ctrl+C
echo ========================================
echo.

start http://127.0.0.1:8100
python -m uvicorn server:app --port 8100

pause
