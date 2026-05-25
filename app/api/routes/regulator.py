from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, WebSocket, WebSocketDisconnect, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db, require_roles
from audit.service import emit
from core.security import decode_access_token
from realtime.ws_hub import ws_hub
from services.regulator_service import regulator_service

router = APIRouter(prefix="/regulator", tags=["regulator"])

_RBAC = [require_roles("admin", "regulator")]


@router.get("/overview", dependencies=_RBAC)
async def get_overview(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """System-wide compliance snapshot: users, positions, exposure, liquidations, alerts."""
    emit(
        "REGULATOR_ACCESS",
        actor_id=getattr(request.state, "user_id", None),
        actor_username=getattr(request.state, "jwt_payload", {}).get("username"),
        ip_address=request.client.host if request.client else None,
        event_data={"endpoint": "/regulator/overview"},
    )
    return await regulator_service.get_overview(db)


@router.get("/positions", dependencies=_RBAC)
async def list_all_positions(
    request: Request,
    symbol: str | None = Query(None, description="Filter by symbol, e.g. BTCUSDT"),
    user_id: int | None = Query(None, description="Filter by user ID"),
    include_liquidated: bool = Query(False, description="Include liquidated positions"),
    limit: int = Query(default=200, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """All positions across all accounts — supports regulator surveillance queries."""
    emit(
        "REGULATOR_ACCESS",
        actor_id=getattr(request.state, "user_id", None),
        actor_username=getattr(request.state, "jwt_payload", {}).get("username"),
        ip_address=request.client.host if request.client else None,
        event_data={"endpoint": "/regulator/positions", "symbol": symbol, "user_id": user_id},
    )
    positions = await regulator_service.get_all_positions(
        db,
        symbol=symbol,
        user_id=user_id,
        include_liquidated=include_liquidated,
        limit=limit,
    )
    return [
        {
            "id": p.id,
            "user_id": p.user_id,
            "account_id": p.account_id,
            "symbol": p.symbol,
            "quantity": str(p.quantity),
            "entry_price": str(p.entry_price),
            "notional": str(p.notional),
            "margin": str(p.margin),
            "margin_type": p.margin_type,
            "liquidated": p.liquidated,
            "updated_at": p.updated_at.isoformat() if p.updated_at else None,
        }
        for p in positions
    ]


@router.get("/exposure", dependencies=_RBAC)
async def get_exposure_breakdown(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Per-symbol aggregate notional exposure across all live positions."""
    emit(
        "REGULATOR_ACCESS",
        actor_id=getattr(request.state, "user_id", None),
        actor_username=getattr(request.state, "jwt_payload", {}).get("username"),
        ip_address=request.client.host if request.client else None,
        event_data={"endpoint": "/regulator/exposure"},
    )
    return await regulator_service.get_exposure_breakdown(db)


@router.get("/liquidations", dependencies=_RBAC)
async def get_liquidation_history(
    request: Request,
    symbol: str | None = Query(None, description="Filter by symbol"),
    user_id: int | None = Query(None, description="Filter by user ID"),
    limit: int = Query(default=200, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Historical record of all liquidated positions."""
    emit(
        "REGULATOR_ACCESS",
        actor_id=getattr(request.state, "user_id", None),
        actor_username=getattr(request.state, "jwt_payload", {}).get("username"),
        ip_address=request.client.host if request.client else None,
        event_data={"endpoint": "/regulator/liquidations", "symbol": symbol, "user_id": user_id},
    )
    positions = await regulator_service.get_liquidation_history(
        db, symbol=symbol, user_id=user_id, limit=limit
    )
    return [
        {
            "id": p.id,
            "user_id": p.user_id,
            "account_id": p.account_id,
            "symbol": p.symbol,
            "quantity": str(p.quantity),
            "entry_price": str(p.entry_price),
            "notional": str(p.notional),
            "margin": str(p.margin),
            "margin_type": p.margin_type,
            "liquidated_at": p.updated_at.isoformat() if p.updated_at else None,
        }
        for p in positions
    ]


@router.get("/users", dependencies=_RBAC)
async def list_users(
    request: Request,
    role: str | None = Query(None, description="Filter by role (trader|admin|regulator)"),
    limit: int = Query(default=200, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """User roster with roles and account balances."""
    emit(
        "REGULATOR_ACCESS",
        actor_id=getattr(request.state, "user_id", None),
        actor_username=getattr(request.state, "jwt_payload", {}).get("username"),
        ip_address=request.client.host if request.client else None,
        event_data={"endpoint": "/regulator/users", "role_filter": role},
    )
    users = await regulator_service.get_users(db, role=role, limit=limit)
    return [
        {
            "id": u.id,
            "username": u.username,
            "role": u.role,
            "tier": u.tier,
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "account": {
                "balance": str(u.account.balance) if u.account else None,
                "margin_used": str(u.account.margin_used) if u.account else None,
            } if u.account is not None else None,
        }
        for u in users
    ]


@router.websocket("/stream")
async def regulator_stream(websocket: WebSocket) -> None:
    """Live WebSocket feed delivering compliance alerts and KPI events to regulators.

    Authentication: pass the JWT as a query parameter: ``?token=<jwt>``
    Required role: ``admin`` or ``regulator``
    """
    token = websocket.query_params.get("token", "")
    if not token:
        await websocket.close(code=4401, reason="Missing token")
        return

    try:
        payload = decode_access_token(token)
    except ValueError:
        await websocket.close(code=4401, reason="Invalid token")
        return

    role = payload.get("role", "trader")
    if role not in ("admin", "regulator"):
        await websocket.close(code=4403, reason="Insufficient role")
        return

    await ws_hub.connect_regulator(websocket)

    emit(
        "REGULATOR_ACCESS",
        actor_id=int(payload.get("sub", 0)) or None,
        actor_username=payload.get("username"),
        event_data={"endpoint": "/regulator/stream", "action": "connect"},
    )

    try:
        # Send an initial snapshot so the client has data immediately.
        await websocket.send_json(
            {
                "type": "regulator_connected",
                "timestamp": datetime.now(UTC).isoformat(),
                "message": "Regulator stream active. You will receive compliance alerts and KPI snapshots.",
            }
        )
        # Keep the connection open; the hub pushes data proactively.
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_hub.disconnect_regulator(websocket)
    except Exception:
        ws_hub.disconnect_regulator(websocket)
