"""认证接口：验证码发送、注册、两种登录、重置密码、注销。"""

from fastapi import APIRouter, Depends, Request, Response

from app.api.deps import get_auth_service, get_current_user, require_csrf
from app.core.config import settings
from app.core.errors import AUTH_REQUIRED, AppError
from app.schemas.auth import (
    EmailCodeLoginRequest,
    EmailCodeRequest,
    EmailCodeResponse,
    PasswordLoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
)
from app.schemas.user import UserView
from app.services.auth_service import AuthService, make_csrf_token

router = APIRouter()


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else ""


def _set_auth_cookies(response: Response, token: str) -> None:
    """登录成功后设置 hw_session（HttpOnly）与 hw_csrf（可读）两个 Cookie。"""
    csrf = make_csrf_token(token)
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        httponly=True,
        samesite=settings.cookie_samesite,
        secure=settings.cookie_secure,
        max_age=settings.session_ttl_seconds,
        path="/api",
    )
    response.set_cookie(
        key=settings.csrf_cookie_name,
        value=csrf,
        httponly=False,
        samesite=settings.cookie_samesite,
        secure=settings.cookie_secure,
        max_age=settings.session_ttl_seconds,
        path="/api",
    )


def _clear_auth_cookies(response: Response) -> None:
    """登出时清除两个 Cookie。"""
    response.delete_cookie(settings.session_cookie_name, path="/api")
    response.delete_cookie(settings.csrf_cookie_name, path="/api")


@router.post("/auth/email-codes", status_code=202)
async def send_email_code(
    payload: EmailCodeRequest,
    request: Request,
    service: AuthService = Depends(get_auth_service),
) -> EmailCodeResponse:
    retry_after = await service.send_email_code(payload.email, payload.purpose, _client_ip(request))
    return EmailCodeResponse(accepted=True, retry_after_seconds=retry_after)


@router.post("/auth/register", status_code=201)
async def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    service: AuthService = Depends(get_auth_service),
) -> UserView:
    user, token = await service.register(
        payload.email, payload.code, payload.password, _client_ip(request), request.headers.get("user-agent")
    )
    _set_auth_cookies(response, token)
    return UserView.model_validate(user)


@router.post("/auth/login/password", status_code=200)
async def login_password(
    payload: PasswordLoginRequest,
    request: Request,
    response: Response,
    service: AuthService = Depends(get_auth_service),
) -> UserView:
    user, token = await service.login_password(
        payload.email, payload.password, _client_ip(request), request.headers.get("user-agent")
    )
    _set_auth_cookies(response, token)
    return UserView.model_validate(user)


@router.post("/auth/login/email-code", status_code=200)
async def login_email_code(
    payload: EmailCodeLoginRequest,
    request: Request,
    response: Response,
    service: AuthService = Depends(get_auth_service),
) -> UserView:
    user, token = await service.login_email_code(
        payload.email, payload.code, _client_ip(request), request.headers.get("user-agent")
    )
    _set_auth_cookies(response, token)
    return UserView.model_validate(user)


@router.post("/auth/password/reset", status_code=204)
async def reset_password(
    payload: ResetPasswordRequest,
    service: AuthService = Depends(get_auth_service),
) -> Response:
    await service.reset_password(payload.email, payload.code, payload.new_password)
    return Response(status_code=204)


@router.post("/auth/logout", status_code=204)
async def logout(
    request: Request,
    response: Response,
    service: AuthService = Depends(get_auth_service),
    _csrf: None = Depends(require_csrf),
) -> Response:
    token = request.cookies.get(settings.session_cookie_name)
    if token is None:
        raise AppError(AUTH_REQUIRED)
    await service.logout(token)
    _clear_auth_cookies(response)
    return Response(status_code=204)


@router.post("/auth/logout-all", status_code=204)
async def logout_all(
    response: Response,
    service: AuthService = Depends(get_auth_service),
    user=Depends(get_current_user),
    _csrf: None = Depends(require_csrf),
) -> Response:
    await service.logout_all(user.id)
    _clear_auth_cookies(response)
    return Response(status_code=204)
