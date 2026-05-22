from __future__ import annotations

from datetime import datetime, timezone

from .models import Account, Comment, Video


def unix_seconds(value: datetime | None) -> int:
    if not value:
        return 0
    return int(value.replace(tzinfo=timezone.utc).timestamp())


def unix_millis(value: datetime | None) -> int:
    if not value:
        return 0
    return int(value.replace(tzinfo=timezone.utc).timestamp() * 1000)


def iso_time(value: datetime | None) -> str | None:
    if not value:
        return None
    return value.isoformat()


def account_dict(account: Account) -> dict:
    return {"id": account.id, "username": account.username}


def video_dict(video: Video) -> dict:
    return {
        "id": video.id,
        "author_id": video.author_id,
        "username": video.username,
        "title": video.title,
        "description": video.description or "",
        "play_url": video.play_url,
        "cover_url": video.cover_url,
        "create_time": iso_time(video.create_time),
        "likes_count": video.likes_count,
        "popularity": video.popularity,
    }


def comment_dict(comment: Comment) -> dict:
    return {
        "id": comment.id,
        "username": comment.username,
        "video_id": comment.video_id,
        "author_id": comment.author_id,
        "content": comment.content,
        "created_at": iso_time(comment.created_at),
    }


def feed_item(video: Video, is_liked: bool = False) -> dict:
    return {
        "id": video.id,
        "author": {"id": video.author_id, "username": video.username},
        "title": video.title,
        "description": video.description or "",
        "play_url": video.play_url,
        "cover_url": video.cover_url,
        "create_time": unix_seconds(video.create_time),
        "likes_count": video.likes_count,
        "is_liked": is_liked,
    }
