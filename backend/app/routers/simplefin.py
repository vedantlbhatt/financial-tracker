from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.middleware.auth_middleware import get_local_user
from app.models.user import User
from app.models.simplefin_connection import SimplefinConnection
from app.models.user_settings import UserSettings
from app.services import sync_service
from app.services.simplefin_service import SimplefinError

router = APIRouter(prefix="/simplefin", tags=["simplefin"])
settings = get_settings()


class ConnectionStatus(BaseModel):
    connected: bool
    status: str | None
    last_sync_at: str | None
    account_errors: list | None


class SetupRequest(BaseModel):
    setup_token: str | None = None
    access_url: str | None = None


class SyncResponse(BaseModel):
    message: str
    new_transactions: int | None = None


async def _ensure_settings(db: AsyncSession, user: User) -> UserSettings:
    if user.settings:
        return user.settings
    s = UserSettings(user_id=user.id, transfer_window_days=settings.transfer_window_days)
    db.add(s)
    await db.flush()
    return s


@router.get("/status", response_model=ConnectionStatus)
async def connection_status(
    current_user: User = Depends(get_local_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SimplefinConnection).where(SimplefinConnection.user_id == current_user.id)
    )
    conn = result.scalar_one_or_none()
    if not conn:
        return ConnectionStatus(connected=False, status=None, last_sync_at=None, account_errors=None)
    return ConnectionStatus(
        connected=True,
        status=conn.status,
        last_sync_at=conn.last_sync_at.isoformat() if conn.last_sync_at else None,
        account_errors=conn.account_errors,
    )


@router.post("/setup", response_model=ConnectionStatus)
async def setup_simplefin(
    body: SetupRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_local_user),
    db: AsyncSession = Depends(get_db),
):
    token = body.setup_token or settings.simplefin_token
    access_url = body.access_url or settings.simplefin_access_url
    if not token and not access_url:
        raise HTTPException(status_code=400, detail="No SimpleFIN token or access URL provided")

    try:
        conn = await sync_service.setup_connection(
            db, str(current_user.id), setup_token=token, access_url=access_url
        )
        await _ensure_settings(db, current_user)
        await db.commit()
    except SimplefinError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    user_settings = await _ensure_settings(db, current_user)

    async def _initial_sync():
        from app.database import AsyncSessionLocal
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(SimplefinConnection).where(SimplefinConnection.user_id == current_user.id)
            )
            c = result.scalar_one_or_none()
            if c:
                await sync_service.run_sync(
                    session, c, window_days=user_settings.transfer_window_days, full_sync=True
                )

    background_tasks.add_task(_initial_sync)

    return ConnectionStatus(
        connected=True,
        status=conn.status,
        last_sync_at=None,
        account_errors=None,
    )


@router.post("/sync", response_model=SyncResponse)
async def trigger_sync(
    current_user: User = Depends(get_local_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SimplefinConnection).where(SimplefinConnection.user_id == current_user.id)
    )
    conn = result.scalar_one_or_none()
    if not conn:
        raise HTTPException(status_code=404, detail="SimpleFIN not connected")

    window = settings.transfer_window_days
    if current_user.settings:
        window = current_user.settings.transfer_window_days

    try:
        summary = await sync_service.run_sync(db, conn, window_days=window)
    except SimplefinError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    return SyncResponse(
        message="Sync complete",
        new_transactions=summary.get("new_transactions"),
    )
