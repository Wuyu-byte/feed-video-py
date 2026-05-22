from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Body, Depends, Request
from sqlalchemy import desc, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import state
from ..deps import check_rate_limit, error, get_db, require_auth, video_exists
from ..models import Like, Video
from ..mq import publish_like, publish_popularity
from ..schemas import EmptyBody, VideoIDRequest
from ..serializers import video_dict
from ..timeline import change_popularity_cache


router = APIRouter(prefix="/like", tags=["like"])


@router.post("/like")
def like_video(request: Request, req: VideoIDRequest, current=Depends(require_auth), db: Session = Depends(get_db)):
    check_rate_limit(request, "like_write", str(current["account_id"]), 30, 60)
    if req.video_id <= 0:
        error(400, "video_id is required")
    if not video_exists(db, req.video_id):
        error(500, "video not found")
    if db.query(Like.id).filter(Like.video_id == req.video_id, Like.account_id == current["account_id"]).first():
        error(500, "user has liked this video")

    mysql_enqueued = publish_like(state.mq, "like", current["account_id"], req.video_id)
    redis_enqueued = publish_popularity(state.mq, req.video_id, 1)
    if not mysql_enqueued:
        db.add(Like(video_id=req.video_id, account_id=current["account_id"], created_at=datetime.utcnow()))
        db.query(Video).filter(Video.id == req.video_id).update(
            {Video.likes_count: Video.likes_count + 1, Video.popularity: Video.popularity + 1},
            synchronize_session=False,
        )
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            error(500, "user has liked this video")
    if not redis_enqueued:
        change_popularity_cache(req.video_id, 1)
    return {"message": "like success"}


@router.post("/unlike")
def unlike_video(request: Request, req: VideoIDRequest, current=Depends(require_auth), db: Session = Depends(get_db)):
    check_rate_limit(request, "like_write", str(current["account_id"]), 30, 60)
    if req.video_id <= 0:
        error(400, "video_id is required")
    if not video_exists(db, req.video_id):
        error(500, "video not found")
    liked = db.query(Like).filter(Like.video_id == req.video_id, Like.account_id == current["account_id"]).first()
    if not liked:
        error(500, "user has not liked this video")

    mysql_enqueued = publish_like(state.mq, "unlike", current["account_id"], req.video_id)
    redis_enqueued = publish_popularity(state.mq, req.video_id, -1)
    if not mysql_enqueued:
        db.delete(liked)
        db.query(Video).filter(Video.id == req.video_id).update(
            {
                Video.likes_count: func.greatest(Video.likes_count - 1, 0),
                Video.popularity: func.greatest(Video.popularity - 1, 0),
            },
            synchronize_session=False,
        )
        db.commit()
    if not redis_enqueued:
        change_popularity_cache(req.video_id, -1)
    return {"message": "unlike success"}


@router.post("/isLiked")
def is_liked(req: VideoIDRequest, current=Depends(require_auth), db: Session = Depends(get_db)):
    if req.video_id <= 0:
        error(400, "video_id is required")
    exists = db.query(Like.id).filter(Like.video_id == req.video_id, Like.account_id == current["account_id"]).first()
    return {"is_liked": exists is not None}


@router.post("/listMyLikedVideos")
def list_my_liked(_: EmptyBody | None = Body(default=None), current=Depends(require_auth), db: Session = Depends(get_db)):
    videos = (
        db.query(Video)
        .join(Like, Like.video_id == Video.id)
        .filter(Like.account_id == current["account_id"])
        .order_by(desc(Like.created_at))
        .all()
    )
    return [video_dict(v) for v in videos]
