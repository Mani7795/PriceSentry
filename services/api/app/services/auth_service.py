"""Auth business logic (separate from API routing)."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.core.settings import settings
from app.db.models import AuditLog, RefreshToken, User


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ─────────────────────────────────────────────────────────
    async def register(
        self, *, email: str, password: str, full_name: str | None,
        ip: str | None = None, user_agent: str | None = None,
    ) -> tuple[User, str, str]:
        """Returns (user, access_token, raw_refresh_token)."""
        email = email.lower().strip()

        exists = await self.db.scalar(select(User.user_id).where(User.email == email))
        if exists:
            raise HTTPException(status.HTTP_409_CONFLICT, "email already registered")

        user = User(
            email=email,
            password_hash=hash_password(password),
            full_name=full_name,
        )
        self.db.add(user)
        await self.db.flush()
        access, refresh_raw = await self._issue_tokens(user, ip=ip, ua=user_agent)
        self.db.add(AuditLog(user_id=user.user_id, event_type="user.registered",
                             ip_address=ip, user_agent=user_agent))
        await self.db.commit()
        return user, access, refresh_raw

    # ─────────────────────────────────────────────────────────
    async def login(
        self, *, email: str, password: str,
        ip: str | None = None, user_agent: str | None = None,
    ) -> tuple[User, str, str]:
        email = email.lower().strip()
        user = await self.db.scalar(select(User).where(User.email == email))
        if not user or not verify_password(password, user.password_hash):
            self.db.add(AuditLog(event_type="login.failed", ip_address=ip,
                                  user_agent=user_agent, extra={"email": email}))
            await self.db.commit()
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid credentials")
        if not user.is_active:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "account disabled")

        await self.db.execute(
            update(User).where(User.user_id == user.user_id).values(last_login_at=datetime.now(timezone.utc))
        )
        access, refresh_raw = await self._issue_tokens(user, ip=ip, ua=user_agent)
        self.db.add(AuditLog(user_id=user.user_id, event_type="login.success",
                              ip_address=ip, user_agent=user_agent))
        await self.db.commit()
        return user, access, refresh_raw

    # ─────────────────────────────────────────────────────────
    async def refresh(
        self, *, raw_refresh: str,
        ip: str | None = None, user_agent: str | None = None,
    ) -> tuple[User, str, str]:
        """Rotate: invalidate old refresh, issue new pair."""
        if not raw_refresh:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "no refresh token")

        token_hash = hash_refresh_token(raw_refresh)
        token = await self.db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
        if not token:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid refresh")

        now = datetime.now(timezone.utc)
        # Make expiry comparison timezone-aware regardless of DB type quirks
        expires_at = token.expires_at if token.expires_at.tzinfo else token.expires_at.replace(tzinfo=timezone.utc)
        if token.revoked_at or expires_at < now:
            # Token reuse after revocation? Revoke all sessions as defense-in-depth.
            await self.db.execute(
                update(RefreshToken)
                .where(RefreshToken.user_id == token.user_id, RefreshToken.revoked_at.is_(None))
                .values(revoked_at=now)
            )
            await self.db.commit()
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "refresh expired/revoked")

        user = await self.db.scalar(select(User).where(User.user_id == token.user_id))
        if not user or not user.is_active:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "account disabled")

        # Issue new pair, mark old as replaced
        new_access, new_refresh_raw = await self._issue_tokens(user, ip=ip, ua=user_agent)
        token.revoked_at = now
        # We just inserted the new RefreshToken; link old → new via replaced_by
        new_token = await self.db.scalar(
            select(RefreshToken)
            .where(RefreshToken.user_id == user.user_id, RefreshToken.revoked_at.is_(None))
            .order_by(RefreshToken.issued_at.desc())
            .limit(1)
        )
        if new_token:
            token.replaced_by = new_token.token_id
        await self.db.commit()
        return user, new_access, new_refresh_raw

    # ─────────────────────────────────────────────────────────
    async def revoke_refresh(self, raw_refresh: str) -> None:
        token_hash = hash_refresh_token(raw_refresh)
        await self.db.execute(
            update(RefreshToken)
            .where(RefreshToken.token_hash == token_hash, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=datetime.now(timezone.utc))
        )
        await self.db.commit()

    # ─────────────────────────────────────────────────────────
    async def _issue_tokens(
        self, user: User, *, ip: str | None, ua: str | None,
    ) -> tuple[str, str]:
        access = create_access_token(subject=str(user.user_id), extra={"email": user.email})
        refresh_raw = generate_refresh_token()
        now = datetime.now(timezone.utc)
        rt = RefreshToken(
            user_id=user.user_id,
            token_hash=hash_refresh_token(refresh_raw),
            issued_at=now,
            expires_at=now + timedelta(days=settings.refresh_token_ttl_days),
            ip_address=ip,
            user_agent=ua,
        )
        self.db.add(rt)
        await self.db.flush()
        return access, refresh_raw
