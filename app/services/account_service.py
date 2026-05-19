from decimal import Decimal
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.account import Account, Position
from services.binance_service import binance_service

logger = logging.getLogger(__name__)


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

        account = Account(user_id=user_id, balance=Decimal("0"), margin_used=Decimal("0"))
        db.add(account)
        await db.flush()
        return account

    async def sync_balance_from_exchange(self, db: AsyncSession, user_id: int) -> Account | None:
        """Fetch live balance from Binance and update the local account record."""
        account = await self.get_or_create_account(db, user_id)
        if not binance_service.has_credentials:
            return account
        try:
            data = await binance_service.get_account()
            wallet_balance = data.get("totalWalletBalance")
            logger.info("Binance account response keys: %s", list(data.keys()))
            logger.info("Binance totalWalletBalance: %s", wallet_balance)
            if wallet_balance is not None:
                account.balance = Decimal(str(wallet_balance))
                await db.commit()
                await db.refresh(account)
        except Exception:
            logger.exception("Failed to sync balance from Binance for user_id=%s; using local value", user_id)
        return account

    async def get_positions_with_pnl(
        self, db: AsyncSession, user_id: int
    ) -> list[tuple[Position, float]]:
        """Return each position paired with its current unrealized PnL."""
        # Import here to avoid module-level circular import
        from services.market_service import market_service

        positions = await self.get_positions(db, user_id)
        result: list[tuple[Position, float]] = []
        for pos in positions:
            pnl = 0.0
            if not pos.liquidated:
                try:
                    price = await market_service.get_price(pos.symbol)
                    pnl = float(
                        (Decimal(str(price)) - Decimal(str(pos.entry_price)))
                        * Decimal(str(pos.quantity))
                    )
                except Exception:
                    pass
            result.append((pos, pnl))
        return result


account_service = AccountService()
