from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.account import Position


async def user_exposure(db: AsyncSession, user_id: int) -> Decimal:
    stmt = select(func.coalesce(func.sum(Position.notional), 0)).where(
        Position.user_id == user_id,
        Position.liquidated.is_(False),
    )
    result = await db.execute(stmt)
    return Decimal(result.scalar_one() or 0)


async def global_exposure(db: AsyncSession) -> Decimal:
    stmt = select(func.coalesce(func.sum(Position.notional), 0)).where(Position.liquidated.is_(False))
    result = await db.execute(stmt)
    return Decimal(result.scalar_one() or 0)
