import json
import time
import pandas as pd
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from services.stock_service import load_data
from services.analysis_service import run_ai_analysis, run_dcf_analysis

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


def _sse_event(event: str, data: dict) -> str:
    """SSE 이벤트 포맷"""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _prepare_latest_data(df, include_bands=False):
    """DataFrame에서 최신 데이터 추출"""
    latest = df.iloc[-1]
    data = {
        "current_price": float(latest['Close']),
        "current_rsi": float(latest['RSI']),
        "date": df.index[-1].strftime('%Y-%m-%d')
    }
    if include_bands:
        data["upper"] = float(latest['Upper']) if not pd.isna(latest['Upper']) else 0
        data["lower"] = float(latest['Lower']) if not pd.isna(latest['Lower']) else 0
    return data


@router.get("/ai/stream")
async def ai_analysis_stream(
    symbol: str = Query(...),
    period: str = Query("1y"),
    news_text: str = Query("")
):
    """AI 분석 — SSE 스트리밍 (단계별 진행)"""
    def generate():
        total_start = time.time()

        # Step 1: 데이터 로딩
        step_start = time.time()
        yield _sse_event("step", {"step": 1, "label": "주식 데이터 로딩 중...", "status": "running"})
        df = load_data(symbol, period)
        elapsed = round(time.time() - step_start, 1)
        if df is None or df.empty:
            yield _sse_event("error", {"message": "주식 데이터를 불러올 수 없습니다."})
            return
        yield _sse_event("step", {"step": 1, "label": "데이터 로딩 완료", "status": "done", "elapsed": elapsed})

        # Step 2: 데이터 준비
        step_start = time.time()
        yield _sse_event("step", {"step": 2, "label": "지표 계산 및 데이터 준비 중...", "status": "running"})
        latest_data = _prepare_latest_data(df, include_bands=True)
        elapsed = round(time.time() - step_start, 1)
        yield _sse_event("step", {"step": 2, "label": "데이터 준비 완료", "status": "done", "elapsed": elapsed})

        # Step 3: AI 모델 호출
        step_start = time.time()
        yield _sse_event("step", {"step": 3, "label": "Gemini AI 모델 호출 중...", "status": "running"})
        result = run_ai_analysis(latest_data, symbol, news_text)
        elapsed = round(time.time() - step_start, 1)
        yield _sse_event("step", {"step": 3, "label": "AI 분석 완료", "status": "done", "elapsed": elapsed})

        # Step 4: 완료
        total_elapsed = round(time.time() - total_start, 1)
        yield _sse_event("step", {"step": 4, "label": f"전체 분석 완료 ({total_elapsed}s)", "status": "done", "elapsed": total_elapsed})

        # 결과 전송
        result["total_elapsed"] = total_elapsed
        yield _sse_event("result", result)

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.get("/dcf/stream")
async def dcf_analysis_stream(
    symbol: str = Query(...),
    period: str = Query("1y")
):
    """DCF 분석 — SSE 스트리밍 (단계별 진행)"""
    def generate():
        total_start = time.time()

        # Step 1: 데이터 로딩
        step_start = time.time()
        yield _sse_event("step", {"step": 1, "label": "주식 데이터 로딩 중...", "status": "running"})
        df = load_data(symbol, period)
        elapsed = round(time.time() - step_start, 1)
        if df is None or df.empty:
            yield _sse_event("error", {"message": "주식 데이터를 불러올 수 없습니다."})
            return
        yield _sse_event("step", {"step": 1, "label": "데이터 로딩 완료", "status": "done", "elapsed": elapsed})

        # Step 2: 기업 정보 조회
        step_start = time.time()
        yield _sse_event("step", {"step": 2, "label": "기업 정보 조회 중...", "status": "running"})
        import yfinance as yf
        try:
            info = yf.Ticker(symbol).info
            company_name = info.get('longName') or info.get('shortName') or symbol
        except Exception:
            company_name = symbol
        elapsed = round(time.time() - step_start, 1)
        yield _sse_event("step", {"step": 2, "label": "기업 정보 조회 완료", "status": "done", "elapsed": elapsed})

        # Step 3: DCF 모델 호출
        step_start = time.time()
        yield _sse_event("step", {"step": 3, "label": "Gemini DCF 분석 모델 호출 중...", "status": "running"})
        latest_data = _prepare_latest_data(df)
        result = run_dcf_analysis(latest_data, symbol, company_name)
        elapsed = round(time.time() - step_start, 1)
        yield _sse_event("step", {"step": 3, "label": "DCF 분석 완료", "status": "done", "elapsed": elapsed})

        # Step 4: 완료
        total_elapsed = round(time.time() - total_start, 1)
        yield _sse_event("step", {"step": 4, "label": f"전체 분석 완료 ({total_elapsed}s)", "status": "done", "elapsed": total_elapsed})

        result["total_elapsed"] = total_elapsed
        yield _sse_event("result", result)

    return StreamingResponse(generate(), media_type="text/event-stream")
