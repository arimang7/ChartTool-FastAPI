from typing import Optional

import numpy as np
import pandas as pd


def calc_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate common technical indicators: Bollinger Bands, RSI, and Volume Spikes.
    """
    if df.empty:
        return df

    # MultiIndex column handling (for yfinance)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    # Force numeric types
    for col in ["Open", "High", "Low", "Close", "Volume"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Bollinger Bands
    df["MA20"] = df["Close"].rolling(window=20).mean()
    df["STD20"] = df["Close"].rolling(window=20).std()
    df["Upper"] = df["MA20"] + (df["STD20"] * 2)
    df["Lower"] = df["MA20"] - (df["STD20"] * 2)

    # RSI
    delta = df["Close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df["RSI"] = 100 - (100 / (1 + rs))

    # Volume Spike Detection (2x average)
    df["Vol_MA20"] = df["Volume"].rolling(window=20).mean()
    df["Vol_Spike"] = df["Volume"].astype(float) > (df["Vol_MA20"].astype(float) * 2)

    return df


# ===================================================
# Harmonic Pattern (AB=CD) Detection
# ===================================================

FIBO_TABLE = {0.382: 2.618, 0.500: 2.000, 0.618: 1.618, 0.707: 1.414, 0.786: 1.272, 0.886: 1.130}


def _find_swing_points(close: np.ndarray, order: int = 5) -> list[dict]:
    """Detect swing highs and lows using a zigzag-like algorithm."""
    swings = []
    n = len(close)
    for i in range(order, n - order):
        # Swing High
        if all(close[i] > close[i - j] for j in range(1, order + 1)) and all(
            close[i] > close[i + j] for j in range(1, order + 1)
        ):
            swings.append({"idx": i, "price": float(close[i]), "type": "high"})
        # Swing Low
        elif all(close[i] < close[i - j] for j in range(1, order + 1)) and all(
            close[i] < close[i + j] for j in range(1, order + 1)
        ):
            swings.append({"idx": i, "price": float(close[i]), "type": "low"})
    return swings


def _alternating_swings(swings: list[dict]) -> list[dict]:
    """Remove consecutive swings of the same type to ensure an alternating array."""
    if not swings:
        return []
    result = [swings[0]]
    for s in swings[1:]:
        if s["type"] != result[-1]["type"]:
            result.append(s)
        else:
            if s["type"] == "high" and s["price"] > result[-1]["price"]:
                result[-1] = s
            elif s["type"] == "low" and s["price"] < result[-1]["price"]:
                result[-1] = s
    return result


def detect_abcd_pattern(df: pd.DataFrame) -> Optional[dict]:
    """
    Detect AB=CD patterns focusing on recent data (latter 50%).
    """
    if df is None or len(df) < 30:
        return None

    close = df["Close"].values.astype(float)
    dates = df.index
    n = len(close)

    start_idx = n // 2
    recent_close = close[start_idx:]
    swings = _find_swing_points(recent_close, order=3)

    for s in swings:
        s["idx"] = s["idx"] + start_idx
    swings = _alternating_swings(swings)

    if len(swings) < 4:
        return None

    best_pattern = None
    best_score = 0
    min_d_idx = int(n * 0.7)

    for i in range(len(swings) - 3):
        a, b, c, d = swings[i], swings[i + 1], swings[i + 2], swings[i + 3]

        if (
            a["type"] == "low"
            and b["type"] == "high"
            and c["type"] == "low"
            and d["type"] == "high"
        ):
            pattern_type = "bullish"
        elif (
            a["type"] == "high"
            and b["type"] == "low"
            and c["type"] == "high"
            and d["type"] == "low"
        ):
            pattern_type = "bearish"
        else:
            continue

        if d["idx"] < min_d_idx:
            continue

        ab = abs(b["price"] - a["price"])
        cd = abs(d["price"] - c["price"])
        if ab == 0:
            continue

        bc = abs(c["price"] - b["price"])
        c_retracement = bc / ab
        if not (0.35 <= c_retracement <= 0.92):
            continue

        ab_cd_ratio = cd / ab
        if not (0.8 <= ab_cd_ratio <= 1.25):
            continue

        closest_fibo = min(FIBO_TABLE.keys(), key=lambda x: abs(x - c_retracement))
        bc_extension = FIBO_TABLE[closest_fibo]

        # Recency-weighted score
        ratio_score = 1.0 - abs(1.0 - ab_cd_ratio)
        recency_score = d["idx"] / n
        score = ratio_score * 0.4 + recency_score * 0.6

        if score > best_score:
            best_score = score
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
                    {
                        "date": dates[a["idx"]].strftime("%Y-%m-%d"),
                        "price": round(a["price"], 2),
                        "label": "A",
                    },
                    {
                        "date": dates[b["idx"]].strftime("%Y-%m-%d"),
                        "price": round(b["price"], 2),
                        "label": "B",
                    },
                    {
                        "date": dates[c["idx"]].strftime("%Y-%m-%d"),
                        "price": round(c["price"], 2),
                        "label": "C",
                    },
                    {
                        "date": dates[d["idx"]].strftime("%Y-%m-%d"),
                        "price": round(d["price"], 2),
                        "label": "D",
                    },
                ],
                "prz": {"min": round(prz_min, 2), "max": round(prz_max, 2)},
                "c_retracement": round(c_retracement, 3),
                "bc_extension": round(bc_extension, 3),
                "ab_cd_ratio": round(ab_cd_ratio, 3),
                "confidence": round(best_score * 100, 1),
            }

    return best_pattern
