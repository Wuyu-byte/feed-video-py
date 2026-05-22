from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class EmptyBody(BaseModel):
    pass


class CreateAccountRequest(BaseModel):
    username: str = ""
    password: str = ""


class LoginRequest(CreateAccountRequest):
    pass


class RenameRequest(BaseModel):
    new_username: str = ""


class ChangePasswordRequest(BaseModel):
    username: str = ""
    old_password: str = ""
    new_password: str = ""


class FindByIDRequest(BaseModel):
    id: int


class FindByUsernameRequest(BaseModel):
    username: str


class PublishVideoRequest(BaseModel):
    title: str = ""
    description: str = ""
    play_url: str = ""
    cover_url: str = ""


class VideoIDRequest(BaseModel):
    video_id: int = 0


class ListByAuthorIDRequest(BaseModel):
    author_id: int = 0


class GetDetailRequest(BaseModel):
    id: int = 0


class PublishCommentRequest(BaseModel):
    video_id: int = 0
    content: str = ""


class DeleteCommentRequest(BaseModel):
    comment_id: int = 0


class GetAllCommentsRequest(BaseModel):
    video_id: int = 0


class FollowRequest(BaseModel):
    vlogger_id: int = 0


class GetAllFollowersRequest(BaseModel):
    vlogger_id: int = 0


class GetAllVloggersRequest(BaseModel):
    follower_id: int = 0


class ListLatestRequest(BaseModel):
    limit: int = 10
    latest_time: int = 0


class ListLikesCountRequest(BaseModel):
    limit: int = 10
    likes_count_before: Optional[int] = None
    id_before: Optional[int] = None


class ListByFollowingRequest(BaseModel):
    limit: int = 10
    latest_time: int = 0


class ListByPopularityRequest(BaseModel):
    limit: int = 10
    as_of: int = 0
    offset: int = 0
    latest_id_before: Optional[int] = None
    latest_popularity: int = 0
    latest_before: Optional[datetime] = None
