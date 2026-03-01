from fastapi import APIRouter, Query, HTTPException
from services.stock_service import load_data, load_news, df_to_chart_json
from services.search_service import search_stocks

router = APIRouter(prefix="/api/stock", tags=["stock"])


@router.get("/search")
async def search_ticker(
    q: str = Query(..., description="검색어 (종목명 또는 티커)"),
    market: str = Query("US", description="시장 (US, KR, HK)")
):
    """종목 검색 (자동완성)"""
    results = search_stocks(q, market)
    return {"results": results}


@router.get("/data")
async def get_stock_data(
    symbol: str = Query(..., description="종목 티커 (예: AAPL)"),
    period: str = Query("1y", description="조회 기간 (1mo, 3mo, 6mo, 1y, 2y)")
):
    """주식 데이터 + 기술적 지표 조회"""
    df = load_data(symbol, period)
    if df is None or df.empty:
        raise HTTPException(status_code=404, detail="데이터를 불러올 수 없습니다. 티커를 확인해주세요.")
    return df_to_chart_json(df, symbol=symbol)


@router.get("/news")
async def get_stock_news(
    symbol: str = Query(..., description="종목 티커")
):
    """종목 관련 뉴스 조회"""
    news = load_news(symbol)
    return {"news": news}
