import os
import sys
from typing import Optional

import pandas as pd
import yfinance as yf

# Add project root to sys.path to allow importing from core
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from core.indicators import calc_technical_indicators, detect_abcd_pattern


def load_data(symbol: str, period: str) -> Optional[pd.DataFrame]:
    """주식 데이터 로드 및 기술적 지표 계산"""
    try:
        df = yf.download(symbol, period=period, interval="1d")
        if df.empty:
            return None

        # 기술적 지표 계산 (중앙 집중화된 로직 사용)
        df = calc_technical_indicators(df)

        return df
    except Exception as e:
        print(f"데이터 처리 중 오류 발생: {e}")
        return None


def df_to_chart_json(df: pd.DataFrame, symbol: str = "") -> dict:
    """DataFrame을 Plotly 차트용 JSON으로 변환"""
    dates = [d.strftime("%Y-%m-%d") for d in df.index]

    # NaN을 None으로 변환
    def safe_list(series):
        return [None if pd.isna(v) else round(float(v), 4) for v in series]

    # 볼륨 스파이크 날짜
    spike_dates = [d.strftime("%Y-%m-%d") for d in df[df["Vol_Spike"]].index]

    # 하모닉 패턴 탐지
    pattern = detect_abcd_pattern(df)

    # 종목명 조회
    company_name = symbol
    if symbol:
        try:
            info = yf.Ticker(symbol).info
            company_name = info.get("shortName") or info.get("longName") or symbol
        except Exception:
            pass

    return {
        "dates": dates,
        "open": safe_list(df["Open"]),
        "high": safe_list(df["High"]),
        "low": safe_list(df["Low"]),
        "close": safe_list(df["Close"]),
        "volume": safe_list(df["Volume"]),
        "upper": safe_list(df["Upper"]),
        "lower": safe_list(df["Lower"]),
        "ma20": safe_list(df["MA20"]),
        "rsi": safe_list(df["RSI"]),
        "vol_spike_dates": spike_dates,
        "current_price": round(float(df["Close"].iloc[-1]), 2),
        "current_rsi": round(float(df["RSI"].iloc[-1]), 2),
        "harmonic_pattern": pattern,
        "company_name": company_name,
    }


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

            content = item.get("content") or {}
            title = content.get("title") or item.get("title") or "제목 없음"

            click_url = content.get("clickThroughUrl") or {}
            link = click_url.get("url") or item.get("link") or "#"

            news_list.append({"title": title, "link": link})

        return news_list
    except Exception:
        return []
