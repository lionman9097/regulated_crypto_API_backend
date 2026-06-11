from contextlib import asynccontextmanager
from decimal import Decimal
import asyncio
import logging
from datetime import datetime, UTC

from fastapi import FastAPI

logger = logging.getLogger(__name__)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import select, text
from sqlalchemy.orm import selectinload

from api.routes.account import router as account_router
from api.routes.api_keys import router as api_keys_router
from api.routes.auth import router as auth_router
from audit.routes import router as audit_router
from api.routes.kpi import router as kpi_router
from api.routes.market import router as market_router
from api.routes.order import router as order_router
from api.routes.regulator import router as regulator_router
from audit.model import AuditLog  # noqa: F401 â€” imported so Base.metadata includes the table
from core.config import AsyncSessionLocal, Base, engine, settings
from alerts.model import KpiAlert  # noqa: F401 -- imported so Base.metadata includes the table
from alerts.routes import router as alerts_router
from api_keys.model import ApiKey  # noqa: F401 -- imported so Base.metadata includes the table
from kpi.alerting import alerting_service

from kpi.aggregator import kpi_aggregator
from middleware.auth import AuthMiddleware
from middleware.logging import LoggingMiddleware
from middleware.rate_limit import RateLimitMiddleware
from models.account import Account
from models.user import User
from realtime.ws_hub import ws_hub
from services.binance_service import binance_service
from services.market_service import market_service
from services.market_stream import market_stream
from services.kline_stream import kline_stream
from services.user_data_stream import user_data_stream


async def seed_initial_data() -> None:
    from core.security import hash_password
    
    async with AsyncSessionLocal() as session:
        # Ensure predictable demo users always exist with known passwords.
        default_users = [
            ("trader_1", "password123", "standard", "trader"),
            ("trader_2", "password456", "standard", "trader"),
            ("trader_3", "password789", "standard", "trader"),
            ("user_1",   "password123", "standard", "trader"),
            ("user_2",   "password456", "standard", "trader"),
            ("user_3",   "password789", "standard", "trader"),
            ("admin_1",  "adminpass1",  "standard", "admin"),
            ("regulator_1", "regulatorpass1", "standard", "regulator"),
        ]

        users_result = await session.execute(
            select(User).options(selectinload(User.account))
        )
        users_by_username = {user.username: user for user in users_result.scalars().all()}

        new_users: list[User] = []
        existing_users: list[User] = []
        for username, password, tier, role in default_users:
            user = users_by_username.get(username)
            if user is None:
                user = User(
                    username=username,
                    password_hash=hash_password(password),
                    tier=tier,
                    role=role,
                )
                session.add(user)
                new_users.append(user)
            else:
                user.password_hash = hash_password(password)
                user.tier = tier
                user.role = role
                existing_users.append(user)

        await session.flush()

        # New users never have an account yet - safe to add without lazy-load
        for user in new_users:
            session.add(
                Account(
                    user_id=user.id,
                    balance=Decimal("0"),
                    margin_used=Decimal("0"),
                )
            )

        # Existing users were eagerly loaded above - account is already in memory
        for user in existing_users:
            if user.account is None:
                session.add(
                    Account(
                        user_id=user.id,
                        balance=Decimal("0"),
                        margin_used=Decimal("0"),
                    )
                )

        await session.commit()


async def market_stream_publisher() -> None:
    while True:
        updated = await market_service.tick()
        if updated:
            await ws_hub.broadcast_market(
                {
                    "type": "market_snapshot",
                    "prices": [
                        {
                            "symbol": item_symbol,
                            "price": item_data["price"],
                            "timestamp": item_data["timestamp"].isoformat(),
                        }
                        for item_symbol, item_data in updated.items()
                    ],
                }
            )
        await asyncio.sleep(settings.market_ws_interval_seconds)


async def kpi_stream_publisher() -> None:
    while True:
        async with AsyncSessionLocal() as session:
            trading_kpi = await kpi_aggregator.trading_kpi(session)

        system_kpi = kpi_aggregator.system_kpi()
        security_kpi = kpi_aggregator.security_kpi()

        await alerting_service.check_thresholds(system_kpi, security_kpi, trading_kpi)

        await ws_hub.broadcast_kpi(
            {
                "type": "kpi_snapshot",
                "timestamp": datetime.now(UTC).isoformat(),
                "system": system_kpi,
                "security": security_kpi,
                "trading": trading_kpi,
            }
        )
        await asyncio.sleep(settings.kpi_ws_interval_seconds)


async def apply_schema_compat_migrations() -> None:
    """Apply minimal compatibility migrations for legacy local databases."""
    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                ALTER TABLE IF EXISTS users
                ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255)
                """
            )
        )
        await conn.execute(
            text(
                """
                DO $$
                BEGIN
                    IF EXISTS (
                        SELECT 1
                        FROM information_schema.columns
                        WHERE table_name = 'users' AND column_name = 'api_key'
                    ) THEN
                        ALTER TABLE users ALTER COLUMN api_key DROP NOT NULL;
                    END IF;
                END $$;
                """
            )
        )
        await conn.execute(
            text(
                """
                ALTER TABLE IF EXISTS positions
                ADD COLUMN IF NOT EXISTS margin_type VARCHAR(16) NOT NULL DEFAULT 'CROSSED';
                """
            )
        )
        await conn.execute(
            text(
                """
                ALTER TABLE IF EXISTS users
                ADD COLUMN IF NOT EXISTS role VARCHAR(32) NOT NULL DEFAULT 'trader';
                """
            )
        )
        await conn.execute(
            text(
                """
                ALTER TABLE IF EXISTS audit_logs
                ADD COLUMN IF NOT EXISTS prev_hash TEXT;
                """
            )
        )
        await conn.execute(
            text(
                """
                ALTER TABLE IF EXISTS audit_logs
                ADD COLUMN IF NOT EXISTS row_hash TEXT;
                """
            )
        )
        await conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_audit_logs_row_hash
                ON audit_logs (row_hash)
                WHERE row_hash IS NOT NULL;
                """
            )
        )


@asynccontextmanager
async def lifespan(_: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await apply_schema_compat_migrations()
    await seed_initial_data()

    await binance_service.sync_server_time()

    market_task = asyncio.create_task(market_stream_publisher())
    kpi_task = asyncio.create_task(kpi_stream_publisher())
    user_data_task = asyncio.create_task(user_data_stream.start())
    market_stream_task = asyncio.create_task(market_stream.start())
    kline_stream_task = asyncio.create_task(kline_stream.start())
    try:
        yield
    finally:
        market_task.cancel()
        kpi_task.cancel()
        user_data_task.cancel()
        market_stream_task.cancel()
        kline_stream_task.cancel()
        await user_data_stream.stop()
        await market_stream.stop()
        await kline_stream.stop()
        await asyncio.gather(
            market_task, kpi_task, user_data_task, market_stream_task, kline_stream_task,
            return_exceptions=True,
        )


app = FastAPI(
    title="Crypto Exchange POC Backend",
    description="Simulation backend for API governance, risk-based leverage control, and KPI observability.",
    version="1.0.0",
    lifespan=lifespan,
)

cors_origins = [origin.strip() for origin in settings.cors_allow_origins.split(",") if origin.strip()]
logger.info("RAW CORS_ALLOW_ORIGINS = %r", settings.cors_allow_origins)
logger.info("CORS allow_origins = %s", cors_origins)
# Ensure the deploy origin is always present regardless of env-var loading quirks
_DEPLOY_ORIGIN = "http://172.10.10.227:3988"
if _DEPLOY_ORIGIN not in cors_origins:
    cors_origins.append(_DEPLOY_ORIGIN)
    logger.info("CORS: forcibly added %s", _DEPLOY_ORIGIN)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins or ["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(AuthMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(LoggingMiddleware)

app.include_router(order_router)
app.include_router(account_router)
app.include_router(market_router)
app.include_router(kpi_router)
app.include_router(auth_router)
app.include_router(audit_router)
app.include_router(alerts_router)
app.include_router(regulator_router)
app.include_router(api_keys_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/metrics")
async def metrics() -> PlainTextResponse:
    return PlainTextResponse(generate_latest().decode("utf-8"), media_type=CONTENT_TYPE_LATEST)

