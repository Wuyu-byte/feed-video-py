from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os

import yaml


@dataclass(frozen=True)
class ServerConfig:
    port: int = 8080


@dataclass(frozen=True)
class DatabaseConfig:
    host: str = "localhost"
    port: int = 3307
    user: str = "root"
    password: str = "123456"
    dbname: str = "feedsystem"


@dataclass(frozen=True)
class RedisConfig:
    host: str = "localhost"
    port: int = 6379
    password: str = "123456"
    db: int = 0


@dataclass(frozen=True)
class RabbitMQConfig:
    host: str = "localhost"
    port: int = 5672
    username: str = "admin"
    password: str = "password123"


@dataclass(frozen=True)
class Config:
    server: ServerConfig
    database: DatabaseConfig
    redis: RedisConfig
    rabbitmq: RabbitMQConfig


def _section(data: dict, name: str) -> dict:
    value = data.get(name) or {}
    return value if isinstance(value, dict) else {}


def load_config(path: str | os.PathLike[str] = "configs/config.yaml") -> Config:
    config_path = Path(os.getenv("FEEDSYSTEM_CONFIG", str(path)))
    if not config_path.exists() and not config_path.is_absolute():
        package_root = Path(__file__).resolve().parents[1]
        fallback = package_root / config_path
        if fallback.exists():
            config_path = fallback
    raw: dict = {}
    if config_path.exists():
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}

    server = _section(raw, "server")
    database = _section(raw, "database")
    redis = _section(raw, "redis")
    rabbitmq = _section(raw, "rabbitmq")

    return Config(
        server=ServerConfig(port=int(os.getenv("PORT", server.get("port", 8080)))),
        database=DatabaseConfig(
            host=os.getenv("DB_HOST", database.get("host", "localhost")),
            port=int(os.getenv("DB_PORT", database.get("port", 3307))),
            user=os.getenv("DB_USER", database.get("user", "root")),
            password=os.getenv("DB_PASSWORD", database.get("password", "123456")),
            dbname=os.getenv("DB_NAME", database.get("dbname", "feedsystem")),
        ),
        redis=RedisConfig(
            host=os.getenv("REDIS_HOST", redis.get("host", "localhost")),
            port=int(os.getenv("REDIS_PORT", redis.get("port", 6379))),
            password=os.getenv("REDIS_PASSWORD", redis.get("password", "123456")),
            db=int(os.getenv("REDIS_DB", redis.get("db", 0))),
        ),
        rabbitmq=RabbitMQConfig(
            host=os.getenv("RABBITMQ_HOST", rabbitmq.get("host", "localhost")),
            port=int(os.getenv("RABBITMQ_PORT", rabbitmq.get("port", 5672))),
            username=os.getenv("RABBITMQ_USERNAME", rabbitmq.get("username", "admin")),
            password=os.getenv("RABBITMQ_PASSWORD", rabbitmq.get("password", "password123")),
        ),
    )
