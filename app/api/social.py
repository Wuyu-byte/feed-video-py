from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import state
from ..deps import check_rate_limit, error, get_account, get_db, require_auth
from ..models import Account, Social
from ..mq import publish_social
from ..schemas import FollowRequest, GetAllFollowersRequest, GetAllVloggersRequest
from ..serializers import account_dict


router = APIRouter(prefix="/social", tags=["social"])


@router.post("/follow")
def follow(request: Request, req: FollowRequest, current=Depends(require_auth), db: Session = Depends(get_db)):
    check_rate_limit(request, "social_write", str(current["account_id"]), 20, 60)
    if req.vlogger_id <= 0:
        error(400, "vlogger_id is required")
    get_account(db, current["account_id"])
    get_account(db, req.vlogger_id)
    if current["account_id"] == req.vlogger_id:
        error(500, "can not follow self")
    if db.query(Social.id).filter(Social.follower_id == current["account_id"], Social.vlogger_id == req.vlogger_id).first():
        error(500, "already followed")
    publish_social(state.mq, "follow", current["account_id"], req.vlogger_id)
    db.add(Social(follower_id=current["account_id"], vlogger_id=req.vlogger_id))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        error(500, "already followed")
    return {"message": "followed"}


@router.post("/unfollow")
def unfollow(request: Request, req: FollowRequest, current=Depends(require_auth), db: Session = Depends(get_db)):
    check_rate_limit(request, "social_write", str(current["account_id"]), 20, 60)
    if req.vlogger_id <= 0:
        error(400, "vlogger_id is required")
    relation = db.query(Social).filter(Social.follower_id == current["account_id"], Social.vlogger_id == req.vlogger_id).first()
    if not relation:
        error(500, "not followed")
    publish_social(state.mq, "unfollow", current["account_id"], req.vlogger_id)
    db.delete(relation)
    db.commit()
    return {"message": "unfollowed"}


@router.post("/getAllFollowers")
def get_all_followers(req: GetAllFollowersRequest, current=Depends(require_auth), db: Session = Depends(get_db)):
    vlogger_id = req.vlogger_id or current["account_id"]
    get_account(db, vlogger_id)
    ids = [x.follower_id for x in db.query(Social).filter(Social.vlogger_id == vlogger_id).all()]
    accounts = db.query(Account).filter(Account.id.in_(ids)).all() if ids else []
    return {"followers": [account_dict(a) for a in accounts]}


@router.post("/getAllVloggers")
def get_all_vloggers(req: GetAllVloggersRequest, current=Depends(require_auth), db: Session = Depends(get_db)):
    follower_id = req.follower_id or current["account_id"]
    get_account(db, follower_id)
    ids = [x.vlogger_id for x in db.query(Social).filter(Social.follower_id == follower_id).all()]
    accounts = db.query(Account).filter(Account.id.in_(ids)).all() if ids else []
    return {"vloggers": [account_dict(a) for a in accounts]}
