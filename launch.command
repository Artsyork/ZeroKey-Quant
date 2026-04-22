#!/bin/bash
# ZeroKey Quant — Mac 런처 (더블클릭으로 실행)
cd "$(dirname "$0")"

echo "=============================="
echo "  ZeroKey Quant 시작 중..."
echo "=============================="

# Python3 설치 확인
if ! command -v python3 &>/dev/null; then
  echo ""
  echo "❌ Python3이 설치되어 있지 않습니다."
  echo "   https://www.python.org 에서 설치 후 다시 실행해주세요."
  read -p "아무 키나 누르면 창이 닫힙니다..."
  exit 1
fi

# 의존성 자동 설치
echo "📦 의존성 확인 중..."
python3 -c "import flask, yfinance, pandas, numpy, plotly, requests, pytz" 2>/dev/null
if [ $? -ne 0 ]; then
  echo "📦 필요한 패키지를 설치합니다 (최초 1회)..."
  pip3 install flask yfinance pandas numpy plotly requests pytz
fi

echo ""
echo "✅ 브라우저에서 http://localhost:5001 이 자동으로 열립니다."
echo "   종료하려면 이 창을 닫거나 Ctrl+C 를 누르세요."
echo ""

python3 main.py
