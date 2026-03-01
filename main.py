import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# .env 파일 로드 (프로젝트 루트에서)
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(env_path)

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from routers import stock, analysis, telegram, auth

app = FastAPI(title="AI 주식 분석 도구", version="1.0.0")

# 세션 미들웨어 (OAuth에 필요)
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("JWT_SECRET", "fastapi-charttool-secret-key-change-in-production")
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(stock.router)
app.include_router(analysis.router)
app.include_router(telegram.router)
app.include_router(auth.router)

# 정적 파일 마운트
static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
async def root():
    """메인 페이지 서빙"""
    return FileResponse(str(static_dir / "index.html"))
