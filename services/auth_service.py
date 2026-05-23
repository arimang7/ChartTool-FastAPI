import os
import time

import jwt
from authlib.integrations.starlette_client import OAuth

# Google OAuth2 설정
CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
REDIRECT_URI = os.getenv("REDIRECT_URI", "http://localhost:8000/api/auth/callback")
JWT_SECRET = os.getenv("JWT_SECRET", "fastapi-charttool-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION = 3600 * 24  # 24시간

# Authlib OAuth 설정
oauth = OAuth()
oauth.register(
    name="google",
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)


def create_jwt_token(email: str, name: str = "") -> str:
    """JWT 토큰 생성"""
    payload = {
        "email": email,
        "name": name,
        "exp": int(time.time()) + JWT_EXPIRATION,
        "iat": int(time.time()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_jwt_token(token: str) -> dict | None:
    """JWT 토큰 검증"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None
