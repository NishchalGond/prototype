"""Enterprise Security and RBAC Authentication Core.

Provides:
- bcrypt password hashing & verification.
- HMAC-SHA256 JWT access token generation & signature validation.
- FastAPI dependency injection for current authenticated user and RBAC role guards.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated, Sequence

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.database.session import get_db
from backend.app.models.models import User, UserRole

# Read straight off settings: config._finalise guarantees a value is present
# (mandatory in production, random-per-boot in development), so there is no
# fallback literal here that could be used to forge tokens.
SECRET_KEY = settings.SECRET_KEY
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES

security_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    """Hash a plaintext password with bcrypt and unique salt."""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify plaintext password against bcrypt hash."""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except Exception:
        return False


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Encode user claims into a signed HS256 JWT."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    """Decode and verify JWT signature and expiration."""
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return None


def _subject_id(payload: dict) -> int | None:
    """Extract the numeric user id from a token subject.

    The claim is attacker-supplied, so a non-numeric `sub` is an authentication
    failure, not a crash: int() on e.g. "admin" raises ValueError, which without
    this guard escaped the dependency as an unhandled 500.
    """
    raw = payload.get("sub")
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def get_current_user_optional(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User | None:
    """Optional user dependency for public routes with enhanced context."""
    if not credentials or not credentials.credentials:
        return None

    payload = decode_access_token(credentials.credentials)
    if not payload:
        return None

    user_id = _subject_id(payload)
    if user_id is None:
        return None

    user = db.scalar(select(User).where(User.id == user_id, User.is_active.is_(True)))
    return user


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """Strict authenticated user dependency."""
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please provide a valid Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(credentials.credentials)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = _subject_id(payload)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token payload.",
        )

    user = db.scalar(select(User).where(User.id == user_id))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account not found.",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated.",
        )

    return user


def require_role(allowed_roles: Sequence[str]):
    """RBAC dependency factory checking user role."""
    def _role_checker(current_user: Annotated[User, Depends(get_current_user)]) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied. Required role in {allowed_roles}, your role is {current_user.role}.",
            )
        return current_user
    return _role_checker


def require_export_permission(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Ensure user has unmasked export permission."""
    if current_user.role == UserRole.ADMIN or current_user.can_export:
        return current_user

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Export permission denied. Contact an administrator to request export privileges.",
    )
