from __future__ import annotations

from datetime import datetime, timezone
import json
import secrets

from .config import RabbitMQConfig


class MQ:
    def __init__(self, connection=None, channel=None):
        self.connection = connection
        self.channel = channel

    @classmethod
    def connect(cls, cfg: RabbitMQConfig) -> "MQ":
        try:
            import pika

            credentials = pika.PlainCredentials(cfg.username, cfg.password)
            params = pika.ConnectionParameters(
                host=cfg.host,
                port=cfg.port,
                credentials=credentials,
                heartbeat=30,
                blocked_connection_timeout=1,
                socket_timeout=1,
                connection_attempts=1,
            )
            connection = pika.BlockingConnection(params)
            channel = connection.channel()
            mq = cls(connection, channel)
            mq.declare_all()
            return mq
        except Exception:
            return cls(None, None)

    @property
    def enabled(self) -> bool:
        return self.channel is not None

    def close(self) -> None:
        try:
            if self.connection and self.connection.is_open:
                self.connection.close()
        except Exception:
            pass

    def declare_topic(self, exchange: str, queue: str, binding: str) -> None:
        if not self.channel:
            return
        self.channel.exchange_declare(exchange=exchange, exchange_type="topic", durable=True)
        self.channel.queue_declare(queue=queue, durable=True)
        self.channel.queue_bind(queue=queue, exchange=exchange, routing_key=binding)

    def declare_all(self) -> None:
        self.declare_topic("social.events", "social.events", "social.*")
        self.declare_topic("like.events", "like.events", "like.*")
        self.declare_topic("comment.events", "comment.events", "comment.*")
        self.declare_topic("video.popularity.events", "video.popularity.events", "video.popularity.*")
        self.declare_topic("video.timeline.events", "video.timeline.update.queue", "video.timeline.*")

    def publish(self, exchange: str, routing_key: str, payload: dict) -> bool:
        if not self.channel:
            return False
        try:
            import pika

            self.channel.basic_publish(
                exchange=exchange,
                routing_key=routing_key,
                body=json.dumps(payload, default=str).encode("utf-8"),
                properties=pika.BasicProperties(content_type="application/json", delivery_mode=2),
            )
            return True
        except Exception:
            return False


def event_id() -> str:
    return secrets.token_hex(16)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def publish_like(mq: MQ, action: str, account_id: int, video_id: int) -> bool:
    return mq.publish(
        "like.events",
        f"like.{action}",
        {"event_id": event_id(), "action": action, "user_id": account_id, "video_id": video_id, "occurred_at": now_iso()},
    )


def publish_comment(mq: MQ, action: str, **payload) -> bool:
    data = {"event_id": event_id(), "action": action, "occurred_at": now_iso(), **payload}
    return mq.publish("comment.events", f"comment.{action}", data)


def publish_popularity(mq: MQ, video_id: int, change: int) -> bool:
    return mq.publish(
        "video.popularity.events",
        "video.popularity.update",
        {"event_id": event_id(), "video_id": video_id, "change": change, "occurred_at": now_iso()},
    )


def publish_timeline(mq: MQ, video_id: int, create_time_ms: int) -> bool:
    return mq.publish(
        "video.timeline.events",
        "video.timeline.publish",
        {"event_id": event_id(), "video_id": video_id, "create_time": create_time_ms, "occurred_at": now_iso()},
    )


def publish_social(mq: MQ, action: str, follower_id: int, vlogger_id: int) -> bool:
    return mq.publish(
        "social.events",
        f"social.{action}",
        {"event_id": event_id(), "action": action, "follower_id": follower_id, "vlogger_id": vlogger_id, "occurred_at": now_iso()},
    )
