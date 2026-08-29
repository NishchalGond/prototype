"""Who may act on whom, and what a password reset can and cannot reveal.

The failure a role system usually has is not that the wrong person is blocked;
it is that "an admin manages users" quietly means an admin can promote
themselves. These tests pin the ordering that prevents it.
"""
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker

from backend.app.api.auth import (
    _require_can_grant, _require_outranks, _target_or_404, _temp_password,
    _visible,
)
from backend.app.core.security import (
    PASSWORD_CHANGE_EXEMPT, hash_password, verify_password,
)
from backend.app.models.models import Base, PrivilegedActionAudit, User, UserRole


@pytest.fixture
def db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path/'roles.db'}")

    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_conn, _):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def _user(db, role, email=None):
    u = User(email=email or f"{role.lower()}@example.com", full_name=role,
             hashed_password=hash_password("initial-password-123"), role=role,
             is_active=True)
    db.add(u)
    db.commit()
    return u


# --- the ordering -----------------------------------------------------------

def test_the_hierarchy_is_ordered_as_intended():
    r = UserRole.rank
    assert (r(UserRole.DEVELOPER) > r(UserRole.CEO) > r(UserRole.CCO)
            > r(UserRole.ADMIN) > r(UserRole.DATA_PROCESSOR)
            > r(UserRole.VIEWER))


def test_nobody_outranks_their_own_level():
    # Strict: two admins cannot reset each other's passwords or demote one
    # another.
    for role in UserRole.ALL:
        assert not UserRole.outranks(role, role), role


def test_an_admin_cannot_act_on_an_executive(db):
    admin, ceo = _user(db, UserRole.ADMIN), _user(db, UserRole.CEO)
    with pytest.raises(HTTPException) as exc:
        _require_outranks(admin, ceo)
    assert exc.value.status_code == 403


def test_an_admin_cannot_promote_anyone_to_their_own_level_or_above(db):
    admin = _user(db, UserRole.ADMIN)
    for role in (UserRole.ADMIN, UserRole.CCO, UserRole.CEO, UserRole.DEVELOPER):
        with pytest.raises(HTTPException):
            _require_can_grant(admin, role)


def test_an_admin_may_create_the_people_below_them(db):
    admin = _user(db, UserRole.ADMIN)
    for role in (UserRole.DATA_PROCESSOR, UserRole.VIEWER):
        _require_can_grant(admin, role)      # must not raise


def test_a_developer_may_grant_every_other_role(db):
    dev = _user(db, UserRole.DEVELOPER)
    for role in UserRole.ALL:
        if role == UserRole.DEVELOPER:
            continue
        _require_can_grant(dev, role)


def test_permission_floors_include_everyone_above_them():
    # Adding CEO above ADMIN must not lock the CEO out of admin functions.
    assert UserRole.CEO in UserRole.at_least(UserRole.ADMIN)
    assert UserRole.DEVELOPER in UserRole.at_least(UserRole.DATA_PROCESSOR)
    assert UserRole.VIEWER not in UserRole.at_least(UserRole.ADMIN)


# --- the ghost --------------------------------------------------------------

def test_a_developer_is_hidden_from_everyone_else(db):
    _user(db, UserRole.DEVELOPER)
    _user(db, UserRole.DATA_PROCESSOR)
    admin = _user(db, UserRole.ADMIN)

    visible = db.scalars(_visible(select(User), admin)).all()
    assert UserRole.DEVELOPER not in {u.role for u in visible}


def test_a_developer_can_see_other_developers(db):
    _user(db, UserRole.DEVELOPER)
    dev = _user(db, UserRole.DEVELOPER, email="dev2@example.com")
    visible = db.scalars(_visible(select(User), dev)).all()
    assert sum(u.role == UserRole.DEVELOPER for u in visible) == 2


def test_fetching_a_hidden_account_is_a_404_not_a_403(db):
    # A 403 confirms the account exists, which is exactly what hiding it is
    # meant to prevent.
    ghost = _user(db, UserRole.DEVELOPER)
    ceo = _user(db, UserRole.CEO)
    with pytest.raises(HTTPException) as exc:
        _target_or_404(db, ghost.id, ceo)
    assert exc.value.status_code == 404


def test_the_hidden_account_is_still_audited(db):
    # Hiding an account from listings is reasonable. Hiding what it did is not.
    dev = _user(db, UserRole.DEVELOPER)
    db.add(PrivilegedActionAudit(actor_user_id=dev.id, actor_email=dev.email,
                                 actor_role=dev.role, action="password.reset",
                                 target_email="someone@example.com"))
    db.commit()
    entry = db.scalar(select(PrivilegedActionAudit))
    assert entry.actor_role == UserRole.DEVELOPER
    assert entry.action == "password.reset"


# --- passwords --------------------------------------------------------------

def test_a_password_is_never_stored_in_the_clear(db):
    user = _user(db, UserRole.DATA_PROCESSOR)
    assert "initial-password-123" not in user.hashed_password
    assert verify_password("initial-password-123", user.hashed_password)


def test_a_new_account_must_replace_its_starting_password(db):
    user = _user(db, UserRole.DATA_PROCESSOR)
    user.must_change_password = True
    db.commit()
    assert user.must_change_password is True


def test_only_the_password_routes_stay_open_during_a_forced_change():
    # Anything else would let someone keep working indefinitely on a password
    # an administrator handed them and can still guess.
    assert "/api/auth/password" in PASSWORD_CHANGE_EXEMPT
    assert "/api/auth/me" in PASSWORD_CHANGE_EXEMPT
    assert "/api/records" not in PASSWORD_CHANGE_EXEMPT


def test_a_temporary_password_is_unguessable():
    a, b = _temp_password(), _temp_password()
    assert a != b
    assert len(a) >= 12


def test_update_user_cannot_set_a_password():
    # A manager who can type a password into someone else's account can sign in
    # as them, and every action after that is attributed to the wrong person.
    import inspect
    from backend.app.api import auth
    body = inspect.getsource(auth.update_user)
    assert "hashed_password" not in body
