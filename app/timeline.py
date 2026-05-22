from __future__ import annotations

from datetime import datetime, timezone
import json
import threading
import time

from . import state
from .models import OutboxMsg
from .mq import publish_timeline
from .serializers import unix_millis


def change_popularity_cache(video_id: int, change: int) -> None:
    if not state.cache.enabled or not video_id or not change:
        return
    state.cache.delete(f"video:detail:id={video_id}")
    minute = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    key = "hot:video:1m:" + minute.strftime("%Y%m%d%H%M")
    state.cache.zincrby(key, change, str(video_id))
    state.cache.expire(key, 2 * 3600)


def add_to_global_timeline(video_id: int, create_time_ms: int) -> None:
    if not state.cache.enabled:
        return
    state.cache.zadd("feed:global_timeline", {str(video_id): float(create_time_ms)})
    state.cache.zremrangebyrank("feed:global_timeline", 0, -1001)


def start_outbox_thread() -> None:
    if not state.mq.enabled:
        return

    def loop():
        while True:
            db = state.SessionLocal()
            try:
                messages = db.query(OutboxMsg).filter(OutboxMsg.status == "pending").order_by(OutboxMsg.create_time).limit(100).all()
                for msg in messages:
                    if publish_timeline(state.mq, msg.video_id, unix_millis(msg.create_time)):
                        db.delete(msg)
                db.commit()
            except Exception:
                db.rollback()
            finally:
                db.close()
            time.sleep(1)

    threading.Thread(target=loop, daemon=True, name="outbox-poller").start()


def start_timeline_consumer_thread() -> None:
    if not state.mq.enabled or not state.cache.enabled:
        return

    def loop():
        try:
            import pika

            credentials = pika.PlainCredentials(state.cfg.rabbitmq.username, state.cfg.rabbitmq.password)
            params = pika.ConnectionParameters(host=state.cfg.rabbitmq.host, port=state.cfg.rabbitmq.port, credentials=credentials)
            conn = pika.BlockingConnection(params)
            ch = conn.channel()
            ch.queue_declare(queue="video.timeline.update.queue", durable=True)

            def callback(channel, method, properties, body):
                try:
                    event = json.loads(body.decode("utf-8"))
                    add_to_global_timeline(int(event.get("video_id") or 0), int(event.get("create_time") or 0))
                    channel.basic_ack(delivery_tag=method.delivery_tag)
                except Exception:
                    channel.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

            ch.basic_qos(prefetch_count=50)
            ch.basic_consume(queue="video.timeline.update.queue", on_message_callback=callback)
            ch.start_consuming()
        except Exception:
            return

    threading.Thread(target=loop, daemon=True, name="timeline-consumer").start()
