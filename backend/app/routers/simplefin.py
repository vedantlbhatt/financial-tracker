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
from app.services import sync_service, quota_service
from app.services.simplefin_errors import filter_connection_errors, has_rate_limit_error
from app.services.quota_service import QuotaExceededError
from app.services.simplefin_service import SimplefinError

router = APIRouter(prefix="/simplefin", tags=["simplefin"])
settings = get_settings()


class QuotaInfo(BaseModel):
    requests_used_today: int
    requests_remaining_today: int
    daily_request_limit: int


class ConnectionStatus(BaseModel):
    connected: bool
    status: str | None
    last_sync_at: str | None
    account_errors: list | None
    quota: QuotaInfo | None = None


class SetupRequest(BaseModel):
    setup_token: str | None = None
    access_url: str | None = None


class SyncResponse(BaseModel):
    message: str
    new_transactions: int | None = None
    api_calls: int | None = None
    quota: QuotaInfo | None = None


async def _ensure_settings(db: AsyncSession, user: User) -> UserSettings:
    if user.settings:
        return user.settings
    s = UserSettings(user_id=user.id, transfer_window_days=settings.transfer_window_days)
    db.add(s)
    await db.flush()
    return s


async def _status_for_connection(db: AsyncSession, conn: SimplefinConnection | None) -> ConnectionStatus:
    if not conn:
        return ConnectionStatus(connected=False, status=None, last_sync_at=None, account_errors=None)

    stored_errors = conn.account_errors
    connection_errors = filter_connection_errors(stored_errors)
    if has_rate_limit_error(stored_errors) and not connection_errors and conn.status == "needs_attention":
        conn.account_errors = None
        conn.status = "active"
        await db.flush()

    quota = await quota_service.quota_snapshot(db, conn.id)
    return ConnectionStatus(
        connected=True,
        status=conn.status,
        last_sync_at=conn.last_sync_at.isoformat() if conn.last_sync_at else None,
        account_errors=connection_errors if connection_errors else None,
        quota=QuotaInfo(**quota),
    )


@router.get("/status", response_model=ConnectionStatus)
async def connection_status(
    current_user: User = Depends(get_local_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SimplefinConnection).where(SimplefinConnection.user_id == current_user.id)
    )
    conn = result.scalar_one_or_none()
    return await _status_for_connection(db, conn)


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
                try:
                    await sync_service.run_sync(
                        session, c, window_days=user_settings.transfer_window_days, full_sync=True
                    )
                except QuotaExceededError:
                    pass

    background_tasks.add_task(_initial_sync)

    return await _status_for_connection(db, conn)


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
    except QuotaExceededError as e:
        raise HTTPException(
            status_code=429,
            detail=str(e),
        ) from e
    except SimplefinError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    quota = QuotaInfo(
        requests_used_today=summary["requests_used_today"],
        requests_remaining_today=summary["requests_remaining_today"],
        daily_request_limit=summary["daily_request_limit"],
    )
    return SyncResponse(
        message="Sync complete",
        new_transactions=summary.get("new_transactions"),
        api_calls=summary.get("api_calls"),
        quota=quota,
    )
