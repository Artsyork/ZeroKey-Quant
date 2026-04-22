#!/usr/bin/env python3
"""
main.py — ZeroKey Quant (Flask)
Usage : python3 main.py
Opens : http://localhost:5001
"""

import json, os, re, sys, threading, time, webbrowser, warnings
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from datetime import datetime
import pytz
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import yfinance as yf
import requests
from flask import Flask, jsonify, request, send_file
from plotly.subplots import make_subplots

warnings.filterwarnings("ignore")
app = Flask(__name__)

def _resource_path(rel: str) -> str:
    """Bundle 내부 파일 경로 반환 — 개발 환경과 PyInstaller 번들 모두 대응."""
    base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)

def _data_dir() -> str:
    """런타임 데이터(ai_usage.json 등) 저장 경로 — 번들 외부 쓰기 가능 위치."""
    if sys.platform == 'darwin':
        d = os.path.expanduser('~/Library/Application Support/ZeroKeyQuant')
    elif sys.platform == 'win32':
        d = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'ZeroKeyQuant')
    else:
        d = os.path.expanduser('~/.zerokey-quant')
    os.makedirs(d, exist_ok=True)
    return d

# ══════════════════════════════════════════════
# KOREAN STOCK DETECTION & DATA FETCH
# ══════════════════════════════════════════════

def is_korean(ticker: str) -> bool:
    """6자리 숫자 → 한국 주식 (코스피/코스닥)"""
    base = ticker.upper().replace(".KS", "").replace(".KQ", "")
    return bool(re.match(r"^\d{6}$", base))

def parse_korean_code(ticker: str) -> str:
    """005930 or 005930.KS → 005930"""
    return ticker.upper().replace(".KS", "").replace(".KQ", "")

def fetch_naver(code6: str) -> pd.DataFrame:
    """
    Naver Finance chart API → daily OHLCV DataFrame.
    endpoint: fchart.stock.naver.com/sise.nhn
    item data format: date|open|high|low|close|volume
    """
    url = (
        f"https://fchart.stock.naver.com/sise.nhn"
        f"?symbol={code6}&timeframe=day&count=300&requestType=0"
    )
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 Chrome/124.0 Safari/537.36"
        ),
        "Referer": f"https://finance.naver.com/item/main.naver?code={code6}",
    }
    resp = requests.get(url, headers=headers, timeout=10)
    resp.raise_for_status()

    items = re.findall(r'data="([^"]+)"', resp.text)
    if not items:
        raise ValueError(f"Naver Finance 데이터 없음: {code6}")

    rows = []
    for item in items:
        p = item.split("|")
        if len(p) >= 6 and all(p[:6]):
            try:
                rows.append({
                    "date":   pd.to_datetime(p[0], format="%Y%m%d"),
                    "open":   float(p[1]),
                    "high":   float(p[2]),
                    "low":    float(p[3]),
                    "close":  float(p[4]),
                    "volume": float(p[5]),
                })
            except ValueError:
                continue

    if not rows:
        raise ValueError(f"Naver Finance 파싱 실패: {code6}")

    df = pd.DataFrame(rows).set_index("date").sort_index()
    df.index.name = "Date"
    return df

def fetch_naver_name(code6: str) -> str:
    """네이버 증권에서 종목명 조회"""
    try:
        url = f"https://finance.naver.com/item/main.naver?code={code6}"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=5)
        m = re.search(r'<title>([^<]+) : (?:네이버 금융|Npay 증권)', resp.text)
        if m:
            return m.group(1).strip()
    except Exception:
        pass
    return code6

# ══════════════════════════════════════════════
# ANALYST CONSENSUS  (Finviz — US only)
# ══════════════════════════════════════════════

_RECOM_LABELS = {
    (1.0, 1.5): ("Strong Buy",  "#3fb950"),
    (1.5, 2.5): ("Buy",         "#7ee787"),
    (2.5, 3.5): ("Hold",        "#e3b341"),
    (3.5, 4.5): ("Sell",        "#f0883e"),
    (4.5, 5.1): ("Strong Sell", "#f85149"),
}

def fetch_analyst(ticker: str) -> dict | None:
    """Finviz에서 미국 주식 애널리스트 컨센서스 조회"""
    try:
        url = f"https://finviz.com/quote.ashx?t={ticker}&p=d"
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
        }
        resp = requests.get(url, headers=headers, timeout=8)
        if resp.status_code != 200:
            return None

        rows = re.findall(
            r'<td[^>]*class="[^"]*snapshot[^"]*"[^>]*>(.*?)</td>',
            resp.text, re.DOTALL
        )
        clean = [re.sub(r"<[^>]+>", "", x).strip() for x in rows]
        pairs = {clean[i]: clean[i + 1] for i in range(0, len(clean) - 1, 2)}

        recom_raw = pairs.get("Recom", "-")
        target_raw = pairs.get("Target Price", "-")
        eps_q  = pairs.get("EPS next Q", "-")
        eps_y  = pairs.get("EPS next Y", "-")
        eps_5y = pairs.get("EPS next 5Y", "-")

        # Recom 숫자 → 라벨
        recom_label, recom_color = "N/A", "#8b949e"
        try:
            score = float(recom_raw)
            for (lo, hi), (lbl, clr) in _RECOM_LABELS.items():
                if lo <= score < hi:
                    recom_label, recom_color = lbl, clr
                    break
        except ValueError:
            score = None

        return {
            "recom_score": recom_raw,
            "recom_label": recom_label,
            "recom_color": recom_color,
            "target_price": target_raw,
            "eps_next_q":   eps_q,
            "eps_next_y":   eps_y,
            "eps_next_5y":  eps_5y,
            "source":       "Finviz (Yahoo Finance · Refinitiv 집계)",
        }
    except Exception:
        return None


# ══════════════════════════════════════════════
# INDICATORS
# ══════════════════════════════════════════════

def _rsi(close, period=14):
    d  = close.diff()
    up = d.clip(lower=0).ewm(alpha=1/period, adjust=False).mean()
    dn = (-d).clip(lower=0).ewm(alpha=1/period, adjust=False).mean()
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))

def _atr(high, low, close, period=14):
    pc = close.shift(1)
    tr = pd.concat([(high-low),(high-pc).abs(),(low-pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1/period, adjust=False).mean()

def _ema(close, span):
    return close.ewm(span=span, adjust=False).mean()

def _adx(high, low, close, period=14):
    up  = high.diff(); dn = -low.diff()
    pdm = pd.Series(np.where((up>dn)&(up>0), up, 0.0), index=close.index)
    mdm = pd.Series(np.where((dn>up)&(dn>0), dn, 0.0), index=close.index)
    a   = _atr(high, low, close, period)
    pdi = 100 * pdm.ewm(alpha=1/period, adjust=False).mean() / a
    mdi = 100 * mdm.ewm(alpha=1/period, adjust=False).mean() / a
    dx  = 100 * (pdi-mdi).abs() / (pdi+mdi).replace(0, np.nan)
    return pd.DataFrame({"+di": pdi, "-di": mdi, "adx": dx.ewm(alpha=1/period, adjust=False).mean()})

def _bb(close, period=20, k=2.0):
    mid = close.rolling(period).mean()
    std = close.rolling(period).std()
    return pd.DataFrame({"bb_mid": mid, "bb_upper": mid+k*std, "bb_lower": mid-k*std})

def _obv(close, volume):
    return (volume * np.sign(close.diff()).fillna(0)).cumsum()

def _hv(close, period=20, ann=252):
    return np.log(close/close.shift(1)).rolling(period).std() * np.sqrt(ann)

# ══════════════════════════════════════════════
# BUILD DATAFRAME
# ══════════════════════════════════════════════

def _yf_history(ticker: str, period: str, interval: str) -> pd.DataFrame:
    """yfinance history 호출 (스레드 내부에서 실행)"""
    raw = yf.Ticker(ticker).history(period=period, interval=interval, auto_adjust=True)
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)
    raw.columns = [c.lower() for c in raw.columns]
    if hasattr(raw.index, "tz") and raw.index.tz is not None:
        raw.index = raw.index.tz_localize(None)
    return raw[["open", "high", "low", "close", "volume"]].dropna()


def _fetch_yfinance(ticker: str, period: str, interval: str,
                    timeout: int = 8, retries: int = 2) -> tuple[pd.DataFrame, str]:
    """Yahoo Finance 데이터 조회 — 호출당 최대 timeout초 제한, retries회 재시도"""
    for attempt in range(retries):
        try:
            with ThreadPoolExecutor(max_workers=1) as ex:
                df = ex.submit(_yf_history, ticker, period, interval).result(timeout=timeout)
            if len(df) >= 50:
                try:
                    name = yf.Ticker(ticker).info.get("shortName", ticker)
                except Exception:
                    name = ticker
                return df, name
        except (FutureTimeout, Exception):
            pass
        if attempt < retries - 1:
            time.sleep(1.0)
    return pd.DataFrame(), ticker


def build(ticker: str, period: str = "1y", interval: str = "1d"):
    korean = is_korean(ticker)
    stock_name = ticker
    currency = "KRW" if korean else "USD"

    if korean:
        code6 = parse_korean_code(ticker)
        stock_name = fetch_naver_name(code6)
        df = fetch_naver(code6)
    else:
        df, stock_name = _fetch_yfinance(ticker, period, interval)

    if len(df) < 50:
        hint = "유효한 티커인지 확인하거나 잠시 후 다시 시도하세요"
        raise ValueError(f"데이터 부족 ({len(df)}일): {ticker} — {hint}")

    df.columns = [c.lower() for c in df.columns]
    df["rsi"]    = _rsi(df["close"])
    df["atr"]    = _atr(df["high"], df["low"], df["close"])
    df["ema12"]  = _ema(df["close"], 12)
    df["ema26"]  = _ema(df["close"], 26)
    df["ema50"]  = _ema(df["close"], 50)
    df["sma200"] = df["close"].rolling(200).mean()
    df["obv"]    = _obv(df["close"], df["volume"])
    df["hv"]     = _hv(df["close"])
    df = pd.concat([df, _adx(df["high"], df["low"], df["close"])], axis=1)
    df = pd.concat([df, _bb(df["close"])], axis=1)

    # Signals
    obv_up = df["obv"] > df["obv"].shift(1)
    obv_dn = df["obv"] < df["obv"].shift(1)
    lc = (df["ema12"]>df["ema26"]) & (df["adx"]>25) & obv_up & (df["rsi"]<70)
    sc = (df["ema12"]<df["ema26"]) & (df["adx"]>25) & obv_dn & (df["rsi"]>30)
    df["signal"]   = np.select([lc, sc], [1, -1], default=0)
    df["sig_edge"] = (df["signal"]!=0) & (df["signal"]!=df["signal"].shift(1))

    # Targets
    df["tgt_long"]   = df["close"] + 2.0*df["atr"]
    df["tgt_short"]  = df["close"] - 2.0*df["atr"]
    df["stop_long"]  = df["close"] - 1.0*df["atr"]
    df["stop_short"] = df["close"] + 1.0*df["atr"]
    dv = df["hv"] / np.sqrt(252)
    df["hv_up5"] = df["close"] * (1 + dv*np.sqrt(5))
    df["hv_dn5"] = df["close"] * (1 - dv*np.sqrt(5))

    df.dropna(inplace=True)

    # Risk metrics
    r   = df["close"].pct_change().dropna()
    cum = (1+r).cumprod()
    dd  = (cum-cum.cummax())/cum.cummax()
    ar  = float(cum.iloc[-1]**(252/len(r)) - 1)
    av  = float(r.std()*np.sqrt(252))
    ds  = float(r[r<0].std()*np.sqrt(252))
    mdd = float(dd.min())
    metrics = {
        "annual_return": ar,
        "annual_vol":    av,
        "sharpe":        ar/av       if av  else 0.0,
        "sortino":       ar/ds       if ds  else 0.0,
        "calmar":        ar/abs(mdd) if mdd else 0.0,
        "max_drawdown":  mdd,
    }
    return df, metrics, stock_name, currency

# ══════════════════════════════════════════════
# AI ANALYSIS — Gemini 1.5 Flash (free 1500/day)
# ══════════════════════════════════════════════

_USAGE_FILE  = os.path.join(_data_dir(), "ai_usage.json")
_DAILY_LIMIT = 1500
_usage_lock  = threading.Lock()

def _load_usage() -> dict:
    today = datetime.now(pytz.timezone("Asia/Seoul")).strftime("%Y-%m-%d")
    try:
        with open(_USAGE_FILE) as f:
            d = json.load(f)
        if d.get("date") != today:
            return {"date": today, "count": 0}
        return d
    except Exception:
        return {"date": today, "count": 0}

def _save_usage(d: dict):
    with open(_USAGE_FILE, "w") as f:
        json.dump(d, f)

def _get_usage() -> dict:
    d    = _load_usage()
    used = d.get("count", 0)
    rem  = max(0, _DAILY_LIMIT - used)
    return {
        "used":      used,
        "limit":     _DAILY_LIMIT,
        "remaining": rem,
        "pct":       round(used / _DAILY_LIMIT * 100, 1),
        "date":      d.get("date"),
    }

def _increment_usage():
    with _usage_lock:
        d = _load_usage()
        d["count"] = d.get("count", 0) + 1
        _save_usage(d)

def ai_analyze(ticker: str, df: pd.DataFrame, rec: dict,
               stock_name: str, currency: str,
               api_key_override: str = "") -> dict:
    # 우선순위: 요청 헤더 > 환경변수
    api_key = (api_key_override or os.environ.get("GEMINI_API_KEY", "")).strip()
    if not api_key:
        return {"error": "Gemini API 키가 없습니다. 설정(⚙)에서 키를 입력하거나 GEMINI_API_KEY 환경변수를 설정하세요."}

    u = _get_usage()
    if u["remaining"] <= 0:
        return {"error": f"일일 사용량 초과 ({_DAILY_LIMIT}회/일). 내일 자정 리셋.", "usage": u}

    sym  = rec["sym"]
    last = df.iloc[-1]

    def fp(v):
        return f"{sym}{v:,.0f}" if currency == "KRW" else f"{sym}{v:.2f}"

    recent_lines = "\n".join(
        f"  {idx.strftime('%m/%d')}: {fp(row['close'])} (거래량 {row['volume']:,.0f})"
        for idx, row in df.tail(5)[["close", "volume"]].iterrows()
    )
    ema_cross = ("골든크로스(상승추세)" if float(last["ema12"]) > float(last["ema26"])
                 else "데드크로스(하락추세)")

    prompt = (
        f"당신은 주식 기술적 분석 전문가입니다. 아래 데이터를 분석해 JSON으로만 답하세요.\n\n"
        f"종목: {stock_name} ({ticker}) / 현재가: {rec['close_fmt']} / 날짜: {rec['date']}\n\n"
        f"[기술 지표]\n"
        f"RSI(14): {rec['rsi']} | ADX(14): {rec['adx']} | HV: {rec['hv_pct']}% | ATR: {rec['atr_fmt']}\n"
        f"EMA: {ema_cross} | 퀀트시그널: {rec['action']} — {rec['watch_reason']}\n\n"
        f"[최근 5일]\n{recent_lines}\n\n"
        f"[1년 수익률]\n"
        f"연환산수익률: {rec['annual_return']}% | 연변동성: {rec['annual_vol']}% | "
        f"샤프: {rec['sharpe']} | MDD: {rec['max_drawdown']}%\n\n"
        f'JSON 형식 (이것만 출력):\n'
        f'{{"bull_case":["근거1","근거2","근거3"],'
        f'"bear_case":["리스크1","리스크2"],'
        f'"verdict":"1~2문장 종합판단",'
        f'"confidence":"높음|중간|낮음",'
        f'"time_horizon":"단기(1-2주)|중기(1-3개월)|장기(3개월+)"}}'
    )

    try:
        url  = ("https://generativelanguage.googleapis.com/v1beta"
                f"/models/gemini-1.5-flash:generateContent?key={api_key}")
        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.3, "maxOutputTokens": 512},
        }
        resp = requests.post(url, json=body, timeout=20)
        resp.raise_for_status()
        text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        m    = re.search(r'\{[\s\S]+\}', text)
        if not m:
            raise ValueError("JSON 파싱 실패")
        result = json.loads(m.group())
        _increment_usage()
        result["usage"] = _get_usage()
        return result
    except requests.HTTPError as e:
        return {"error": f"Gemini API 오류 {e.response.status_code}", "usage": _get_usage()}
    except Exception as e:
        return {"error": str(e), "usage": _get_usage()}


# ══════════════════════════════════════════════
# RECOMMENDATION
# ══════════════════════════════════════════════

def recommend(df, metrics, currency):
    last    = df.iloc[-1]
    signal  = int(last["signal"])
    close   = float(last["close"])
    atr_v   = float(last["atr"])
    rsi_v   = float(last["rsi"])
    adx_v   = float(last["adx"])
    hv_v    = float(last["hv"])
    today   = df.index[-1]
    ema_gap = abs(float(last["ema12"])-float(last["ema26"]))/close*100

    sym = "₩" if currency == "KRW" else "$"

    if signal == 1:
        action, watch_days = "BUY", 0
        watch_reason = "3-조건 매수 시그널 활성 (EMA골든크로스 + ADX>25 + OBV↑ + RSI<70)"
    elif signal == -1:
        action, watch_days = "SELL", 0
        watch_reason = "3-조건 매도 시그널 활성 (EMA데드크로스 + ADX>25 + OBV↓ + RSI>30)"
    else:
        action = "WAIT"
        if adx_v >= 25:
            watch_days = 2 if ema_gap < 0.5 else 3
            watch_reason = ("EMA12/26 교차 임박 — 크로스 확인 후 진입" if ema_gap < 0.5
                            else f"ADX {adx_v:.1f} 트렌드 존재, EMA 방향 전환 대기")
        elif adx_v >= 20:
            watch_days = 3
            watch_reason = f"ADX {adx_v:.1f} 상승 중 — 트렌드 형성 초기"
        elif rsi_v > 65:
            watch_days = 5
            watch_reason = f"RSI {rsi_v:.1f} 과매수 — 조정 후 진입 대기"
        elif rsi_v < 35:
            watch_days = 3
            watch_reason = f"RSI {rsi_v:.1f} 과매도 — 반등 캔들 확인 후 진입"
        else:
            watch_days = 5
            watch_reason = f"ADX {adx_v:.1f} 낮음 — 방향성 형성까지 관망"

    watch_until = ((today + pd.offsets.BDay(watch_days)).strftime("%Y-%m-%d")
                   if watch_days > 0 else "오늘 진입 검토")

    def fmt(v): return f"{sym}{v:,.0f}" if currency == "KRW" else f"{sym}{v:.2f}"

    be = round(close - 0.5*atr_v, 2); bt = round(close + 2.0*atr_v, 2); bs = round(close - 1.0*atr_v, 2)
    se = round(close + 0.5*atr_v, 2); st = round(close - 2.0*atr_v, 2); ss = round(close + 1.0*atr_v, 2)
    brr = round((bt-be)/(be-bs), 2) if (be-bs) > 0 else 0
    srr = round((se-st)/(ss-se), 2) if (ss-se) > 0 else 0
    dv = hv_v/np.sqrt(252)

    return {
        "action": action, "signal": signal,
        "watch_days": watch_days, "watch_until": watch_until,
        "watch_reason": watch_reason,
        "date": today.strftime("%Y-%m-%d"),
        "close": round(close, 2), "close_fmt": fmt(close),
        "rsi": round(rsi_v,1), "adx": round(adx_v,1),
        "hv_pct": round(hv_v*100,1), "atr": round(atr_v,2),
        "atr_fmt": fmt(atr_v), "currency": currency, "sym": sym,
        "buy_entry": be, "buy_entry_fmt": fmt(be),
        "buy_target": bt, "buy_target_fmt": fmt(bt),
        "buy_stop": bs, "buy_stop_fmt": fmt(bs),
        "buy_rr": brr,
        "buy_tgt_pct": round((bt-close)/close*100,1),
        "buy_stop_pct": round((bs-close)/close*100,1),
        "sell_entry": se, "sell_entry_fmt": fmt(se),
        "sell_target": st, "sell_target_fmt": fmt(st),
        "sell_stop": ss, "sell_stop_fmt": fmt(ss),
        "sell_rr": srr,
        "sell_tgt_pct": round((st-close)/close*100,1),
        "sell_stop_pct": round((ss-close)/close*100,1),
        "hv_up5": round(close*(1+dv*np.sqrt(5)),2),
        "hv_up5_fmt": fmt(round(close*(1+dv*np.sqrt(5)),2)),
        "hv_dn5": round(close*(1-dv*np.sqrt(5)),2),
        "hv_dn5_fmt": fmt(round(close*(1-dv*np.sqrt(5)),2)),
        "annual_return": round(metrics["annual_return"]*100,1),
        "annual_vol":    round(metrics["annual_vol"]*100,1),
        "sharpe":        round(metrics["sharpe"],2),
        "sortino":       round(metrics["sortino"],2),
        "calmar":        round(metrics["calmar"],2),
        "max_drawdown":  round(metrics["max_drawdown"]*100,1),
    }

# ══════════════════════════════════════════════
# CHART
# ══════════════════════════════════════════════

G="#3fb950"; R="#f85149"; B="#58a6ff"; Y="#e3b341"; P="#bc8cff"; GR="#8b949e"

def make_chart(df, ticker, stock_name, currency):
    buy_idx  = df.index[df["sig_edge"] & (df["signal"]==1)]
    sell_idx = df.index[df["sig_edge"] & (df["signal"]==-1)]
    sym = "₩" if currency == "KRW" else "$"

    fig = make_subplots(
        rows=4, cols=1, shared_xaxes=True,
        row_heights=[0.52,0.16,0.16,0.16],
        vertical_spacing=0.02,
        subplot_titles=["가격 · 시그널 · 목표가","거래량 / OBV","RSI (14)","ADX / ±DI (14)"],
    )

    fig.add_trace(go.Candlestick(
        x=df.index, open=df["open"], high=df["high"],
        low=df["low"], close=df["close"], name="Price",
        increasing=dict(line=dict(color=G), fillcolor=G),
        decreasing=dict(line=dict(color=R), fillcolor=R), showlegend=False,
    ), row=1, col=1)

    fig.add_trace(go.Scatter(x=df.index, y=df["bb_upper"], name="BB Upper",
        line=dict(color="rgba(88,166,255,0.35)",width=1,dash="dot"), showlegend=False), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["bb_lower"], name="BB Lower",
        fill="tonexty", fillcolor="rgba(88,166,255,0.06)",
        line=dict(color="rgba(88,166,255,0.35)",width=1,dash="dot"), showlegend=False), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["bb_mid"],
        line=dict(color="rgba(139,148,158,0.5)",width=1), name="BB Mid", showlegend=False), row=1, col=1)

    for cn, lbl, c in [("ema12","EMA 12",Y),("ema26","EMA 26",R),
                        ("ema50","EMA 50",GR),("sma200","SMA 200",P)]:
        fig.add_trace(go.Scatter(x=df.index, y=df[cn], name=lbl,
            line=dict(color=c,width=1.4)), row=1, col=1)

    if len(buy_idx):
        fig.add_trace(go.Scatter(x=buy_idx, y=df.loc[buy_idx,"low"]*0.988,
            mode="markers", name="BUY",
            marker=dict(symbol="triangle-up",color=G,size=13,
                        line=dict(color="white",width=1))), row=1, col=1)
    if len(sell_idx):
        fig.add_trace(go.Scatter(x=sell_idx, y=df.loc[sell_idx,"high"]*1.012,
            mode="markers", name="SELL",
            marker=dict(symbol="triangle-down",color=R,size=13,
                        line=dict(color="white",width=1))), row=1, col=1)

    def fp(v):  # format price for chart label
        return f"{sym}{v:,.0f}" if currency == "KRW" else f"{sym}{v:.2f}"

    last = df.iloc[-1]; last_dt = df.index[-1]; fwd_dt = last_dt + pd.offsets.BDay(5)

    # 레이블 최소 간격 = 현재가의 7% (10px 폰트 기준 ~48px 확보)
    close_p = float(last["close"])
    min_gap = close_p * 0.07

    ann_items = [
        (float(last["tgt_long"]),  f"목표↑ {fp(last['tgt_long'])}",  G),
        (float(last["hv_up5"]),    f"HV+1σ {fp(last['hv_up5'])}",   "#39d353"),
        (float(last["hv_dn5"]),    f"HV-1σ {fp(last['hv_dn5'])}",   "#da3633"),
        (float(last["tgt_short"]), f"목표↓ {fp(last['tgt_short'])}", R),
    ]
    ann_items.sort(key=lambda x: x[0], reverse=True)   # 높은 값 → 낮은 값

    # 위→아래 단순 패스: adj[i] 가 adj[i-1] 보다 min_gap 이상 낮도록 강제
    adj_vals = [item[0] for item in ann_items]
    for i in range(1, len(adj_vals)):
        required = adj_vals[i - 1] - min_gap
        if adj_vals[i] > required:          # 간격 부족 → 아래로 밀기
            adj_vals[i] = required

    for (yval, lbl, c), adj in zip(ann_items, adj_vals):
        # 기준선은 실제 가격에 점선
        fig.add_shape(type="line", x0=last_dt, x1=fwd_dt, y0=yval, y1=yval,
            line=dict(color=c, width=1.5, dash="dot"), xref="x", yref="y", row=1, col=1)
        # 레이블은 adj 위치 (간격 보장)
        fig.add_annotation(x=fwd_dt, y=adj, text=f" {lbl}",
            showarrow=False, xanchor="left", font=dict(size=10, color=c),
            xref="x", yref="y", row=1, col=1)

    bar_c = [G if c>=o else R for c,o in zip(df["close"],df["open"])]
    fig.add_trace(go.Bar(x=df.index, y=df["volume"], marker_color=bar_c,
        opacity=0.45, name="Volume", showlegend=False), row=2, col=1)
    obv_s = df["obv"]
    obv_n = (obv_s-obv_s.min())/(obv_s.max()-obv_s.min()+1e-9)*df["volume"].max()
    fig.add_trace(go.Scatter(x=df.index, y=obv_n,
        line=dict(color=P,width=1.5), name="OBV (norm)"), row=2, col=1)

    fig.add_trace(go.Scatter(x=df.index, y=df["rsi"],
        line=dict(color=B,width=1.5), name="RSI", showlegend=False), row=3, col=1)
    for lvl, c in [(70,R),(50,GR),(30,G)]:
        fig.add_hline(y=lvl, line=dict(color=c,width=0.8,dash="dash"), row=3, col=1)
    fig.add_hrect(y0=70, y1=100, fillcolor="rgba(248,81,73,0.06)", line_width=0, row=3, col=1)
    fig.add_hrect(y0=0,  y1=30,  fillcolor="rgba(63,185,80,0.06)",  line_width=0, row=3, col=1)

    for cn, lbl, c, w in [("adx","ADX",Y,2.0),("+di","+DI",G,1.2),("-di","-DI",R,1.2)]:
        fig.add_trace(go.Scatter(x=df.index, y=df[cn], name=lbl,
            line=dict(color=c,width=w)), row=4, col=1)
    fig.add_hline(y=25, line=dict(color="white",width=0.8,dash="dot"), row=4, col=1)

    fig.update_layout(
        template="plotly_dark", paper_bgcolor="#0d1117", plot_bgcolor="#161b22",
        height=680, xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                    font=dict(size=11)),
        margin=dict(l=60, r=200, t=35, b=30),
        hovermode="x unified",
    )
    for row in range(1,5):
        fig.update_xaxes(gridcolor="rgba(48,54,61,0.6)", showspikes=True,
                         spikecolor=GR, spikethickness=1, row=row, col=1)
        fig.update_yaxes(gridcolor="rgba(48,54,61,0.8)", row=row, col=1)
    fig.update_yaxes(title_text=f"가격 ({currency})", row=1, col=1)
    fig.update_yaxes(title_text="거래량", row=2, col=1)
    fig.update_yaxes(title_text="RSI", range=[0,100], row=3, col=1)
    fig.update_yaxes(title_text="ADX/DI", row=4, col=1)
    return fig

# ══════════════════════════════════════════════
# ROUTES
# ══════════════════════════════════════════════

@app.route("/")
def index():
    return send_file(_resource_path("landing.html"))

@app.route("/dashboard")
def dashboard():
    return send_file(_resource_path("dashboard.html"))

def _market_meta(korean: bool, df: pd.DataFrame) -> dict:
    """데이터 소스 · 지연 · 장 상태 · API 한도 메타 정보 생성"""
    now_utc = datetime.now(pytz.utc)
    kst = pytz.timezone("Asia/Seoul")
    now_kst = now_utc.astimezone(kst)

    last_dt = df.index[-1]
    if hasattr(last_dt, "strftime"):
        data_last = last_dt.strftime("%Y-%m-%d")
    else:
        data_last = str(last_dt)[:10]

    fetched_at = now_kst.strftime("%Y-%m-%d %H:%M:%S KST")

    if korean:
        # 한국 장: 평일 09:00-15:30 KST
        wd = now_kst.weekday()
        h, m = now_kst.hour, now_kst.minute
        market_open = wd < 5 and ((h == 9 and m >= 0) or (9 < h < 15) or (h == 15 and m < 30))
        return {
            "source":       "네이버 금융",
            "source_url":   "finance.naver.com",
            "delay":        "실시간 (장중 1분봉 기반 일봉)",
            "limit":        "무료 · 일 제한 없음 · 최근 300일",
            "market_open":  market_open,
            "market_label": "한국 장 " + ("개장 중" if market_open else "마감"),
            "market_hours": "평일 09:00 – 15:30 KST",
            "data_last":    data_last,
            "fetched_at":   fetched_at,
            "data_note":    "일봉 종가 기준",
        }
    else:
        # 미국 장: 평일 09:30-16:00 ET
        et = pytz.timezone("America/New_York")
        now_et = now_utc.astimezone(et)
        wd = now_et.weekday()
        h, m = now_et.hour, now_et.minute
        pre  = wd < 5 and ((h == 4) or (5 <= h < 9) or (h == 9 and m < 30))
        main = wd < 5 and ((h == 9 and m >= 30) or (10 <= h < 16))
        post = wd < 5 and (16 <= h < 20)
        if main:
            market_label = "미국 장 개장 중"
            delay        = "15분 지연 (장중)"
        elif pre:
            market_label = "프리마켓"
            delay        = "프리마켓 데이터"
        elif post:
            market_label = "애프터마켓"
            delay        = "애프터마켓 데이터"
        else:
            market_label = "미국 장 마감"
            delay        = "전 거래일 종가"
        return {
            "source":       "Yahoo Finance (yfinance)",
            "source_url":   "finance.yahoo.com",
            "delay":        delay,
            "limit":        "무료 · 비공식 ~2,000회/시간 · 초과 시 빈 데이터",
            "market_open":  main,
            "market_label": market_label,
            "market_hours": "평일 09:30 – 16:00 ET (한국 22:30 – 05:00 KST)",
            "data_last":    data_last,
            "fetched_at":   fetched_at,
            "data_note":    "일봉 · 1년치 (약 252 거래일)",
        }


@app.route("/api/analyze")
def analyze():
    ticker = request.args.get("ticker", "").strip().upper()
    if not ticker:
        return jsonify({"error": "티커를 입력해주세요"}), 400

    display_ticker = ticker

    try:
        df, metrics, stock_name, currency = build(ticker)
        rec  = recommend(df, metrics, currency)
        fig  = make_chart(df, ticker, stock_name, currency)
        meta     = _market_meta(is_korean(ticker), df)
        analyst  = None if is_korean(ticker) else fetch_analyst(ticker)
        return jsonify({
            "ticker":         display_ticker,
            "stock_name":     stock_name,
            "currency":       currency,
            "figure":         json.loads(fig.to_json()),
            "recommendation": rec,
            "meta":           meta,
            "analyst":        analyst,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ══════════════════════════════════════════════
# SCANNER HELPERS
# ══════════════════════════════════════════════

def _finviz_get(url: str) -> str:
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
               "AppleWebKit/537.36 Chrome/124.0 Safari/537.36"}
    return requests.get(url, headers=headers, timeout=(4, 12)).text


def _parse_screener_tickers(html: str, limit: int = 20) -> list:
    """Finviz 스크리너에서 티커 목록 추출"""
    tickers = list(dict.fromkeys(re.findall(r'quote\.ashx\?t=([A-Z]{1,6})', html)))
    return tickers[:limit]


def _finviz_snapshot(ticker: str) -> dict:
    """Finviz 종목 스냅샷 데이터 조회"""
    html = _finviz_get(f"https://finviz.com/quote.ashx?t={ticker}&p=d")
    rows = re.findall(r'<td[^>]*class="[^"]*snapshot[^"]*"[^>]*>(.*?)</td>', html, re.DOTALL)
    clean = [re.sub(r"<[^>]+>", "", x).strip() for x in rows]
    pairs = {clean[i]: clean[i + 1] for i in range(0, len(clean) - 1, 2)}
    # 회사명 추출
    company = ""
    m = re.search(r'<h2[^>]*>\s*<a[^>]*>([^<]+)</a>', html)
    if m:
        company = m.group(1).strip()
    return {
        "company":    company,
        "sector":     pairs.get("Sector", ""),
        "industry":   pairs.get("Industry", ""),
        "market_cap": pairs.get("Market Cap", ""),
        "price":      pairs.get("Price", ""),
        "change":     pairs.get("Change", ""),
        "volume":     pairs.get("Volume", ""),
        "recom":      pairs.get("Recom", ""),
        "target":     pairs.get("Target Price", ""),
        "analysts":   pairs.get("Analyst Recom", ""),
    }


# Curated disruptive tickers by theme
_DISRUPTIVE = {
    "AI·데이터":     ["NVDA", "PLTR", "AI", "PATH", "SOUN"],
    "바이오·게놈":   ["RXRX", "CRSP", "BEAM", "EDIT", "PACB"],
    "에너지전환":    ["ENPH", "PLUG", "FCEL", "RUN",  "ARRY"],
    "블록체인·핀테크":["COIN", "HOOD", "AFRM","MSTR", "PYPL"],
    "로봇·우주":     ["IONQ", "JOBY", "RKLB", "ACHR", "TRMB"],
}


# ══════════════════════════════════════════════
# SCANNER ROUTES
# ══════════════════════════════════════════════

@app.route("/api/ai-usage")
def route_ai_usage():
    """Gemini 일일 사용량 조회"""
    return jsonify(_get_usage())


@app.route("/api/ai-analysis")
def route_ai_analysis():
    """AI 시그널 분석 — Gemini 1.5 Flash"""
    ticker = request.args.get("ticker", "").strip().upper()
    if not ticker:
        return jsonify({"error": "ticker required"}), 400
    try:
        df, metrics, stock_name, currency = build(ticker)
        rec    = recommend(df, metrics, currency)
        key_override = request.headers.get("X-Gemini-Key", "")
        result = ai_analyze(ticker, df, rec, stock_name, currency, key_override)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/price")
def get_price():
    """알림 폴링용 빠른 가격 조회"""
    ticker = request.args.get("ticker", "").strip().upper()
    if not ticker:
        return jsonify({"error": "ticker required"}), 400
    try:
        if is_korean(ticker):
            df = fetch_naver(parse_korean_code(ticker))
            price = float(df["close"].iloc[-1])
        else:
            with ThreadPoolExecutor(max_workers=1) as ex:
                raw = ex.submit(
                    lambda: yf.Ticker(ticker).history(period="2d", interval="1d", auto_adjust=True)
                ).result(timeout=8)
            price = float(raw["Close"].iloc[-1]) if len(raw) > 0 else None
        return jsonify({"ticker": ticker, "price": price})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/scan/smallcap")
def scan_smallcap():
    """소형주 스캐너 — 시총 $300M-$2B, 분기 매출증가 >25%, 애널리스트 매수 추천"""
    try:
        html    = _finviz_get(
            "https://finviz.com/screener.ashx?v=111"
            "&f=cap_small,fa_salesqoq_o25,an_recom_buybetter&o=-volume"
        )
        tickers = _parse_screener_tickers(html, limit=15)
        results = []
        for t in tickers:
            try:
                snap = _finviz_snapshot(t)
                snap["ticker"] = t
                results.append(snap)
            except Exception:
                results.append({"ticker": t})
        return jsonify({"results": results})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/scan/insider")
def scan_insider():
    """내부자 매수 스캐너 — Finviz 최근 Buy 거래"""
    try:
        html = _finviz_get(
            "https://finviz.com/insidertrading.ashx?tc=1&o=-transdate"
        )
        results = []
        # quote.ashx 링크를 포함한 tr 행만 추출
        all_rows = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.DOTALL)
        for row in all_rows:
            t_match = re.search(r'quote\.ashx\?t=([A-Z]{1,6})', row)
            if not t_match:
                continue
            ticker = t_match.group(1)
            # data-boxover-company 속성에서 기업명 추출
            co_match = re.search(r'data-boxover-company="([^"]+)"', row)
            company = co_match.group(1) if co_match else ""
            cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
            c = [re.sub(r'<[^>]+>', '', x).strip() for x in cells]
            # 구조: [0]=ticker [1]=insider [2]=relation [3]=date [4]=type [5]=price [6]=shares [7]=value
            if len(c) >= 5 and c[4].lower() == "buy":
                results.append({
                    "ticker":   ticker,
                    "company":  company,
                    "insider":  c[1] if len(c) > 1 else "",
                    "relation": c[2] if len(c) > 2 else "",
                    "date":     c[3] if len(c) > 3 else "",
                    "type":     c[4] if len(c) > 4 else "",
                    "cost":     c[5] if len(c) > 5 else "",
                    "shares":   c[6] if len(c) > 6 else "",
                    "value":    c[7] if len(c) > 7 else "",
                })
        return jsonify({"results": results[:30]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/scan/disruptive")
def scan_disruptive():
    """혁신주 스캐너 — 테마별 큐레이션 + 실시간 가격"""
    try:
        all_tickers = [t for tickers in _DISRUPTIVE.values() for t in tickers]
        # 멀티 ticker 한 번에 조회
        with ThreadPoolExecutor(max_workers=1) as ex:
            raw = ex.submit(
                lambda: yf.download(all_tickers, period="2d", interval="1d",
                                    auto_adjust=True, progress=False)
            ).result(timeout=15)

        def _price(ticker):
            try:
                if isinstance(raw.columns, pd.MultiIndex):
                    s = raw["Close"][ticker].dropna()
                else:
                    s = raw["Close"].dropna()
                if len(s) < 1:
                    return None, None
                close = float(s.iloc[-1])
                chg = float((s.iloc[-1] - s.iloc[-2]) / s.iloc[-2] * 100) if len(s) > 1 else 0
                return round(close, 2), round(chg, 2)
            except Exception:
                return None, None

        results = {}
        for theme, tickers in _DISRUPTIVE.items():
            theme_list = []
            for t in tickers:
                price, chg = _price(t)
                theme_list.append({"ticker": t, "price": price, "change": chg})
            results[theme] = theme_list

        return jsonify({"results": results})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ══════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════

if __name__ == "__main__":
    url = "http://localhost:5001"
    print(f"[→] ZeroKey Quant  →  {url}")
    print(f"    미국 주식: AAPL TSLA NVDA")
    print(f"    한국 주식: 005930 (삼성전자) 035420 (네이버)")
    print(f"    Ctrl+C 로 종료\n")
    threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    app.run(debug=False, port=5001, use_reloader=False, threaded=True)
