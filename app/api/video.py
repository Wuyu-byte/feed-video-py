from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import secrets

from fastapi import APIRouter, Depends, File, Request, UploadFile
from sqlalchemy import desc
from sqlalchemy.orm import Session

from .. import state
from ..deps import error, get_db, require_auth
from ..models import OutboxMsg, Video
from ..schemas import GetDetailRequest, ListByAuthorIDRequest, PublishVideoRequest
from ..serializers import unix_millis, video_dict
from ..timeline import add_to_global_timeline


router = APIRouter(prefix="/video", tags=["video"])


@router.post("/uploadVideo")
def upload_video(request: Request, file: UploadFile = File(...), current=Depends(require_auth)):
    return save_upload(request, file, current["account_id"], "videos", {".mp4"}, 200 << 20, "play_url")


@router.post("/uploadCover")
def upload_cover(request: Request, file: UploadFile = File(...), current=Depends(require_auth)):
    return save_upload(request, file, current["account_id"], "covers", {".jpg", ".jpeg", ".png", ".webp"}, 10 << 20, "cover_url")


def save_upload(request: Request, file: UploadFile, account_id: int, kind: str, allowed_ext: set[str], max_size: int, field: str):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in allowed_ext:
        allowed = "/".join(sorted(allowed_ext))
        error(400, f"only {allowed} is allowed")

    date = datetime.now().strftime("%Y%m%d")
    rel_dir = Path(kind) / str(account_id) / date
    abs_dir = state.UPLOAD_ROOT / rel_dir
    abs_dir.mkdir(parents=True, exist_ok=True)
    filename = secrets.token_hex(16) + suffix
    target = abs_dir / filename

    size = 0
    with target.open("wb") as out:
        while chunk := file.file.read(1024 * 1024):
            size += len(chunk)
            if size > max_size:
                out.close()
                target.unlink(missing_ok=True)
                error(400, "invalid file size")
            out.write(chunk)
    if size <= 0:
        target.unlink(missing_ok=True)
        error(400, "invalid file size")

    url_path = "/static/" + "/".join([kind, str(account_id), date, filename])
    scheme = request.headers.get("x-forwarded-proto") or request.url.scheme
    host = request.headers.get("host") or request.url.netloc
    absolute = f"{scheme}://{host}{url_path}"
    return {"url": absolute, field: absolute}


@router.post("/publish")
def publish_video(req: PublishVideoRequest, current=Depends(require_auth), db: Session = Depends(get_db)):
    title = req.title.strip()
    play_url = req.play_url.strip()
    cover_url = req.cover_url.strip()
    if not title:
        error(400, "title is required")
    if not play_url:
        error(400, "play url is required")
    if not cover_url:
        error(400, "cover url is required")

    video = Video(
        author_id=current["account_id"],
        username=current["username"],
        title=title,
        description=req.description,
        play_url=play_url,
        cover_url=cover_url,
        create_time=datetime.utcnow(),
    )
    db.add(video)
    db.flush()
    db.add(OutboxMsg(video_id=video.id, event_type="video_published", create_time=video.create_time, status="pending"))
    db.commit()
    if not state.mq.enabled:
        add_to_global_timeline(video.id, unix_millis(video.create_time))
    return video_dict(video)


@router.post("/listByAuthorID")
def list_by_author(req: ListByAuthorIDRequest, db: Session = Depends(get_db)):
    videos = db.query(Video).filter(Video.author_id == req.author_id).order_by(desc(Video.create_time)).all()
    return [video_dict(v) for v in videos]


@router.post("/getDetail")
def get_detail(req: GetDetailRequest, db: Session = Depends(get_db)):
    key = f"video:detail:id={req.id}"
    cached = state.cache.get(key)
    if cached:
        try:
            return json.loads(cached)
        except json.JSONDecodeError:
            pass
    video = db.get(Video, req.id)
    if not video:
        error(400, "record not found")
    data = video_dict(video)
    state.cache.set(key, json.dumps(data), 300)
    return data
