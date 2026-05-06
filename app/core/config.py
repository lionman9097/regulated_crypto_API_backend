import logging
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from redis.asyncio import Redis


class Settings(BaseSettings):
    app_name: str = "crypto-exchange-poc-backend"
    environment: str = "dev"

    database_url: str = "postgresql+asyncpg://postgres:postgres@postgres:5432/crypto_poc"
    redis_url: str = "redis://redis:6379/0"

    api_keys: str = "beginner-key,intermediate-key,advanced-key"
    rate_limit_per_minute: int = 100
    jwt_secret_key: str = "change-me-poc-secret"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60

    exchange_mode: str = "binance_demo"
    binance_base_url: str = "https://demo-fapi.binance.com"
    binance_api_key: str = ""
    binance_api_secret: str = ""

    global_exposure_threshold: float = 10_000_000.0
    liquidation_threshold: float = 0.25

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)


class Base(DeclarativeBase):
    pass


engine = create_async_engine(settings.database_url, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
redis_client: Redis = Redis.from_url(settings.redis_url, decode_responses=True)


async def get_db_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
