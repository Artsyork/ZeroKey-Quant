# 📈 ZeroKey Quant

개인용 퀀트 분석 대시보드. 미국·한국 주식의 기술적 지표를 자동으로 계산하고, 매수/매도/관망 시그널과 목표가를 제시합니다. 별도 구독료 없이 무료 데이터 소스만으로 동작합니다.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Flask](https://img.shields.io/badge/Flask-3.x-lightgrey)
![License](https://img.shields.io/badge/License-MIT-green)

---

## ✨ 주요 기능

### 종목 분석
| 기능 | 설명 |
|---|---|
| **기술 지표** | RSI · ADX · EMA(12/26/50) · SMA(200) · Bollinger Bands · ATR · OBV · 역사적 변동성(HV) |
| **매매 시그널** | EMA 골든/데드크로스 + ADX >25 + OBV 방향 + RSI 복합 조건 + 관망 일수 자동 제시 |
| **목표가 / 손절가** | ATR 기반 자동 계산 (R:R 비율 포함) |
| **5일 변동 예상 범위** | 역사적 변동성 ±1σ |
| **성과 지표** | 연환산 수익률 · 변동성 · 샤프 · 소르티노 · 칼마 비율 · MDD |
| **애널리스트 컨센서스** | 미국 주식 한정 (Finviz 집계) |
| **보유 현황** | 평균 매입가 · 평가손익 · 수익률 계산 (localStorage 저장) |

### 발굴 스캐너
| 스캐너 | 조건 |
|---|---|
| 💎 소형주 보석 | 시총 $300M–$2B · 분기 매출 성장 >25% · 애널리스트 매수 추천 |
| 🔍 내부자 매수 | 최근 임원/대주주 매수 거래 |
| 🚀 혁신주 | AI·바이오·에너지전환·블록체인·로봇 테마 큐레이션 |

### AI 분석
- **Gemini 1.5 Flash** 기반 기술적 분석 코멘트 (매수 근거 / 리스크 / 종합 판단)
- 일일 사용량 실시간 표시 (무료 티어 1,500회/일)

### 기타
- 가격 알림 (목표가·손절가 도달 시 브라우저 알림, 2분마다 폴링)
- 한국 주식 완전 지원 (네이버 금융, KRW 표시, 종목명 자동 조회)
- 다크 테마 UI (Navy + Glass 디자인 시스템)
- 랜딩 페이지 온보딩 (최초 방문 시 Gemini API 키 설정 안내)
- 사이드바 설정(⚙) 버튼으로 API 키 상태 확인 및 재설정
- 스캐너 결과에서 종목 즉시 추가
- 전체 종목 일괄 새로고침

---

## 🚀 설치 및 실행

### 요구사항
- Python 3.10 이상
- 인터넷 연결 (데이터 실시간 조회)

### 1. 저장소 클론

```bash
git clone https://github.com/Artsyork/ZeroKey-Quant.git
cd ZeroKey-Quant
```

### 2. 의존성 설치

```bash
pip install flask yfinance pandas numpy plotly requests pytz
```

또는 `requirements.txt` 생성 후 한 번에:

```bash
pip install -r requirements.txt
```

### 3. 실행

```bash
python3 main.py
```

브라우저가 자동으로 `http://localhost:5001` 을 엽니다.

### 4. AI 분석 기능 사용 (선택)

[Google AI Studio](https://aistudio.google.com/app/apikey) 에서 무료 API 키를 발급한 후:

```bash
export GEMINI_API_KEY="your-api-key-here"
python3 main.py
```

---

## 📖 사용 설명서

### 종목 검색

사이드바 검색창에 티커를 입력하고 **추가** 버튼을 누릅니다.

```
미국 주식:  AAPL   TSLA   NVDA   MSFT   AMZN
한국 주식:  005930 (삼성전자)   035420 (NAVER)   000660 (SK하이닉스)
```

> 한국 주식은 6자리 숫자 코드를 입력합니다. `.KS` / `.KQ` 접미사도 지원합니다.

---

### 시그널 읽기

분석 화면 상단에 **BUY / SELL / WAIT** 배지가 표시됩니다.

| 배지 | 조건 | 의미 |
|---|---|---|
| **▲ BUY** | EMA12 > EMA26 AND ADX > 25 AND OBV↑ AND RSI < 70 | 4개 조건 동시 충족, 매수 검토 |
| **▼ SELL** | EMA12 < EMA26 AND ADX > 25 AND OBV↓ AND RSI > 30 | 4개 조건 동시 충족, 매도 검토 |
| **⏸ WAIT** | 위 조건 미충족 | ADX·RSI 상태에 따른 관망 기간 제시 |

**예시 — NVDA BUY 시그널**
```
▲ 매수 시그널
진입가:  $118.50  (현재가 − 0.5×ATR)
목표가:  $127.20  (+7.3%)
손절가:  $113.80  (-4.0%)
R:R 비율: 1.8
```

---

### 매수 / 매도 시나리오 카드

ATR(Average True Range) 기반으로 진입가·목표가·손절가를 자동 계산합니다.

```
매수 시나리오
  진입가 (close − 0.5×ATR) : $118.50
  목표가 (close + 2.0×ATR) : $127.20  +7.3%
  손절가 (close − 1.0×ATR) : $113.80  -4.0%
  R:R                       : 1.8

매도(숏) 시나리오
  진입가 (close + 0.5×ATR) : $121.50
  목표가 (close − 2.0×ATR) : $112.80  -6.1%
  손절가 (close + 1.0×ATR) : $126.20  +4.0%
  R:R                       : 1.5
```

---

### 가격 알림 설정

분석 화면 하단 **알림 설정** 에서 목표가·손절가를 입력하면, 해당 가격 도달 시 브라우저 알림을 받을 수 있습니다.

```
목표가 알림:  $130.00  → 가격 돌파 시 "NVDA 목표가 도달!" 알림
손절가 알림:  $110.00  → 가격 하락 시 "NVDA 손절가 도달!" 알림
```

> 알림은 2분마다 가격을 폴링합니다. 브라우저 알림 권한을 허용해야 합니다.

---

### AI 분석 요청

GEMINI_API_KEY 설정 후, 종목 분석 화면의 **🤖 AI 시그널 분석** 카드에서 **분석 요청** 버튼을 클릭합니다.

**예시 출력**
```
종합 판단
  EMA 골든크로스와 강한 ADX(32)가 상승 추세를 지지하나,
  RSI 68로 단기 과열 가능성이 있어 눌림목 진입을 권장합니다.

📈 매수 근거              📉 리스크 요인
  · EMA12 > EMA26         · RSI 68, 과매수 근접
  · ADX 32 (강한 추세)    · 거래량 감소 추세
  · OBV 지속 상승         · 섹터 전반 조정 가능

신뢰도: 중간   투자 기간: 중기(1-3개월)
```

---

## 🏗 아키텍처

```
zerokey-quant/
├── main.py            # Flask 서버 (백엔드 전체)
├── dashboard.html     # 단일 페이지 프론트엔드
├── ai_usage.json      # AI 일일 사용량 추적 (런타임 생성, git 제외)
├── ticker_history.json          # 개인 조회 기록 (git 제외)
├── ticker_history.example.json  # 형식 예시
└── .gitignore
```

### 백엔드 구조 (`main.py`)

```
main.py
├── 데이터 수집
│   ├── fetch_naver()          # 네이버 금융 → 한국 주식 OHLCV
│   ├── _fetch_yfinance()      # Yahoo Finance → 미국 주식 OHLCV
│   └── fetch_analyst()        # Finviz → 애널리스트 컨센서스
│
├── 지표 계산
│   ├── _rsi()  _atr()  _ema() # 개별 지표 함수
│   ├── _adx()  _bb()          # ADX, Bollinger Bands
│   ├── _obv()  _hv()          # OBV, 역사적 변동성
│   └── build()                # 위 지표를 DataFrame에 합산
│
├── 시그널 / 추천
│   └── recommend()            # BUY/SELL/WAIT 판정 + 목표가 + 성과지표(샤프·소르티노·칼마·MDD)
│
├── 차트
│   └── make_chart()           # Plotly 4-subplot 차트 생성
│
├── AI 분석
│   ├── ai_analyze()           # Gemini API 호출
│   └── _get_usage()           # 일일 사용량 관리
│
└── Flask 라우트
    ├── GET /                  # dashboard.html 서빙
    ├── GET /api/analyze       # 종목 전체 분석
    ├── GET /api/price         # 빠른 가격 조회 (알림 폴링)
    ├── GET /api/ai-analysis   # AI 시그널 분석
    ├── GET /api/ai-usage      # AI 사용량 조회
    ├── GET /api/scan/smallcap # 소형주 스캐너
    ├── GET /api/scan/insider  # 내부자 매수 스캐너
    └── GET /api/scan/disruptive # 혁신주 스캐너
```

### 프론트엔드 구조 (`dashboard.html`)

단일 HTML 파일로 구성됩니다. 외부 프레임워크 없이 Vanilla JS로 작성되어 있습니다.

```
dashboard.html
├── CSS           인라인 디자인 시스템 (CSS 변수, 다크 테마)
├── HTML          랜딩 페이지 + 사이드바 + 분석 패널 + 발굴 탭
└── JavaScript
    ├── fetchTicker()        /api/analyze 호출 → 캐시 저장 (재시도 2회)
    ├── showAnalysis()       캐시 데이터 → 화면 렌더링
    ├── renderSidebar()      종목 목록 + 시그널 dot + 손익 표시
    ├── Plotly 차트          서버 반환 JSON → 차트 렌더링
    ├── 알림 시스템          2분 폴링 + Web Notifications API
    ├── 보유 현황            localStorage 저장/불러오기
    ├── requestAiAnalysis()  AI 분석 요청 및 결과 표시
    ├── loadUsagePill()      AI 일일 사용량 조회 및 진행바 표시
    ├── runScan()            3종 스캐너 실행 및 결과 렌더링
    └── lpSaveKey() / lpEnter() / lpShow()  랜딩 페이지 제어
```

### 데이터 흐름

```
브라우저 → GET /api/analyze?ticker=NVDA
              │
              ▼
         build(ticker)
              ├─ yfinance / 네이버 금융  →  OHLCV DataFrame
              ├─ 지표 계산 (RSI, ADX …)
              └─ 시그널 판정 (BUY/SELL/WAIT)
              │
         make_chart()  →  Plotly JSON
         recommend()   →  시그널 dict
         fetch_analyst() →  컨센서스 dict
              │
              ▼
         JSON 응답 → 브라우저 렌더링
```

### 데이터 소스

| 소스 | 용도 | 제한 |
|---|---|---|
| 네이버 금융 | 한국 주식 OHLCV (최근 300일) | 무료, 비공식 |
| Yahoo Finance (yfinance) | 미국 주식 OHLCV (1년) | 무료, 비공식, ~2,000회/시간 |
| Finviz | 미국 주식 애널리스트 컨센서스, 스캐너 | 무료, 비공식 |
| Gemini 1.5 Flash | AI 분석 | 무료 1,500회/일 (API 키 필요) |

---

## ⚠️ 면책조항

- 이 도구는 **개인 학습 및 비상업적 사용** 목적으로 제작되었습니다.
- 제공되는 시그널과 분석은 **투자 권유가 아닙니다.** 투자 결정의 책임은 본인에게 있습니다.
- Naver Finance, Yahoo Finance, Finviz 데이터는 비공식 방식으로 조회됩니다. 각 서비스의 이용약관을 준수할 책임은 사용자에게 있습니다.

---

## 📄 라이선스

MIT License
