from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from core.security import decode_access_token
from kpi.aggregator import kpi_aggregator
from realtime.ws_hub import ws_hub
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


@router.websocket("/stream")
async def kpi_stream(websocket: WebSocket):
    token = websocket.query_params.get("token", "")
    if not token:
        await websocket.close(code=4401, reason="Missing token")
        return

    try:
        decode_access_token(token)
    except ValueError:
        await websocket.close(code=4401, reason="Invalid token")
        return

    await ws_hub.connect_kpi(websocket)

    try:
        await websocket.send_json(
            {
                "type": "kpi_snapshot",
                "system": kpi_aggregator.system_kpi(),
                "security": kpi_aggregator.security_kpi(),
            }
        )

        while True:
            # Keep the socket open until the client disconnects.
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_hub.disconnect_kpi(websocket)
    except Exception:
        ws_hub.disconnect_kpi(websocket)
