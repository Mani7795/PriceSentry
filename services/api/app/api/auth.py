"""Auth routes."""
from __future__ import annotations

from fastapi import APIRouter, Cookie, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.settings import settings
from app.db.models import User
from app.db.session import get_db
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserOut
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


REFRESH_COOKIE = "ps_refresh"


def _set_refresh_cookie(resp: Response, raw_refresh: str) -> None:
    resp.set_cookie(
        key=REFRESH_COOKIE,
        value=raw_refresh,
        httponly=True,
        secure=(settings.app_env == "prod"),
        samesite="lax",
        max_age=settings.refresh_token_ttl_days * 86400,
        path="/api/v1/auth",
    )


def _clear_refresh_cookie(resp: Response) -> None:
    resp.delete_cookie(REFRESH_COOKIE, path="/api/v1/auth")


def _client_metadata(request: Request) -> tuple[str | None, str | None]:
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    return ip, ua


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    ip, ua = _client_metadata(request)
    svc = AuthService(db)
    _, access, refresh_raw = await svc.register(
        email=body.email, password=body.password, full_name=body.full_name,
        ip=ip, user_agent=ua,
    )
    _set_refresh_cookie(response, refresh_raw)
    return TokenResponse(access_token=access, expires_in_seconds=settings.access_token_ttl_minutes * 60)


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    ip, ua = _client_metadata(request)
    svc = AuthService(db)
    _, access, refresh_raw = await svc.login(
        email=body.email, password=body.password, ip=ip, user_agent=ua,
    )
    _set_refresh_cookie(response, refresh_raw)
    return TokenResponse(access_token=access, expires_in_seconds=settings.access_token_ttl_minutes * 60)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    request: Request,
    response: Response,
    ps_refresh: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    ip, ua = _client_metadata(request)
    svc = AuthService(db)
    _, access, new_refresh = await svc.refresh(raw_refresh=ps_refresh or "", ip=ip, user_agent=ua)
    _set_refresh_cookie(response, new_refresh)
    return TokenResponse(access_token=access, expires_in_seconds=settings.access_token_ttl_minutes * 60)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    ps_refresh: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
) -> Response:
    if ps_refresh:
        await AuthService(db).revoke_refresh(ps_refresh)
    _clear_refresh_cookie(response)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(user)
