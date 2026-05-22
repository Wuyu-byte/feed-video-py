from __future__ import annotations

from fastapi import Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from . import auth
from . import state
from .models import Account, Like, Video
from .serializers import feed_item


def get_db():
    db = state.SessionLocal()
    try:
        yield db
    finally:
        db.close()


def error(status: int, message: str):
    raise HTTPException(status_code=status, detail=message)


async def http_exception_handler(_: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"error": str(exc.detail)})


def parse_bearer(request: Request) -> str:
    header = request.headers.get("authorization", "")
    if not header:
        error(401, "missing authorization header")
    parts = header.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        error(401, "invalid authorization header")
    return parts[1]


def check_token(request: Request, db: Session, optional: bool = False) -> dict:
    header = request.headers.get("authorization", "")
    if optional and not header:
        return {"account_id": 0, "username": ""}

    token = parse_bearer(request)
    try:
        claims = auth.parse_token(token)
    except Exception:
        error(401, "invalid or expired token")

    account_id = int(claims.get("account_id") or 0)
    username = str(claims.get("username") or "")
    cached = state.cache.get(f"account:{account_id}") if state.cache.enabled else None
    if cached is not None:
        if cached != token:
            error(401, "token has been revoked")
        return {"account_id": account_id, "username": username, "token": token}

    account = db.get(Account, account_id)
    if not account or not account.token or account.token != token:
        error(401, "token has been revoked")
    if state.cache.enabled:
        state.cache.set(f"account:{account_id}", token, 24 * 3600)
    return {"account_id": account_id, "username": username, "token": token}


def require_auth(request: Request, db: Session = Depends(get_db)) -> dict:
    return check_token(request, db, optional=False)


def soft_auth(request: Request, db: Session = Depends(get_db)) -> dict:
    return check_token(request, db, optional=True)


def check_rate_limit(request: Request, prefix: str, subject: str, maximum: int, window_seconds: int) -> None:
    if not state.cache.enabled or not subject:
        return
    key = f"feedsystem:ratelimit:{prefix}:{subject.strip()}"
    count = state.cache.incr_with_expire(key, window_seconds)
    if count is not None and count > maximum:
        error(429, "too many requests")


def limit_from_request(value: int) -> int:
    return 10 if value <= 0 or value > 50 else value


def get_account(db: Session, account_id: int) -> Account:
    account = db.get(Account, account_id)
    if not account:
        error(500, "record not found")
    return account


def video_exists(db: Session, video_id: int) -> bool:
    return db.query(Video.id).filter(Video.id == video_id).first() is not None


def build_feed_items(db: Session, videos: list[Video], viewer_account_id: int) -> list[dict]:
    liked: set[int] = set()
    if viewer_account_id and videos:
        ids = [v.id for v in videos]
        liked = {
            row.video_id
            for row in db.query(Like.video_id).filter(Like.account_id == viewer_account_id, Like.video_id.in_(ids)).all()
        }
    return [feed_item(video, video.id in liked) for video in videos]
