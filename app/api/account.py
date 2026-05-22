from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import auth, state
from ..deps import check_rate_limit, error, get_account, get_db, require_auth
from ..models import Account
from ..schemas import (
    ChangePasswordRequest,
    CreateAccountRequest,
    EmptyBody,
    FindByIDRequest,
    FindByUsernameRequest,
    LoginRequest,
    RenameRequest,
)
from ..serializers import account_dict


router = APIRouter(prefix="/account", tags=["account"])


@router.post("/register")
def register(request: Request, req: CreateAccountRequest, db: Session = Depends(get_db)):
    check_rate_limit(request, "account_register", request.client.host if request.client else "", 5, 3600)
    account = Account(username=req.username, password=auth.hash_password(req.password), token="")
    db.add(account)
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        error(500, str(exc))
    return {"message": "account created"}


@router.post("/login")
def login(request: Request, req: LoginRequest, db: Session = Depends(get_db)):
    check_rate_limit(request, "account_login", request.client.host if request.client else "", 10, 60)
    account = db.query(Account).filter(Account.username == req.username).first()
    if not account or not auth.check_password(account.password, req.password):
        error(500, "record not found")
    token = auth.generate_token(account.id, account.username)
    account.token = token
    db.commit()
    state.cache.set(f"account:{account.id}", token, 24 * 3600)
    return {"token": token}


@router.post("/logout")
def logout(_: EmptyBody | None = Body(default=None), current=Depends(require_auth), db: Session = Depends(get_db)):
    account = get_account(db, current["account_id"])
    account.token = ""
    db.commit()
    state.cache.delete(f"account:{account.id}")
    return {"message": "account logged out"}


@router.post("/rename")
def rename(req: RenameRequest, current=Depends(require_auth), db: Session = Depends(get_db)):
    new_username = req.new_username.strip()
    if not new_username:
        error(400, "new_username is required")
    account = get_account(db, current["account_id"])
    token = auth.generate_token(account.id, new_username)
    account.username = new_username
    account.token = token
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        error(409, "username already exists")
    state.cache.set(f"account:{account.id}", token, 24 * 3600)
    return {"token": token}


@router.post("/changePassword")
def change_password(req: ChangePasswordRequest, db: Session = Depends(get_db)):
    account = db.query(Account).filter(Account.username == req.username).first()
    if not account or not auth.check_password(account.password, req.old_password):
        error(400, "unsuccessfully password changed")
    account.password = auth.hash_password(req.new_password)
    account.token = ""
    db.commit()
    state.cache.delete(f"account:{account.id}")
    return {"message": "successfully password changed"}


@router.post("/findByID")
def find_by_id(req: FindByIDRequest, db: Session = Depends(get_db)):
    return account_dict(get_account(db, req.id))


@router.post("/findByUsername")
def find_by_username(req: FindByUsernameRequest, db: Session = Depends(get_db)):
    account = db.query(Account).filter(Account.username == req.username).first()
    if not account:
        error(500, "record not found")
    return account_dict(account)
