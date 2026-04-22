@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ==============================
echo   ZeroKey Quant Starting...
echo ==============================
echo.

:: Python 명령어 탐색 (python -> py -> python3 순서)
set PYTHON_CMD=
python --version >nul 2>&1
if %errorlevel% equ 0 ( set PYTHON_CMD=python & goto :found_python )

py --version >nul 2>&1
if %errorlevel% equ 0 ( set PYTHON_CMD=py & goto :found_python )

python3 --version >nul 2>&1
if %errorlevel% equ 0 ( set PYTHON_CMD=python3 & goto :found_python )

echo [ERROR] Python이 설치되어 있지 않습니다.
echo         https://www.python.org 에서 설치 후 다시 실행해주세요.
echo         설치 시 "Add Python to PATH" 옵션을 반드시 체크하세요.
echo.
pause
exit /b 1

:found_python
echo [OK] Python 확인: %PYTHON_CMD%

:: 의존성 확인 및 자동 설치
echo [..] 패키지 확인 중...
%PYTHON_CMD% -c "import flask, yfinance, pandas, numpy, plotly, requests, pytz" >nul 2>&1
if %errorlevel% neq 0 (
  echo [..] 필요한 패키지를 설치합니다. 잠시 기다려주세요...
  %PYTHON_CMD% -m pip install flask yfinance pandas numpy plotly requests pytz
  if %errorlevel% neq 0 (
    echo [ERROR] 패키지 설치에 실패했습니다.
    echo         관리자 권한으로 실행하거나 수동으로 설치해주세요:
    echo         pip install flask yfinance pandas numpy plotly requests pytz
    pause
    exit /b 1
  )
)
echo [OK] 패키지 확인 완료

echo.
echo [!] Windows 방화벽 팝업이 뜨면 "액세스 허용"을 클릭해주세요.
echo [OK] 브라우저에서 http://localhost:5001 이 자동으로 열립니다.
echo     종료하려면 이 창을 닫거나 Ctrl+C 를 누르세요.
echo.

%PYTHON_CMD% main.py
pause
