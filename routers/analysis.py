import json
import time
import asyncio
import pandas as pd
from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from services.stock_service import load_data
from services.analysis_service import run_ai_analysis, run_dcf_analysis, get_client

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


def _sse_event(event: str, data: dict) -> str:
    """SSE 이벤트 포맷"""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _prepare_latest_data(df, include_bands=False):
    """DataFrame에서 최신 데이터 추출"""
    latest = df.iloc[-1]
    data = {
        "current_price": float(latest["Close"]),
        "current_rsi": float(latest["RSI"]),
        "date": df.index[-1].strftime("%Y-%m-%d"),
    }
    if include_bands:
        data["upper"] = float(latest["Upper"]) if not pd.isna(latest["Upper"]) else 0
        data["lower"] = float(latest["Lower"]) if not pd.isna(latest["Lower"]) else 0
    return data


# 모델 정보 설정 및 우선순위
MODELS_CONFIG = [
    {"id": "gemini-3.5-flash", "priority": 1, "emoji": "🚀"},
    {"id": "gemini-3.1-pro", "priority": 2, "emoji": "💡"},
    {"id": "gemini-3.1-flash-lite", "priority": 3, "emoji": "⚡"},
    {"id": "gemini-2.5-flash", "priority": 4, "emoji": "⚙️"}
]


async def ping_model(model_id: str, priority: int, emoji: str) -> dict:
    """각 모델별로 지연시간(latency) 및 상태(status) 측정"""
    start_time = time.time()
    try:
        def sync_ping():
            client = get_client()
            return client.models.generate_content(
                model=model_id,
                contents="hi",
                config={'max_output_tokens': 1}
            )

        # asyncio.to_thread를 사용하여 비동기로 동기 API 호출 실행하며 2.5초 타임아웃 적용
        await asyncio.wait_for(asyncio.to_thread(sync_ping), timeout=2.5)
        latency = int((time.time() - start_time) * 1000)

        if latency < 3000:
            status = "fast"
        elif latency <= 8000:
            status = "normal"
        else:
            status = "busy"

        return {
            "id": model_id,
            "label": f"{emoji} {model_id}",
            "priority": priority,
            "latency": latency,
            "status": status
        }
    except Exception as e:
        latency = int((time.time() - start_time) * 1000)
        return {
            "id": model_id,
            "label": f"{emoji} {model_id}",
            "priority": priority,
            "latency": latency,
            "status": "busy",
            "error": str(e)
        }


@router.get("/model-health")
async def model_health():
    """Gemini 모델별 실시간 헬스체크 및 자동 권장 모델 선정"""
    results = await asyncio.gather(*(
        ping_model(m["id"], m["priority"], m["emoji"]) for m in MODELS_CONFIG
    ))

    # 우선순위 정렬
    results = list(results)
    results.sort(key=lambda x: x["priority"])

    recommended = None
    # 1단계: 가장 높은 우선순위의 fast 모델 선정
    for r in results:
        if r["status"] == "fast":
            recommended = r["id"]
            break

    # 2단계: fast가 없는 경우 normal 모델 선정
    if not recommended:
        for r in results:
            if r["status"] == "normal":
                recommended = r["id"]
                break

    # 3단계: 모두 busy인 경우 첫번째 모델로 폴백
    if not recommended:
        recommended = results[0]["id"]

    return {
        "models": results,
        "recommended": recommended
    }


@router.get("/ai/stream")
async def ai_analysis_stream(
    symbol: str = Query(...),
    period: str = Query("1y"),
    news_text: str = Query(""),
    model: str = Query("gemini-2.5-flash")
):
    """AI 분석 — SSE 스트리밍 (단계별 진행)"""

    def generate():
        total_start = time.time()

        # Step 1: 데이터 로딩
        step_start = time.time()
        yield _sse_event(
            "step", {"step": 1, "label": "주식 데이터 로딩 중...", "status": "running"}
        )
        df = load_data(symbol, period)
        elapsed = round(time.time() - step_start, 1)
        if df is None or df.empty:
            yield _sse_event("error", {"message": "주식 데이터를 불러올 수 없습니다."})
            return
        yield _sse_event(
            "step", {"step": 1, "label": "데이터 로딩 완료", "status": "done", "elapsed": elapsed}
        )

        # Step 2: 데이터 준비
        step_start = time.time()
        yield _sse_event(
            "step", {"step": 2, "label": "지표 계산 및 데이터 준비 중...", "status": "running"}
        )
        latest_data = _prepare_latest_data(df, include_bands=True)
        elapsed = round(time.time() - step_start, 1)
        yield _sse_event(
            "step", {"step": 2, "label": "데이터 준비 완료", "status": "done", "elapsed": elapsed}
        )

        # Step 3: AI 모델 호출
        step_start = time.time()
        yield _sse_event(
            "step", {"step": 3, "label": "Gemini AI 모델 호출 중...", "status": "running"}
        )
        result = run_ai_analysis(latest_data, symbol, news_text, model=model)
        elapsed = round(time.time() - step_start, 1)
        yield _sse_event(
            "step", {"step": 3, "label": "AI 분석 완료", "status": "done", "elapsed": elapsed}
        )

        # Step 4: 완료
        total_elapsed = round(time.time() - total_start, 1)
        yield _sse_event(
            "step",
            {
                "step": 4,
                "label": f"전체 분석 완료 ({total_elapsed}s)",
                "status": "done",
                "elapsed": total_elapsed,
            },
        )

        # 결과 전송
        result["total_elapsed"] = total_elapsed
        yield _sse_event("result", result)

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.get("/dcf/stream")
async def dcf_analysis_stream(
    symbol: str = Query(...),
    period: str = Query("1y"),
    model: str = Query("gemini-2.5-flash")
):
    """DCF 분석 — SSE 스트리밍 (단계별 진행)"""

    def generate():
        total_start = time.time()

        # Step 1: 데이터 로딩
        step_start = time.time()
        yield _sse_event(
            "step", {"step": 1, "label": "주식 데이터 로딩 중...", "status": "running"}
        )
        df = load_data(symbol, period)
        elapsed = round(time.time() - step_start, 1)
        if df is None or df.empty:
            yield _sse_event("error", {"message": "주식 데이터를 불러올 수 없습니다."})
            return
        yield _sse_event(
            "step", {"step": 1, "label": "데이터 로딩 완료", "status": "done", "elapsed": elapsed}
        )

        # Step 2: 기업 정보 조회
        step_start = time.time()
        yield _sse_event("step", {"step": 2, "label": "기업 정보 조회 중...", "status": "running"})
        import yfinance as yf

        try:
            info = yf.Ticker(symbol).info
            company_name = info.get("longName") or info.get("shortName") or symbol
        except Exception:
            company_name = symbol
        elapsed = round(time.time() - step_start, 1)
        yield _sse_event(
            "step",
            {"step": 2, "label": "기업 정보 조회 완료", "status": "done", "elapsed": elapsed},
        )

        # Step 3: DCF 모델 호출
        step_start = time.time()
        yield _sse_event(
            "step", {"step": 3, "label": "Gemini DCF 분석 모델 호출 중...", "status": "running"}
        )
        latest_data = _prepare_latest_data(df)
        result = run_dcf_analysis(latest_data, symbol, company_name, model=model)
        elapsed = round(time.time() - step_start, 1)
        yield _sse_event(
            "step", {"step": 3, "label": "DCF 분석 완료", "status": "done", "elapsed": elapsed}
        )

        # Step 4: 완료
        total_elapsed = round(time.time() - total_start, 1)
        yield _sse_event(
            "step",
            {
                "step": 4,
                "label": f"전체 분석 완료 ({total_elapsed}s)",
                "status": "done",
                "elapsed": total_elapsed,
            },
        )

        result["total_elapsed"] = total_elapsed
        yield _sse_event("result", result)

    return StreamingResponse(generate(), media_type="text/event-stream")
