from contextlib import asynccontextmanager
from decimal import Decimal

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import select

from api.routes.account import router as account_router
from api.routes.auth import router as auth_router
from api.routes.kpi import router as kpi_router
from api.routes.market import router as market_router
from api.routes.order import router as order_router
from core.config import AsyncSessionLocal, Base, engine, settings
from middleware.auth import AuthMiddleware
from middleware.logging import LoggingMiddleware
from middleware.rate_limit import RateLimitMiddleware
from models.account import Account
from models.user import User


async def seed_initial_data() -> None:
    async with AsyncSessionLocal() as session:
        existing = await session.execute(select(User.id).limit(1))
        if existing.scalar_one_or_none() is not None:
            return

        raw_keys = [key.strip() for key in settings.api_keys.split(",") if key.strip()]
        api_keys = raw_keys or ["local-dev-key"]
        users = [
            User(username=f"user_{idx + 1}", api_key=api_key, tier="standard")
            for idx, api_key in enumerate(api_keys)
        ]
        session.add_all(users)
        await session.flush()

        accounts = [
            Account(user_id=user.id, balance=Decimal("100000"), margin_used=Decimal("0"))
            for user in users
        ]
        session.add_all(accounts)
        await session.commit()


@asynccontextmanager
async def lifespan(_: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await seed_initial_data()
    yield


app = FastAPI(
    title="Crypto Exchange POC Backend",
    description="Simulation backend for API governance, risk-based leverage control, and KPI observability.",
    version="1.0.0",
    lifespan=lifespan,
)

cors_origins = [origin.strip() for origin in settings.cors_allow_origins.split(",") if origin.strip()]
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


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/metrics")
async def metrics() -> PlainTextResponse:
    return PlainTextResponse(generate_latest().decode("utf-8"), media_type=CONTENT_TYPE_LATEST)
