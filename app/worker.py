from __future__ import annotations

from datetime import datetime
import json
import signal
import threading
import time

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from .cache import Cache
from .config import load_config
from .database import build_engine, make_session_factory
from .models import Comment, Like, Social, Video


cfg = load_config()
engine = build_engine(cfg)
SessionLocal = make_session_factory(engine)
cache = Cache.connect(cfg.redis)
stop = threading.Event()


def change_popularity_cache(video_id: int, change: int) -> None:
    if not cache.enabled or not video_id or not change:
        return
    from datetime import timezone

    cache.delete(f"video:detail:id={video_id}")
    minute = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    key = "hot:video:1m:" + minute.strftime("%Y%m%d%H%M")
    cache.zincrby(key, change, str(video_id))
    cache.expire(key, 2 * 3600)


def connect_channel():
    import pika

    credentials = pika.PlainCredentials(cfg.rabbitmq.username, cfg.rabbitmq.password)
    params = pika.ConnectionParameters(
        host=cfg.rabbitmq.host,
        port=cfg.rabbitmq.port,
        credentials=credentials,
        heartbeat=30,
        blocked_connection_timeout=5,
    )
    conn = pika.BlockingConnection(params)
    ch = conn.channel()
    declare(ch, "social.events", "social.events", "social.*")
    declare(ch, "like.events", "like.events", "like.*")
    declare(ch, "comment.events", "comment.events", "comment.*")
    declare(ch, "video.popularity.events", "video.popularity.events", "video.popularity.*")
    ch.basic_qos(prefetch_count=50)
    return conn, ch


def declare(ch, exchange: str, queue: str, binding: str) -> None:
    ch.exchange_declare(exchange=exchange, exchange_type="topic", durable=True)
    ch.queue_declare(queue=queue, durable=True)
    ch.queue_bind(queue=queue, exchange=exchange, routing_key=binding)


def consume(queue: str, handler):
    while not stop.is_set():
        try:
            conn, ch = connect_channel()

            def callback(channel, method, properties, body):
                try:
                    payload = json.loads(body.decode("utf-8"))
                    handler(payload)
                    channel.basic_ack(delivery_tag=method.delivery_tag)
                except Exception:
                    channel.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

            ch.basic_consume(queue=queue, on_message_callback=callback)
            ch.start_consuming()
        except Exception:
            time.sleep(2)


def handle_social(event: dict) -> None:
    follower_id = int(event.get("follower_id") or 0)
    vlogger_id = int(event.get("vlogger_id") or 0)
    if not follower_id or not vlogger_id:
        return
    db = SessionLocal()
    try:
        if event.get("action") == "follow":
            db.add(Social(follower_id=follower_id, vlogger_id=vlogger_id))
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
        elif event.get("action") == "unfollow":
            db.query(Social).filter(Social.follower_id == follower_id, Social.vlogger_id == vlogger_id).delete()
            db.commit()
    finally:
        db.close()


def handle_like(event: dict) -> None:
    account_id = int(event.get("user_id") or 0)
    video_id = int(event.get("video_id") or 0)
    if not account_id or not video_id:
        return
    db = SessionLocal()
    try:
        if db.query(Video.id).filter(Video.id == video_id).first() is None:
            return
        if event.get("action") == "like":
            db.add(Like(video_id=video_id, account_id=account_id, created_at=datetime.utcnow()))
            try:
                db.flush()
            except IntegrityError:
                db.rollback()
                return
            db.query(Video).filter(Video.id == video_id).update(
                {Video.likes_count: Video.likes_count + 1, Video.popularity: Video.popularity + 1},
                synchronize_session=False,
            )
            db.commit()
        elif event.get("action") == "unlike":
            deleted = db.query(Like).filter(Like.video_id == video_id, Like.account_id == account_id).delete()
            if deleted:
                db.query(Video).filter(Video.id == video_id).update(
                    {
                        Video.likes_count: func.greatest(Video.likes_count - 1, 0),
                        Video.popularity: func.greatest(Video.popularity - 1, 0),
                    },
                    synchronize_session=False,
                )
            db.commit()
    finally:
        db.close()


def handle_comment(event: dict) -> None:
    db = SessionLocal()
    try:
        action = event.get("action")
        if action == "publish":
            video_id = int(event.get("video_id") or 0)
            author_id = int(event.get("author_id") or 0)
            content = str(event.get("content") or "").strip()
            if not video_id or not author_id or not content:
                return
            if db.query(Video.id).filter(Video.id == video_id).first() is None:
                return
            db.add(
                Comment(
                    username=str(event.get("username") or "").strip(),
                    video_id=video_id,
                    author_id=author_id,
                    content=content,
                )
            )
            db.query(Video).filter(Video.id == video_id).update({Video.popularity: Video.popularity + 1}, synchronize_session=False)
            db.commit()
        elif action == "delete":
            comment_id = int(event.get("comment_id") or 0)
            if comment_id:
                db.query(Comment).filter(Comment.id == comment_id).delete()
                db.commit()
    finally:
        db.close()


def handle_popularity(event: dict) -> None:
    video_id = int(event.get("video_id") or 0)
    change = int(event.get("change") or 0)
    if video_id and change:
        change_popularity_cache(video_id, change)


def main() -> None:
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    workers = [
        threading.Thread(target=consume, args=("social.events", handle_social), daemon=True),
        threading.Thread(target=consume, args=("like.events", handle_like), daemon=True),
        threading.Thread(target=consume, args=("comment.events", handle_comment), daemon=True),
        threading.Thread(target=consume, args=("video.popularity.events", handle_popularity), daemon=True),
    ]
    for worker in workers:
        worker.start()
    while not stop.is_set():
        time.sleep(1)


if __name__ == "__main__":
    main()
