import logging
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from redis.asyncio import Redis


class Settings(BaseSettings):
    app_name: str = "crypto-exchange-poc-backend"
    environment: str = "dev"

    database_url: str
    redis_url: str = "redis://redis:6379/0"

    rate_limit_per_minute: int = 100
    cors_allow_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    jwt_secret_key: str = "change-me-poc-secret"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60
    market_ws_interval_seconds: float = 2.0
    kpi_ws_interval_seconds: float = 5.0

    binance_base_url: str = "https://demo-fapi.binance.com"
    binance_ws_base_url: str = "wss://demo-fstream.binance.com"
    binance_api_key: str = ""
    binance_api_secret: str = ""

    global_exposure_threshold: float = 10_000_000.0
    max_leverage: int = 20

    # KPI alerting thresholds
    alert_latency_ms_threshold: float = 500.0
    alert_error_rate_threshold: float = 0.05          # 5 %
    alert_auth_failure_per_cycle: int = 5             # auth failures per KPI check cycle
    alert_rate_limit_per_cycle: int = 20              # rate-limit hits per KPI check cycle
    alert_liquidation_per_cycle: int = 3              # liquidations per KPI check cycle
    alert_exposure_pct_threshold: float = 80.0        # % of global_exposure_threshold

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
