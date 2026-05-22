from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from . import state
from .api import account, comment, feed, like, social, video
from .cache import Cache
from .database import migrate
from .deps import http_exception_handler
from .mq import MQ
from .timeline import start_outbox_thread, start_timeline_consumer_thread


@asynccontextmanager
async def lifespan(_: FastAPI):
    migrate(state.engine)
    state.cache = Cache.connect(state.cfg.redis)
    state.mq = MQ.connect(state.cfg.rabbitmq)
    start_outbox_thread()
    start_timeline_consumer_thread()
    try:
        yield
    finally:
        state.mq.close()


def create_app() -> FastAPI:
    app = FastAPI(title="feedsystem_video_py", lifespan=lifespan)
    state.UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(state.UPLOAD_ROOT)), name="static")
    web_root = state.APP_ROOT / "web"
    app.mount("/assets", StaticFiles(directory=str(web_root)), name="assets")

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(web_root / "index.html")

    app.add_exception_handler(HTTPException, http_exception_handler)

    app.include_router(account.router)
    app.include_router(video.router)
    app.include_router(like.router)
    app.include_router(comment.router)
    app.include_router(social.router)
    app.include_router(feed.router)

    return app


app = create_app()


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=state.cfg.server.port, reload=False)
