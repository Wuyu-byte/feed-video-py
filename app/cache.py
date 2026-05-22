from __future__ import annotations

from datetime import timedelta
from typing import Iterable

from .config import RedisConfig


class Cache:
    def __init__(self, client=None):
        self.client = client

    @classmethod
    def connect(cls, cfg: RedisConfig) -> "Cache":
        try:
            import redis

            client = redis.Redis(
                host=cfg.host,
                port=cfg.port,
                password=cfg.password or None,
                db=cfg.db,
                decode_responses=True,
                socket_connect_timeout=0.3,
                socket_timeout=0.3,
            )
            client.ping()
            return cls(client)
        except Exception:
            return cls(None)

    @property
    def enabled(self) -> bool:
        return self.client is not None

    def get(self, key: str) -> str | None:
        if not self.client:
            return None
        try:
            return self.client.get(key)
        except Exception:
            return None

    def set(self, key: str, value: str, ttl_seconds: int | None = None) -> None:
        if not self.client:
            return
        try:
            self.client.set(key, value, ex=ttl_seconds)
        except Exception:
            pass

    def delete(self, *keys: str) -> None:
        if not self.client or not keys:
            return
        try:
            self.client.delete(*keys)
        except Exception:
            pass

    def incr_with_expire(self, key: str, ttl_seconds: int) -> int | None:
        if not self.client:
            return None
        try:
            count = self.client.incr(key)
            if count == 1:
                self.client.expire(key, ttl_seconds)
            return int(count)
        except Exception:
            return None

    def zadd(self, key: str, mapping: dict[str, float]) -> None:
        if not self.client:
            return
        try:
            self.client.zadd(key, mapping)
        except Exception:
            pass

    def zincrby(self, key: str, amount: float, member: str) -> None:
        if not self.client:
            return
        try:
            self.client.zincrby(key, amount, member)
        except Exception:
            pass

    def expire(self, key: str, ttl_seconds: int) -> None:
        if not self.client:
            return
        try:
            self.client.expire(key, ttl_seconds)
        except Exception:
            pass

    def zrevrangebyscore(self, key: str, max_score, min_score, start: int, num: int) -> list[str]:
        if not self.client:
            return []
        try:
            return [str(x) for x in self.client.zrevrangebyscore(key, max_score, min_score, start=start, num=num)]
        except Exception:
            return []

    def zrange_withscores(self, key: str, start: int, stop: int) -> list[tuple[str, float]]:
        if not self.client:
            return []
        try:
            return [(str(m), float(s)) for m, s in self.client.zrange(key, start, stop, withscores=True)]
        except Exception:
            return []

    def zremrangebyrank(self, key: str, start: int, stop: int) -> None:
        if not self.client:
            return
        try:
            self.client.zremrangebyrank(key, start, stop)
        except Exception:
            pass

    def zunionstore(self, dest: str, keys: Iterable[str], aggregate: str = "SUM") -> None:
        if not self.client:
            return
        try:
            self.client.zunionstore(dest, list(keys), aggregate=aggregate)
        except Exception:
            pass

    def zrevrange(self, key: str, start: int, stop: int) -> list[str]:
        if not self.client:
            return []
        try:
            return [str(x) for x in self.client.zrevrange(key, start, stop)]
        except Exception:
            return []

    def exists(self, key: str) -> bool:
        if not self.client:
            return False
        try:
            return bool(self.client.exists(key))
        except Exception:
            return False
