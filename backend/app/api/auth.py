"""Authentication and User Management REST Endpoints."""
from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
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
from backend.app.models.models import (PrivilegedActionAudit, User,
                                       UserRole)

router = APIRouter(prefix="/auth", tags=["auth"])


# bcrypt hashes at most 72 bytes and raises above that; silently truncating
# would make "<72 chars>" and "<72 chars>extra" the same password, so long
# inputs are rejected outright instead.
MIN_PASSWORD_LEN = 10
MAX_PASSWORD_BYTES = 72


def _validate_password(password: str) -> str:
    pw = (password or "").strip()
    if len(pw) < MIN_PASSWORD_LEN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Password must be at least {MIN_PASSWORD_LEN} characters.",
        )
    if len(pw.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Password must be at most {MAX_PASSWORD_BYTES} bytes.",
        )
    return pw


# --------------------------------------------------------------------------
# authority rules
# --------------------------------------------------------------------------
_MANAGER = require_role(list(UserRole.MANAGES_USERS))


def _audit(db: Session, actor: User, action: str,
           target: User | None = None, detail: str | None = None) -> None:
    """Write down who did what to whose account.

    Covers every manager, not only the hidden DEVELOPER: "who reset whose
    password" is the question asked after an incident, and it is unanswerable
    if only the unusual case is recorded.
    """
    db.add(PrivilegedActionAudit(
        actor_user_id=actor.id, actor_email=actor.email, actor_role=actor.role,
        action=action,
        target_user_id=target.id if target else None,
        target_email=target.email if target else None,
        detail=detail,
    ))


def _visible(stmt, viewer: User):
    """Hide ghost accounts from everyone but another ghost."""
    if viewer.role in UserRole.GHOST:
        return stmt
    return stmt.where(User.role.not_in(UserRole.GHOST))


def _target_or_404(db: Session, user_id: int, viewer: User) -> User:
    """Fetch a user the viewer is allowed to know exists.

    A hidden account returns 404, never 403. A 403 confirms the account is
    there, which is precisely what hiding it is meant to prevent.
    """
    user = db.scalar(select(User).where(User.id == user_id))
    if not user or (user.role in UserRole.GHOST and viewer.role not in UserRole.GHOST):
        raise HTTPException(status_code=404, detail="User not found.")
    return user


def _require_outranks(actor: User, target: User) -> None:
    if not UserRole.outranks(actor.role, target.role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot manage an account at or above your own level.")


def _require_can_grant(actor: User, role: str) -> None:
    """Nobody may hand out a role they do not outrank, including their own.

    Without this, "an admin manages users" means an admin can make themselves
    CEO, and the hierarchy is decorative.
    """
    if role not in UserRole.ALL:
        raise HTTPException(status_code=400,
                            detail=f"Invalid role. Must be one of {UserRole.ALL}")
    if not UserRole.outranks(actor.role, role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You cannot grant the {role} role.")


def _temp_password() -> str:
    """A one-time password, shown once and never stored in the clear."""
    return secrets.token_urlsafe(12)


class LoginRequest(BaseModel):
    email: str
    password: str


class UserOut(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    email: str
    full_name: str
    role: str
    is_active: bool
    can_export: bool
    created_at: datetime
    last_login_at: datetime | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class CreateUserRequest(BaseModel):
    email: str
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


@router.get("/users", response_model=list[UserOut])
def list_users(
    current_user: Annotated[User, Depends(_MANAGER)],
    db: Annotated[Session, Depends(get_db)],
):
    """Team members the caller is allowed to know about."""
    users = db.scalars(
        _visible(select(User), current_user).order_by(User.id.asc())).all()
    return [UserOut.model_validate(u) for u in users]


@router.post("/users", response_model=UserOut)
def create_user(
    req: CreateUserRequest,
    current_user: Annotated[User, Depends(_MANAGER)],
    db: Annotated[Session, Depends(get_db)],
):
    """Create a team member, below the caller's own level.

    The password set here is a starting password, not the person's password:
    must_change_password forces them to replace it before they can use
    anything. Nobody -- including whoever typed it -- can read it afterwards,
    because only the bcrypt hash is stored.
    """
    existing = db.scalar(select(User).where(User.email == req.email.lower().strip()))
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"User with email '{req.email}' already exists.",
        )

    _require_can_grant(current_user, req.role)

    new_user = User(
        email=req.email.lower().strip(),
        hashed_password=hash_password(_validate_password(req.password)),
        full_name=req.full_name.strip(),
        role=req.role,
        is_active=True,
        can_export=req.can_export or (UserRole.rank(req.role) >= UserRole.rank(UserRole.ADMIN)),
        must_change_password=True,
    )
    db.add(new_user)
    db.flush()
    _audit(db, current_user, "user.create", new_user, f"role={req.role}")
    db.commit()
    db.refresh(new_user)

    return UserOut.model_validate(new_user)


@router.put("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    req: UpdateUserRequest,
    current_user: Annotated[User, Depends(_MANAGER)],
    db: Annotated[Session, Depends(get_db)],
):
    """Update a team member's name, role, export permission or status.

    Password is deliberately NOT settable here. A manager who can type a
    password into someone else's account can then sign in as them, and every
    action that follows is attributed to the wrong person. Resets go through
    /users/{id}/reset-password, which issues a one-time password and forces the
    owner to replace it.
    """
    user = _target_or_404(db, user_id, current_user)
    _require_outranks(current_user, user)

    if req.full_name is not None:
        user.full_name = req.full_name.strip()
    if req.role is not None:
        _require_can_grant(current_user, req.role)
        _audit(db, current_user, "user.role_change", user,
               f"{user.role} -> {req.role}")
        user.role = req.role
        if UserRole.rank(req.role) >= UserRole.rank(UserRole.ADMIN):
            user.can_export = True
    if req.is_active is not None:
        if req.is_active != user.is_active:
            _audit(db, current_user, "user.activate" if req.is_active
                   else "user.deactivate", user)
        user.is_active = req.is_active
    if req.can_export is not None:
        user.can_export = req.can_export

    db.commit()
    db.refresh(user)
    return UserOut.model_validate(user)


# --------------------------------------------------------------------------
# passwords
# --------------------------------------------------------------------------
class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class ResetPasswordOut(BaseModel):
    user_id: int
    email: str
    # Returned exactly once, in this response, and never stored in the clear.
    # Hand it to the person; they are forced to replace it on first use.
    temporary_password: str


@router.post("/password", response_model=UserOut)
def change_own_password(
    req: ChangePasswordRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Set your own password.

    Requires the current one, so a walked-away-from session cannot be used to
    lock the real owner out. This is reachable while must_change_password is
    set -- it is the one thing someone in that state needs to do.
    """
    if not verify_password(req.current_password, current_user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Current password is incorrect.")
    new = _validate_password(req.new_password)
    if verify_password(new, current_user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="New password must differ from the current one.")

    current_user.hashed_password = hash_password(new)
    current_user.must_change_password = False
    current_user.password_changed_at = datetime.now(timezone.utc)
    # The actor is the owner, so this records that they set it themselves --
    # which is what distinguishes a normal change from an administrative reset.
    _audit(db, current_user, "password.self_change", current_user)
    db.commit()
    db.refresh(current_user)
    return UserOut.model_validate(current_user)


@router.post("/users/{user_id}/reset-password", response_model=ResetPasswordOut)
def reset_password(
    user_id: int,
    current_user: Annotated[User, Depends(_MANAGER)],
    db: Annotated[Session, Depends(get_db)],
):
    """Issue a one-time password for someone who is locked out.

    The manager never learns the person's real password -- only bcrypt hashes
    are stored, so there is nothing to learn. They hand over a temporary one,
    and must_change_password forces the owner to replace it before they can use
    the platform. That keeps the window in which someone else knows a working
    credential down to a single login.
    """
    user = _target_or_404(db, user_id, current_user)
    _require_outranks(current_user, user)

    temp = _temp_password()
    user.hashed_password = hash_password(temp)
    user.must_change_password = True
    user.password_changed_at = datetime.now(timezone.utc)
    _audit(db, current_user, "password.reset", user)
    db.commit()

    return ResetPasswordOut(user_id=user.id, email=user.email,
                            temporary_password=temp)


@router.get("/audit", response_model=list[dict])
def privileged_audit(
    limit: int = 200,
    current_user: Annotated[User, Depends(require_role(list(UserRole.EXECUTIVE)))] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    """Who did what to which account.

    Executive-only, and it includes the hidden DEVELOPER's actions. Hiding an
    account from listings is reasonable; hiding what it did is not, and would
    make any breach involving it impossible to reconstruct.
    """
    rows = db.scalars(
        select(PrivilegedActionAudit)
        .order_by(PrivilegedActionAudit.occurred_at.desc())
        .limit(max(1, min(limit, 1000)))
    ).all()
    return [{
        "actor": r.actor_email, "actor_role": r.actor_role, "action": r.action,
        "target": r.target_email, "detail": r.detail,
        "at": r.occurred_at.isoformat() if r.occurred_at else None,
    } for r in rows]
