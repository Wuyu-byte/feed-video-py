from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os

import bcrypt
import jwt


def jwt_secret() -> str:
    return os.getenv("JWT_SECRET", "change-me-in-env")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def check_password(password_hash: str, password: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def generate_token(account_id: int, username: str) -> str:
    now = datetime.now(tz=timezone.utc)
    payload = {
        "account_id": account_id,
        "username": username,
        "exp": now + timedelta(hours=24),
        "iat": now,
        "nbf": now,
    }
    return jwt.encode(payload, jwt_secret(), algorithm="HS256")


def parse_token(token: str) -> dict:
    return jwt.decode(token, jwt_secret(), algorithms=["HS256"])
