from __future__ import annotations

from pathlib import Path

from .cache import Cache
from .config import Config, load_config
from .database import build_engine, make_session_factory
from .mq import MQ


cfg: Config = load_config()
engine = build_engine(cfg)
SessionLocal = make_session_factory(engine)

cache = Cache()
mq = MQ()

UPLOAD_ROOT = Path(".run/uploads")
