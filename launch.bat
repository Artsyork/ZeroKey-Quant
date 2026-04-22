@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ==============================
echo   ZeroKey Quant 시작 중...
echo ==============================

:: Python3 설치 확인
python --version >nul 2>&1
if %errorlevel% neq 0 (
  echo.
  echo ❌ Python이 설치되어 있지 않습니다.
  echo    https://www.python.org 에서 설치 후 다시 실행해주세요.
  pause
  exit /b 1
)

:: 의존성 자동 설치
echo 📦 의존성 확인 중...
python -c "import flask, yfinance, pandas, numpy, plotly, requests, pytz" 2>nul
if %errorlevel% neq 0 (
  echo 📦 필요한 패키지를 설치합니다 (최초 1회)...
  pip install flask yfinance pandas numpy plotly requests pytz
)

echo.
echo ✅ 브라우저에서 http://localhost:5001 이 자동으로 열립니다.
echo    종료하려면 이 창을 닫거나 Ctrl+C 를 누르세요.
echo.

python main.py
pause
