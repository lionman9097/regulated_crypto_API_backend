"""
tests/seed_test_data.py
───────────────────────
One-time setup script: fund test accounts and set user tiers so the
integration test suite can place orders without hitting zero-balance guards.

Run ONCE before the test suite (or whenever the DB is reset):

    cd c:\\temp\\crypto-thesis
    python tests/seed_test_data.py

Requires .env.test to be present with a valid DATABASE_URL.
"""

import asyncio
import os
import sys
from decimal import Decimal
from pathlib import Path

# ── path & env setup ──────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env.test", override=True)

# ── app imports ───────────────────────────────────────────────────────────────
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from core.config import AsyncSessionLocal
from models.account import Account
# Import related models so SQLAlchemy can resolve string relationships on User.
from models.order import Order  # noqa: F401
from models.trade import Trade  # noqa: F401
from models.user import User


# Accounts to fund (username → balance in USDT)
FUNDED_ACCOUNTS: dict[str, Decimal] = {
    "trader_1": Decimal("100000"),
    "trader_2": Decimal("100000"),
    "trader_3": Decimal("100000"),
    "user_1":   Decimal("100000"),
}

# Users whose tier needs upgrading for leverage-boundary tests
TIER_UPDATES: dict[str, str] = {
    "trader_2": "professional",
    "trader_3": "institutional",
}


async def seed() -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(User).options(selectinload(User.account))
        )
        users = {u.username: u for u in result.scalars().all()}

        for username, balance in FUNDED_ACCOUNTS.items():
            user = users.get(username)
            if user is None:
                print(f"  SKIP  {username} — user not found (run the app once to seed users)")
                continue
            if user.account is None:
                db.add(Account(user_id=user.id, balance=balance, margin_used=Decimal("0")))
                print(f"  CREATE account for {username}  balance={balance}")
            else:
                user.account.balance = balance
                user.account.margin_used = Decimal("0")
                print(f"  UPDATE {username}  balance={balance}")

        for username, tier in TIER_UPDATES.items():
            user = users.get(username)
            if user:
                user.tier = tier
                print(f"  TIER   {username} -> {tier}")

        await db.commit()
        print("Done.")


if __name__ == "__main__":
    asyncio.run(seed())
