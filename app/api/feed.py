from __future__ import annotations

from datetime import datetime, timedelta, timezone
import time

from fastapi import APIRouter, Depends
from sqlalchemy import and_, desc, or_
from sqlalchemy.orm import Session

from .. import state
from ..deps import build_feed_items, error, get_db, limit_from_request, require_auth, soft_auth
from ..models import Social, Video
from ..schemas import ListByFollowingRequest, ListByPopularityRequest, ListLatestRequest, ListLikesCountRequest
from ..serializers import unix_millis


router = APIRouter(prefix="/feed", tags=["feed"])


@router.post("/listLatest")
def list_latest(req: ListLatestRequest, current=Depends(soft_auth), db: Session = Depends(get_db)):
    limit = limit_from_request(req.limit)
    latest_before = datetime.fromtimestamp(req.latest_time / 1000) if req.latest_time > 0 else None
    videos: list[Video] = []

    if state.cache.enabled:
        tail = state.cache.zrange_withscores("feed:global_timeline", 0, 0)
        if not tail:
            seed = db.query(Video).order_by(desc(Video.create_time)).limit(1000).all()
            if seed:
                state.cache.zadd("feed:global_timeline", {str(v.id): float(unix_millis(v.create_time)) for v in seed})
                tail = state.cache.zrange_withscores("feed:global_timeline", 0, 0)
        if tail:
            watermark = int(tail[0][1])
            req_time = int(time.time() * 1000) if not latest_before else unix_millis(latest_before)
            if req_time > watermark:
                max_score = "+inf" if not latest_before else str(req_time - 1)
                ids = [int(x) for x in state.cache.zrevrangebyscore("feed:global_timeline", max_score, "-inf", 0, limit) if str(x).isdigit()]
                if ids:
                    rows = db.query(Video).filter(Video.id.in_(ids)).all()
                    by_id = {v.id: v for v in rows}
                    videos = [by_id[i] for i in ids if i in by_id]

    if len(videos) < limit:
        q = db.query(Video).order_by(desc(Video.create_time))
        if videos:
            q = q.filter(Video.create_time < videos[-1].create_time)
        elif latest_before:
            q = q.filter(Video.create_time < latest_before)
        videos.extend(q.limit(limit - len(videos)).all())

    return {
        "video_list": build_feed_items(db, videos, current["account_id"]),
        "next_time": unix_millis(videos[-1].create_time) if videos else 0,
        "has_more": len(videos) == limit,
    }


@router.post("/listLikesCount")
def list_likes_count(req: ListLikesCountRequest, current=Depends(soft_auth), db: Session = Depends(get_db)):
    limit = limit_from_request(req.limit)
    q = db.query(Video).order_by(desc(Video.likes_count), desc(Video.id))
    if req.likes_count_before is not None or req.id_before is not None:
        if req.likes_count_before is None or req.id_before is None:
            error(400, "likes_count_before and id_before must be provided together")
        if req.likes_count_before < 0:
            error(400, "invalid cursor: likes_count_before must be >= 0")
        if req.id_before:
            q = q.filter(or_(Video.likes_count < req.likes_count_before, and_(Video.likes_count == req.likes_count_before, Video.id < req.id_before)))
        elif req.likes_count_before != 0:
            error(400, "invalid cursor: id_before must be > 0")
    videos = q.limit(limit).all()
    resp = {"video_list": build_feed_items(db, videos, current["account_id"]), "has_more": len(videos) == limit}
    if videos:
        resp["next_likes_count_before"] = videos[-1].likes_count
        resp["next_id_before"] = videos[-1].id
    return resp


@router.post("/listByFollowing")
def list_by_following(req: ListByFollowingRequest, current=Depends(require_auth), db: Session = Depends(get_db)):
    limit = limit_from_request(req.limit)
    latest_before = datetime.fromtimestamp(req.latest_time) if req.latest_time > 0 else None
    following = db.query(Social.vlogger_id).filter(Social.follower_id == current["account_id"])
    q = db.query(Video).filter(Video.author_id.in_(following)).order_by(desc(Video.create_time))
    if latest_before:
        q = q.filter(Video.create_time < latest_before)
    videos = q.limit(limit).all()
    return {
        "video_list": build_feed_items(db, videos, current["account_id"]),
        "next_time": int(videos[-1].create_time.timestamp()) if videos else 0,
        "has_more": len(videos) == limit,
    }


@router.post("/listByPopularity")
def list_by_popularity(req: ListByPopularityRequest, current=Depends(soft_auth), db: Session = Depends(get_db)):
    limit = limit_from_request(req.limit)
    if req.latest_popularity < 0:
        error(400, "latest_popularity must be >= 0")

    videos: list[Video] = []
    as_of = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    if req.as_of > 0:
        as_of = datetime.fromtimestamp(req.as_of, tz=timezone.utc).replace(second=0, microsecond=0)
    if state.cache.enabled:
        keys = ["hot:video:1m:" + (as_of - timedelta(minutes=i)).strftime("%Y%m%d%H%M") for i in range(60)]
        dest = "hot:video:merge:1m:" + as_of.strftime("%Y%m%d%H%M")
        if not state.cache.exists(dest):
            state.cache.zunionstore(dest, keys, "SUM")
            state.cache.expire(dest, 120)
        ids = [int(x) for x in state.cache.zrevrange(dest, req.offset, req.offset + limit - 1) if str(x).isdigit()]
        if ids:
            rows = db.query(Video).filter(Video.id.in_(ids)).all()
            by_id = {v.id: v for v in rows}
            videos = [by_id[i] for i in ids if i in by_id]
            items = build_feed_items(db, videos, current["account_id"])
            resp = {"video_list": items, "as_of": int(as_of.timestamp()), "next_offset": req.offset + len(items), "has_more": len(items) == limit}
            if videos:
                resp["next_latest_popularity"] = videos[-1].popularity
                resp["next_latest_before"] = videos[-1].create_time.isoformat()
                resp["next_latest_id_before"] = videos[-1].id
            return resp
        if req.offset > 0:
            return {"video_list": [], "as_of": int(as_of.timestamp()), "next_offset": req.offset, "has_more": False}

    q = db.query(Video).order_by(desc(Video.popularity), desc(Video.create_time), desc(Video.id))
    if req.latest_before is not None or req.latest_id_before is not None:
        if req.latest_before is None or not req.latest_id_before:
            error(400, "latest_before and latest_id_before must be provided together")
        q = q.filter(
            or_(
                Video.popularity < req.latest_popularity,
                and_(Video.popularity == req.latest_popularity, Video.create_time < req.latest_before),
                and_(Video.popularity == req.latest_popularity, Video.create_time == req.latest_before, Video.id < req.latest_id_before),
            )
        )
    videos = q.limit(limit).all()
    resp = {"video_list": build_feed_items(db, videos, current["account_id"]), "as_of": 0, "next_offset": 0, "has_more": len(videos) == limit}
    if videos:
        resp["next_latest_popularity"] = videos[-1].popularity
        resp["next_latest_before"] = videos[-1].create_time.isoformat()
        resp["next_latest_id_before"] = videos[-1].id
    return resp
