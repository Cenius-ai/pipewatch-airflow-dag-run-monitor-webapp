"""Server-side authentication: password hashing, lookup and session lifecycle."""

from __future__ import annotations

import secrets
import time
from collections import defaultdict, deque

from flask import g, session
from sqlalchemy import func, or_, select
from werkzeug.security import check_password_hash, generate_password_hash

from . import config, db
from .models import User

SESSION_USER_KEY = "user_id"
CSRF_KEY = "csrf_token"

# Verified against when the username does not exist so a missing account and a
# wrong password take the same amount of work (no user enumeration by timing).
_DUMMY_HASH = generate_password_hash("pipewatch-dummy-password")
_attempts: dict[str, deque[float]] = defaultdict(deque)


def hash_password(raw_password: str) -> str:
    return generate_password_hash(raw_password)


def verify_password(password_hash: str, raw_password: str) -> bool:
    return check_password_hash(password_hash, raw_password)


def authenticate(identity: str, password: str) -> dict | None:
    """Return the public user dict for valid credentials, otherwise None."""
    if not identity or not password:
        return None
    needle = identity.strip().lower()
    with db.session_scope() as db_session:
        user = db_session.execute(
            select(User).where(
                or_(func.lower(User.username) == needle, func.lower(User.email) == needle)
            )
        ).scalar_one_or_none()
        if user is None:
            verify_password(_DUMMY_HASH, password)
            return None
        if not verify_password(user.password_hash, password):
            return None
        return {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "display_name": user.display_name,
            "role": user.role,
        }


def login_rate_limited(client_key: str) -> bool:
    """Simple sliding-window limiter: LOGIN_ATTEMPT_LIMIT tries per minute."""
    now = time.monotonic()
    window = config.LOGIN_ATTEMPT_WINDOW_SECONDS
    bucket = _attempts[client_key]
    while bucket and now - bucket[0] > window:
        bucket.popleft()
    bucket.append(now)
    return len(bucket) > config.LOGIN_ATTEMPT_LIMIT


def start_session(user: dict) -> None:
    """Rotate the session (fresh cookie) and store the signed-in identity."""
    session.clear()
    session[SESSION_USER_KEY] = user["id"]
    session[CSRF_KEY] = secrets.token_urlsafe(32)
    session.permanent = True


def end_session() -> None:
    session.clear()


def current_user() -> dict | None:
    """The signed-in user for this request, or None."""
    cached = getattr(g, "_pipewatch_user", "unset")
    if cached != "unset":
        return cached
    user_id = session.get(SESSION_USER_KEY)
    user = None
    if isinstance(user_id, int):
        with db.session_scope() as db_session:
            row = db_session.get(User, user_id)
            if row is not None:
                user = {
                    "id": row.id,
                    "username": row.username,
                    "email": row.email,
                    "display_name": row.display_name,
                    "role": row.role,
                }
    g._pipewatch_user = user
    return user


def csrf_token() -> str:
    """Per-session CSRF token, created on first use."""
    token = session.get(CSRF_KEY)
    if not token:
        token = secrets.token_urlsafe(32)
        session[CSRF_KEY] = token
    return token


def csrf_valid(submitted: str | None) -> bool:
    expected = session.get(CSRF_KEY)
    if not expected or not submitted:
        return False
    return secrets.compare_digest(str(expected), str(submitted))
