"""
종목 검색 서비스 — 미국 / 한국 / 홍콩 / 상해 시장 지원
"""

import csv
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


# ===================================================
# KRX 종목 데이터 (한국)
# ===================================================
@lru_cache(maxsize=1)
def _load_krx_stocks() -> list[dict]:
    """KRX 전종목 CSV 로드 (캐싱)"""
    csv_path = DATA_DIR / "krx_stocks.csv"
    if not csv_path.exists():
        return []
    stocks = []
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            stocks.append(
                {
                    "code": row.get("code", "").strip(),
                    "name": row.get("name", "").strip(),
                    "name_en": row.get("name_en", "").strip(),
                    "market": row.get("market", "KOSPI").strip(),
                }
            )
    return stocks


def search_kr(query: str, limit: int = 15) -> list[dict]:
    """한국 종목 검색 (한글명 + 영문명 + 코드 부분 매칭, yfinance fallback)"""
    stocks = _load_krx_stocks()
    query_lower = query.lower()
    results = []
    for s in stocks:
        # 한글명, 영문명, 코드 모두로 부분 매칭
        if (
            query_lower in s["name"].lower()
            or query_lower in s["name_en"].lower()
            or query_lower in s["code"]
        ):
            suffix = ".KS" if s["market"] == "KOSPI" else ".KQ"
            results.append(
                {
                    "symbol": s["code"] + suffix,
                    "name": s["name"],
                    "name_en": s["name_en"],
                    "market": "KR",
                }
            )
            if len(results) >= limit:
                break

    # 로컬 매칭 결과 부족 시 yfinance fallback (영문 검색)
    if len(results) < 3 and len(query) >= 2:
        try:
            import yfinance as yf

            sr = yf.Search(query)
            quotes = sr.quotes if hasattr(sr, "quotes") else []
            seen = {r["symbol"] for r in results}
            for q in quotes[:limit]:
                if not isinstance(q, dict):
                    continue
                sym = q.get("symbol", "")
                if (sym.endswith(".KS") or sym.endswith(".KQ")) and sym not in seen:
                    results.append(
                        {
                            "symbol": sym,
                            "name": q.get("shortname") or q.get("longname") or sym,
                            "name_en": q.get("longname") or q.get("shortname") or "",
                            "market": "KR",
                        }
                    )
                    seen.add(sym)
                    if len(results) >= limit:
                        break
        except Exception:
            pass

    return results


# ===================================================
# 홍콩 종목 (yfinance Search API)
# ===================================================
def search_hk(query: str, limit: int = 10) -> list[dict]:
    """홍콩 종목 검색 — yfinance Search API"""
    import yfinance as yf

    try:
        search_result = yf.Search(query)
        quotes = search_result.quotes if hasattr(search_result, "quotes") else []
        results = []
        for q in quotes[: limit * 2]:
            if not isinstance(q, dict):
                continue
            symbol = q.get("symbol", "")
            name = q.get("shortname") or q.get("longname") or symbol
            exchange = q.get("exchange", "")
            # 홍콩 거래소 필터 (.HK 심볼 또는 HKG 거래소)
            if symbol.endswith(".HK") or "HKG" in exchange.upper():
                results.append(
                    {
                        "symbol": symbol if symbol.endswith(".HK") else symbol + ".HK",
                        "name": name,
                        "market": "HK",
                    }
                )
                if len(results) >= limit:
                    break
        return results
    except Exception:
        return []


# ===================================================
# 상해 종목 (yfinance Search API)
# ===================================================
def search_sh(query: str, limit: int = 10) -> list[dict]:
    """상해 종목 검색 — yfinance Search API"""
    import yfinance as yf

    try:
        search_result = yf.Search(query)
        quotes = search_result.quotes if hasattr(search_result, "quotes") else []
        results = []
        for q in quotes[: limit * 2]:
            if not isinstance(q, dict):
                continue
            symbol = q.get("symbol", "")
            name = q.get("shortname") or q.get("longname") or symbol
            exchange = q.get("exchange", "")
            # 상해 거래소 필터 (.SS 심볼 또는 SHH/SHZ 거래소)
            if symbol.endswith(".SS") or "SHH" in exchange.upper() or "SHZ" in exchange.upper():
                results.append(
                    {
                        "symbol": symbol if symbol.endswith(".SS") else symbol + ".SS",
                        "name": name,
                        "market": "SH",
                    }
                )
                if len(results) >= limit:
                    break
        return results
    except Exception:
        return []


# ===================================================
# 미국 종목 (yfinance search 활용)
# ===================================================
def search_us(query: str, limit: int = 10) -> list[dict]:
    """미국 종목 검색 — yfinance screener 활용"""
    import yfinance as yf

    try:
        search_result = yf.Search(query)
        quotes = search_result.quotes if hasattr(search_result, "quotes") else []
        results = []
        for q in quotes[:limit]:
            if not isinstance(q, dict):
                continue
            symbol = q.get("symbol", "")
            name = q.get("shortname") or q.get("longname") or symbol
            exchange = q.get("exchange", "")
            # 미국 거래소만 필터
            if any(
                ex in exchange.upper() for ex in ["NMS", "NYQ", "NGM", "PCX", "BTS", "NAS", "NYS"]
            ):
                results.append(
                    {
                        "symbol": symbol,
                        "name": name,
                        "market": "US",
                    }
                )
        return results
    except Exception:
        return []


# ===================================================
# 통합 검색
# ===================================================
def search_stocks(query: str, market: str = "US", limit: int = 10) -> list[dict]:
    """시장별 종목 검색 — US / KR / HK / SH"""
    if not query or len(query) < 1:
        return []

    if market == "KR":
        return search_kr(query, limit)
    elif market == "HK":
        return search_hk(query, limit)
    elif market == "SH":
        return search_sh(query, limit)
    else:
        return search_us(query, limit)
