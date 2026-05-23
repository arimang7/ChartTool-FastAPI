from fastapi.responses import RedirectResponse

from fastapi import APIRouter, HTTPException, Request, Response
from services.auth_service import REDIRECT_URI, create_jwt_token, oauth, verify_jwt_token

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/login")
async def login(request: Request):
    """Google OAuth 로그인 시작"""
    return await oauth.google.authorize_redirect(request, REDIRECT_URI)


@router.get("/callback")
async def auth_callback(request: Request):
    """Google OAuth 콜백 처리"""
    try:
        token = await oauth.google.authorize_access_token(request)
        user_info = token.get("userinfo")

        if not user_info:
            raise HTTPException(status_code=400, detail="사용자 정보를 가져올 수 없습니다.")

        email = user_info.get("email", "")
        name = user_info.get("name", "")

        # JWT 토큰 생성 후 쿠키에 설정
        jwt_token = create_jwt_token(email, name)
        response = RedirectResponse(url="/")
        response.set_cookie(
            key="auth_token", value=jwt_token, httponly=True, max_age=3600 * 24, samesite="lax"
        )
        return response
    except Exception:
        return RedirectResponse(url="/?error=auth_failed")


@router.get("/me")
async def get_current_user(request: Request):
    """현재 로그인된 사용자 정보"""
    token = request.cookies.get("auth_token")
    if not token:
        return {"logged_in": False, "email": "", "name": ""}

    payload = verify_jwt_token(token)
    if not payload:
        return {"logged_in": False, "email": "", "name": ""}

    return {"logged_in": True, "email": payload.get("email", ""), "name": payload.get("name", "")}


@router.post("/logout")
async def logout():
    """로그아웃"""
    response = Response(content='{"success": true}', media_type="application/json")
    response.delete_cookie("auth_token")
    return response
