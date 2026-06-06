from fastapi import APIRouter, HTTPException, Response

from app.core.settings import Settings
from app.services.ui_auth_service import get_ui_auth_service


router = APIRouter()
settings = Settings()


@router.get("/auth/status")
async def auth_status() -> dict:
    service = get_ui_auth_service()
    return {"auth_enabled": service.enabled()}


@router.post("/auth/request-code")
async def request_login_code() -> dict:
    service = get_ui_auth_service()
    if not service.enabled():
        return {"sent": False, "auth_enabled": False}
    try:
        await service.send_login_code()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)[:200])
    return {
        "sent": True,
        "auth_enabled": True,
        "delivery_errors": service.last_delivery_errors(),
    }


@router.post("/auth/verify-code")
async def verify_login_code(payload: dict, response: Response) -> dict:
    service = get_ui_auth_service()
    if not service.enabled():
        return {"authenticated": True}
    code = str(payload.get("code") or "").strip()
    if not service.verify_code(code):
        raise HTTPException(status_code=401, detail="invalid_or_expired_code")
    response.set_cookie(
        "tb_session",
        service.create_session_token(),
        httponly=True,
        secure=settings.ui_auth_cookie_secure,
        samesite="lax",
        max_age=60 * 60 * 24 * 14,
        path="/",
    )
    return {"authenticated": True}


@router.post("/auth/logout")
async def logout(response: Response) -> dict:
    response.delete_cookie("tb_session", path="/")
    return {"authenticated": False}
