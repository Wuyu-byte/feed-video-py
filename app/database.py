from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .config import Config
from .models import Base


def database_url(cfg: Config) -> str:
    db = cfg.database
    return f"mysql+pymysql://{db.user}:{db.password}@{db.host}:{db.port}/{db.dbname}?charset=utf8mb4"


def build_engine(cfg: Config):
    return create_engine(database_url(cfg), pool_pre_ping=True, pool_recycle=1800, future=True)


def migrate(engine) -> None:
    Base.metadata.create_all(bind=engine)


def make_session_factory(engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, future=True)


@contextmanager
def session_scope(factory: sessionmaker[Session]):
    db = factory()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
