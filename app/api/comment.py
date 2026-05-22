from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from .. import state
from ..deps import check_rate_limit, error, get_db, require_auth, video_exists
from ..models import Comment, Video
from ..mq import publish_comment, publish_popularity
from ..schemas import DeleteCommentRequest, GetAllCommentsRequest, PublishCommentRequest
from ..serializers import comment_dict
from ..timeline import change_popularity_cache


router = APIRouter(prefix="/comment", tags=["comment"])


@router.post("/publish")
def publish_comment_api(request: Request, req: PublishCommentRequest, current=Depends(require_auth), db: Session = Depends(get_db)):
    check_rate_limit(request, "comment_write", str(current["account_id"]), 10, 60)
    content = req.content.strip()
    if not content:
        error(400, "content is required")
    if req.video_id <= 0:
        error(400, "video_id is required")
    if not video_exists(db, req.video_id):
        error(400, "video not found")

    mysql_enqueued = publish_comment(
        state.mq,
        "publish",
        username=current["username"],
        video_id=req.video_id,
        author_id=current["account_id"],
        content=content,
    )
    redis_enqueued = publish_popularity(state.mq, req.video_id, 1)
    if not mysql_enqueued:
        db.add(Comment(username=current["username"], video_id=req.video_id, author_id=current["account_id"], content=content))
        db.query(Video).filter(Video.id == req.video_id).update({Video.popularity: Video.popularity + 1}, synchronize_session=False)
        db.commit()
    if not redis_enqueued:
        change_popularity_cache(req.video_id, 1)
    return {"message": "comment published successfully"}


@router.post("/delete")
def delete_comment(request: Request, req: DeleteCommentRequest, current=Depends(require_auth), db: Session = Depends(get_db)):
    check_rate_limit(request, "comment_write", str(current["account_id"]), 10, 60)
    if req.comment_id <= 0:
        error(400, "comment_id is required")
    comment = db.get(Comment, req.comment_id)
    if not comment:
        error(400, "comment not found")
    if comment.author_id != current["account_id"]:
        error(400, "permission denied")
    if not publish_comment(state.mq, "delete", comment_id=req.comment_id):
        db.delete(comment)
        db.commit()
    return {"message": "comment deleted successfully"}


@router.post("/listAll")
def list_comments(req: GetAllCommentsRequest, db: Session = Depends(get_db)):
    if req.video_id == 0:
        error(400, "video_id is required")
    if not video_exists(db, req.video_id):
        error(400, "video not found")
    comments = db.query(Comment).filter(Comment.video_id == req.video_id).all()
    return [comment_dict(c) for c in comments]
