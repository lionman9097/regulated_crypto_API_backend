from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from kpi.aggregator import kpi_aggregator
from schemas.kpi import SecurityKPIResponse, SystemKPIResponse, TradingKPIResponse


router = APIRouter(prefix="/kpi", tags=["kpi"])


@router.get("/system", response_model=SystemKPIResponse)
async def get_system_kpi():
    return kpi_aggregator.system_kpi()


@router.get("/trading", response_model=TradingKPIResponse)
async def get_trading_kpi(db: AsyncSession = Depends(get_db)):
    return await kpi_aggregator.trading_kpi(db)


@router.get("/security", response_model=SecurityKPIResponse)
async def get_security_kpi():
    return kpi_aggregator.security_kpi()
