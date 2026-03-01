import os
import requests


TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def send_telegram_message(message: str) -> dict:
    """텔레그램 메시지 전송"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return {"success": False, "message": "텔레그램 설정이 되어있지 않습니다."}

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    max_length = 4000
    chunks = [message[i:i + max_length] for i in range(0, len(message), max_length)]

    for i, chunk in enumerate(chunks):
        text_to_send = chunk
        if len(chunks) > 1:
            text_to_send = f"[{i + 1}/{len(chunks)}]\n" + chunk

        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text_to_send
        }

        try:
            response = requests.post(url, json=payload)
            if response.status_code != 200:
                return {"success": False, "message": f"오류: {response.text}"}
        except Exception as e:
            return {"success": False, "message": f"예외 발생: {e}"}

    return {"success": True, "message": "성공"}
