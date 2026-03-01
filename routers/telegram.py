from fastapi import APIRouter
from pydantic import BaseModel
from services.telegram_service import send_telegram_message

router = APIRouter(prefix="/api/telegram", tags=["telegram"])


class TelegramRequest(BaseModel):
    message: str


@router.post("/send")
async def send_message(request: TelegramRequest):
    """텔레그램 메시지 전송"""
    result = send_telegram_message(request.message)
    return result
