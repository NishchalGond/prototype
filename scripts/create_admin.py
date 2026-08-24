"""Create or reset an administrator account.

The application no longer ships a default password, so this is the supported way
to get back in if ADMIN_PASSWORD was never set or the admin password is lost.

Usage:
    python scripts/create_admin.py                        # prompts for a password
    python scripts/create_admin.py --email me@example.com
    python scripts/create_admin.py --generate             # prints a random password

Runs against whatever DATABASE_URL is in the environment / .env.
"""
from __future__ import annotations

import argparse
import getpass
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import select  # noqa: E402

from backend.app.config import settings  # noqa: E402
from backend.app.core.security import hash_password  # noqa: E402
from backend.app.database.session import SessionLocal, init_db  # noqa: E402
from backend.app.models.models import User, UserRole  # noqa: E402

MIN_LEN = 10
MAX_BYTES = 72


def main() -> int:
    ap = argparse.ArgumentParser(description="Create or reset an admin account.")
    ap.add_argument("--email", default=settings.ADMIN_EMAIL,
                    help=f"Admin email (default: {settings.ADMIN_EMAIL})")
    ap.add_argument("--name", default="Lead Data Administrator")
    ap.add_argument("--generate", action="store_true",
                    help="Generate a random password and print it once.")
    args = ap.parse_args()

    email = args.email.lower().strip()

    if args.generate:
        password = secrets.token_urlsafe(16)
    else:
        password = getpass.getpass("New password: ")
        if password != getpass.getpass("Confirm password: "):
            print("Passwords do not match.", file=sys.stderr)
            return 1

    if len(password) < MIN_LEN:
        print(f"Password must be at least {MIN_LEN} characters.", file=sys.stderr)
        return 1
    if len(password.encode("utf-8")) > MAX_BYTES:
        print(f"Password must be at most {MAX_BYTES} bytes.", file=sys.stderr)
        return 1

    init_db()
    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.email == email))
        if user:
            user.hashed_password = hash_password(password)
            user.role = UserRole.ADMIN
            user.is_active = True
            user.can_export = True
            action = "reset"
        else:
            db.add(User(
                email=email,
                hashed_password=hash_password(password),
                full_name=args.name,
                role=UserRole.ADMIN,
                is_active=True,
                can_export=True,
            ))
            action = "created"
        db.commit()
    finally:
        db.close()

    print(f"Administrator {action}: {email}")
    if args.generate:
        print(f"Password: {password}")
        print("Store this now; it is not recoverable.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
