from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from schemas.account import AccountSummary, PositionView
from services.account_service import account_service


router = APIRouter(prefix="/account", tags=["account"])


@router.get("/{user_id}", response_model=AccountSummary)
async def get_account_summary(user_id: int, db: AsyncSession = Depends(get_db)):
    account = await account_service.get_account(db, user_id)
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

    positions = await account_service.get_positions(db, user_id)
    available_margin = Decimal(account.balance) - Decimal(account.margin_used)

    return {
        "user_id": user_id,
        "balance": float(account.balance),
        "margin_used": float(account.margin_used),
        "available_margin": float(available_margin),
        "positions": [
            PositionView(
                symbol=position.symbol,
                quantity=float(position.quantity),
                entry_price=float(position.entry_price),
                notional=float(position.notional),
                margin=float(position.margin),
                liquidated=position.liquidated,
            )
            for position in positions
        ],
    }
