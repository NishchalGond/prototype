"""Authentication and User Management REST Endpoints."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.security import (
    create_access_token,
    get_current_user,
    hash_password,
    require_role,
    verify_password,
)
from backend.app.database.session import get_db
from backend.app.models.models import User, UserRole

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    email: str
    full_name: str
    role: str
    is_active: bool
    can_export: bool
    created_at: datetime
    last_login_at: datetime | None = None

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class CreateUserRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    role: str = UserRole.DATA_PROCESSOR
    can_export: bool = False


class UpdateUserRequest(BaseModel):
    full_name: str | None = None
    role: str | None = None
    is_active: bool | None = None
    can_export: bool | None = None
    password: str | None = None


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Annotated[Session, Depends(get_db)]):
    """Authenticate user with email & password and return signed JWT."""
    user = db.scalar(select(User).where(User.email == req.email.lower().strip()))
    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account has been deactivated.",
        )

    # Update last login timestamp
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)

    token = create_access_token(
        data={"sub": str(user.id), "email": user.email, "role": user.role}
    )

    return TokenResponse(
        access_token=token,
        user=UserOut.model_validate(user),
    )


@router.get("/me", response_model=UserOut)
def get_me(current_user: Annotated[User, Depends(get_current_user)]):
    """Return currently authenticated user profile."""
    return UserOut.model_validate(current_user)


@router.post("/seed-admin")
def seed_admin(db: Annotated[Session, Depends(get_db)]):
    """Idempotently seed default admin account if none exists."""
    existing_admin = db.scalar(select(User).where(User.role == UserRole.ADMIN))
    if existing_admin:
        return {"status": "exists", "email": existing_admin.email}

    admin = User(
        email="admin@datalink.ae",
        hashed_password=hash_password("admin321"),
        full_name="Lead Data Administrator",
        role=UserRole.ADMIN,
        is_active=True,
        can_export=True,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)

    return {
        "status": "created",
        "email": admin.email,
        "message": "Default admin account initialized. Password: admin321",
    }


@router.get("/users", response_model=list[UserOut])
def list_users(
    current_user: Annotated[User, Depends(require_role([UserRole.ADMIN]))],
    db: Annotated[Session, Depends(get_db)],
):
    """List all registered team members (Admin only)."""
    users = db.scalars(select(User).order_by(User.id.asc())).all()
    return [UserOut.model_validate(u) for u in users]


@router.post("/users", response_model=UserOut)
def create_user(
    req: CreateUserRequest,
    current_user: Annotated[User, Depends(require_role([UserRole.ADMIN]))],
    db: Annotated[Session, Depends(get_db)],
):
    """Create new team user (Admin only)."""
    existing = db.scalar(select(User).where(User.email == req.email.lower().strip()))
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"User with email '{req.email}' already exists.",
        )

    if req.role not in UserRole.ALL:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role. Must be one of {UserRole.ALL}",
        )

    new_user = User(
        email=req.email.lower().strip(),
        hashed_password=hash_password(req.password),
        full_name=req.full_name.strip(),
        role=req.role,
        is_active=True,
        can_export=req.can_export or (req.role == UserRole.ADMIN),
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return UserOut.model_validate(new_user)


@router.put("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    req: UpdateUserRequest,
    current_user: Annotated[User, Depends(require_role([UserRole.ADMIN]))],
    db: Annotated[Session, Depends(get_db)],
):
    """Update team user role, export permissions, or status (Admin only)."""
    user = db.scalar(select(User).where(User.id == user_id))
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    if req.full_name is not None:
        user.full_name = req.full_name.strip()
    if req.role is not None:
        if req.role not in UserRole.ALL:
            raise HTTPException(status_code=400, detail=f"Invalid role. Must be one of {UserRole.ALL}")
        user.role = req.role
        if req.role == UserRole.ADMIN:
            user.can_export = True
    if req.is_active is not None:
        user.is_active = req.is_active
    if req.can_export is not None:
        user.can_export = req.can_export
    if req.password:
        user.hashed_password = hash_password(req.password)

    db.commit()
    db.refresh(user)
    return UserOut.model_validate(user)
