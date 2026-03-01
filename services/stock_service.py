import yfinance as yf
import pandas as pd
import numpy as np
from typing import Optional


def load_data(symbol: str, period: str) -> Optional[pd.DataFrame]:
    """주식 데이터 로드 및 기술적 지표 계산"""
    try:
        df = yf.download(symbol, period=period, interval="1d")
        if df.empty:
            return None

        # MultiIndex 컬럼 처리: yfinance 최신 버전 대응
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # 데이터 타입 강제 변환
        for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')

        # 볼린저 밴드 계산
        df['MA20'] = df['Close'].rolling(window=20).mean()
        df['STD20'] = df['Close'].rolling(window=20).std()
        df['Upper'] = df['MA20'] + (df['STD20'] * 2)
        df['Lower'] = df['MA20'] - (df['STD20'] * 2)

        # RSI 계산
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))

        # 거래량 급증 판단 (평균 대비 2배 이상)
        df['Vol_MA20'] = df['Volume'].rolling(window=20).mean()
        df['Vol_Spike'] = df['Volume'].astype(float) > (df['Vol_MA20'].astype(float) * 2)

        return df
    except Exception as e:
        print(f"데이터 처리 중 오류 발생: {e}")
        return None


def load_news(symbol: str) -> list[dict]:
    """yfinance에서 뉴스 데이터 로드"""
    try:
        stock_info = yf.Ticker(symbol)
        news_data = stock_info.news
        if not news_data:
            return []

        news_list = []
        for item in news_data[:5]:
            if not isinstance(item, dict):
                continue

            content = item.get('content') or {}
            title = content.get('title') or item.get('title') or '제목 없음'

            click_url = content.get('clickThroughUrl') or {}
            link = click_url.get('url') or item.get('link') or '#'

            news_list.append({"title": title, "link": link})

        return news_list
    except Exception:
        return []


# ===================================================
# 하모닉 패턴 AB=CD 탐지
# ===================================================
def _find_swing_points(close: np.ndarray, order: int = 5) -> list[dict]:
    """지그재그 알고리즘으로 스윙 하이/로우 탐지"""
    swings = []
    n = len(close)
    for i in range(order, n - order):
        # Swing High: i가 좌우 order개 봉보다 높음
        if all(close[i] > close[i - j] for j in range(1, order + 1)) and \
           all(close[i] > close[i + j] for j in range(1, order + 1)):
            swings.append({"idx": i, "price": float(close[i]), "type": "high"})
        # Swing Low: i가 좌우 order개 봉보다 낮음
        elif all(close[i] < close[i - j] for j in range(1, order + 1)) and \
             all(close[i] < close[i + j] for j in range(1, order + 1)):
            swings.append({"idx": i, "price": float(close[i]), "type": "low"})
    return swings


def _alternating_swings(swings: list[dict]) -> list[dict]:
    """연속된 같은 타입 스윙 제거 → 교대 배열"""
    if not swings:
        return []
    result = [swings[0]]
    for s in swings[1:]:
        if s["type"] != result[-1]["type"]:
            result.append(s)
        else:
            # 같은 타입이면 더 극단적인 것으로 교체
            if s["type"] == "high" and s["price"] > result[-1]["price"]:
                result[-1] = s
            elif s["type"] == "low" and s["price"] < result[-1]["price"]:
                result[-1] = s
    return result


# C 되돌림 비율 → 대표 BC 확장 D 후보 매핑
FIBO_TABLE = {
    0.382: 2.618, 0.500: 2.000, 0.618: 1.618,
    0.707: 1.414, 0.786: 1.272, 0.886: 1.130
}


def detect_abcd_pattern(df: pd.DataFrame) -> Optional[dict]:
    """AB=CD 패턴 탐지 — 최근 데이터(후반 50%) 중심, 최적 패턴 반환"""
    if df is None or len(df) < 30:
        return None

    close = df['Close'].values.astype(float)
    dates = df.index
    n = len(close)

    # 후반 50% 구간에서만 스윙 탐지 (최근 데이터 중심)
    start_idx = n // 2
    recent_close = close[start_idx:]

    # order=3으로 축소하여 더 세밀한 스윙 포착
    swings = _find_swing_points(recent_close, order=3)
    # 인덱스를 전체 데이터 기준으로 보정
    for s in swings:
        s["idx"] = s["idx"] + start_idx
    swings = _alternating_swings(swings)

    if len(swings) < 4:
        return None

    best_pattern = None
    best_score = 0
    # D 포인트가 전체 데이터의 후반 30% 안에 있어야 채택
    min_d_idx = int(n * 0.7)

    # 최근 스윙부터 역순으로 탐색 (최근 패턴 우선)
    for i in range(len(swings) - 3):
        a, b, c, d = swings[i], swings[i + 1], swings[i + 2], swings[i + 3]

        # Bullish: A(low) → B(high) → C(low) → D(high)
        # Bearish: A(high) → B(low) → C(high) → D(low)
        if a["type"] == "low" and b["type"] == "high" and c["type"] == "low" and d["type"] == "high":
            pattern_type = "bullish"
        elif a["type"] == "high" and b["type"] == "low" and c["type"] == "high" and d["type"] == "low":
            pattern_type = "bearish"
        else:
            continue

        # D 포인트가 최근 30% 범위 안에 있는지 확인
        if d["idx"] < min_d_idx:
            continue

        ab = abs(b["price"] - a["price"])
        cd = abs(d["price"] - c["price"])

        if ab == 0:
            continue

        # C 되돌림 비율 계산
        bc = abs(c["price"] - b["price"])
        c_retracement = bc / ab

        # C 되돌림이 0.382~0.886 범위인지 확인
        if not (0.35 <= c_retracement <= 0.92):
            continue

        # AB ≈ CD 비율 확인 (±20% 허용)
        ab_cd_ratio = cd / ab
        if not (0.8 <= ab_cd_ratio <= 1.25):
            continue

        # 가장 가까운 피보나치 비율 찾기
        closest_fibo = min(FIBO_TABLE.keys(), key=lambda x: abs(x - c_retracement))
        bc_extension = FIBO_TABLE[closest_fibo]

        # 점수: recency 가중치 0.6으로 상향 (최근 패턴 우선)
        ratio_score = 1.0 - abs(1.0 - ab_cd_ratio)
        recency_score = d["idx"] / n
        score = ratio_score * 0.4 + recency_score * 0.6

        if score > best_score:
            best_score = score
            # PRZ 계산
            if pattern_type == "bullish":
                prz_target = c["price"] + bc * bc_extension
                prz_min = min(d["price"], prz_target) * 0.995
                prz_max = max(d["price"], prz_target) * 1.005
            else:
                prz_target = c["price"] - bc * bc_extension
                prz_min = min(d["price"], prz_target) * 0.995
                prz_max = max(d["price"], prz_target) * 1.005

            best_pattern = {
                "type": pattern_type,
                "points": [
                    {"date": dates[a["idx"]].strftime('%Y-%m-%d'), "price": round(a["price"], 2), "label": "A"},
                    {"date": dates[b["idx"]].strftime('%Y-%m-%d'), "price": round(b["price"], 2), "label": "B"},
                    {"date": dates[c["idx"]].strftime('%Y-%m-%d'), "price": round(c["price"], 2), "label": "C"},
                    {"date": dates[d["idx"]].strftime('%Y-%m-%d'), "price": round(d["price"], 2), "label": "D"},
                ],
                "prz": {"min": round(prz_min, 2), "max": round(prz_max, 2)},
                "c_retracement": round(c_retracement, 3),
                "bc_extension": round(bc_extension, 3),
                "ab_cd_ratio": round(ab_cd_ratio, 3),
                "confidence": round(best_score * 100, 1),
            }

    return best_pattern


def df_to_chart_json(df: pd.DataFrame, symbol: str = "") -> dict:
    """DataFrame을 Plotly 차트용 JSON으로 변환"""
    dates = [d.strftime('%Y-%m-%d') for d in df.index]

    # NaN을 None으로 변환
    def safe_list(series):
        return [None if pd.isna(v) else round(float(v), 4) for v in series]

    # 볼륨 스파이크 날짜
    spike_dates = [d.strftime('%Y-%m-%d') for d in df[df['Vol_Spike']].index]

    # 하모닉 패턴 탐지
    pattern = detect_abcd_pattern(df)

    # 종목명 조회
    company_name = symbol
    if symbol:
        try:
            info = yf.Ticker(symbol).info
            company_name = info.get('shortName') or info.get('longName') or symbol
        except Exception:
            pass

    return {
        "dates": dates,
        "open": safe_list(df['Open']),
        "high": safe_list(df['High']),
        "low": safe_list(df['Low']),
        "close": safe_list(df['Close']),
        "volume": safe_list(df['Volume']),
        "upper": safe_list(df['Upper']),
        "lower": safe_list(df['Lower']),
        "ma20": safe_list(df['MA20']),
        "rsi": safe_list(df['RSI']),
        "vol_spike_dates": spike_dates,
        "current_price": round(float(df['Close'].iloc[-1]), 2),
        "current_rsi": round(float(df['RSI'].iloc[-1]), 2),
        "harmonic_pattern": pattern,
        "company_name": company_name,
    }

