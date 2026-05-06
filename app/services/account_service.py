from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.account import Account, Position


class AccountService:
    async def get_account(self, db: AsyncSession, user_id: int) -> Account | None:
        stmt = select(Account).where(Account.user_id == user_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_positions(self, db: AsyncSession, user_id: int) -> list[Position]:
        stmt = select(Position).where(Position.user_id == user_id)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_or_create_account(self, db: AsyncSession, user_id: int) -> Account:
        account = await self.get_account(db, user_id)
        if account:
            return account

        account = Account(user_id=user_id, balance=Decimal("100000"), margin_used=Decimal("0"))
        db.add(account)
        await db.flush()
        return account


account_service = AccountService()
