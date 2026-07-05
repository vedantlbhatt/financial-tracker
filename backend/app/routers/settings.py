from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.middleware.auth_middleware import get_local_user
from app.models.user import User
from app.models.user_settings import UserSettings
from app.models.simplefin_connection import SimplefinConnection
from app.models.merchant_category_rule import MerchantCategoryRule
from app.models.category_override import CategoryOverride
from app.services import sync_service
from app.services.category_service import CATEGORIES

router = APIRouter(prefix="/settings", tags=["settings"])
settings = get_settings()


class SettingsResponse(BaseModel):
    transfer_window_days: int
    simplefin_connected: bool
    simplefin_status: str | None
    last_sync_at: str | None


class SettingsUpdateRequest(BaseModel):
    transfer_window_days: int | None = None


class SimplefinSetupRequest(BaseModel):
    setup_token: str | None = None
    access_url: str | None = None


class RuleResponse(BaseModel):
    id: str
    pattern: str
    category: str
    is_regex: bool


@router.get("", response_model=SettingsResponse)
async def get_settings_view(
    current_user: User = Depends(get_local_user),
    db: AsyncSession = Depends(get_db),
):
    conn_result = await db.execute(
        select(SimplefinConnection).where(SimplefinConnection.user_id == current_user.id)
    )
    conn = conn_result.scalar_one_or_none()

    settings_result = await db.execute(
        select(UserSettings).where(UserSettings.user_id == current_user.id)
    )
    user_settings = settings_result.scalar_one_or_none()
    if not user_settings:
        user_settings = UserSettings(
            user_id=current_user.id,
            transfer_window_days=settings.transfer_window_days,
        )
        db.add(user_settings)

    return SettingsResponse(
        transfer_window_days=user_settings.transfer_window_days,
        simplefin_connected=conn is not None,
        simplefin_status=conn.status if conn else None,
        last_sync_at=conn.last_sync_at.isoformat() if conn and conn.last_sync_at else None,
    )


@router.patch("", response_model=SettingsResponse)
async def update_settings(
    body: SettingsUpdateRequest,
    current_user: User = Depends(get_local_user),
    db: AsyncSession = Depends(get_db),
):
    settings_result = await db.execute(
        select(UserSettings).where(UserSettings.user_id == current_user.id)
    )
    user_settings = settings_result.scalar_one_or_none()
    if not user_settings:
        user_settings = UserSettings(user_id=current_user.id)
        db.add(user_settings)

    if body.transfer_window_days is not None:
        if body.transfer_window_days < 0 or body.transfer_window_days > 14:
            raise HTTPException(status_code=400, detail="Transfer window must be 0-14 days")
        user_settings.transfer_window_days = body.transfer_window_days

    conn_result = await db.execute(
        select(SimplefinConnection).where(SimplefinConnection.user_id == current_user.id)
    )
    conn = conn_result.scalar_one_or_none()

    return SettingsResponse(
        transfer_window_days=user_settings.transfer_window_days,
        simplefin_connected=conn is not None,
        simplefin_status=conn.status if conn else None,
        last_sync_at=conn.last_sync_at.isoformat() if conn and conn.last_sync_at else None,
    )


@router.post("/simplefin/reconnect")
async def reconnect_simplefin(
    body: SimplefinSetupRequest,
    current_user: User = Depends(get_local_user),
    db: AsyncSession = Depends(get_db),
):
    from app.services.simplefin_service import SimplefinError

    token = body.setup_token or settings.simplefin_token
    access_url = body.access_url or settings.simplefin_access_url
    if not token and not access_url:
        raise HTTPException(status_code=400, detail="Provide setup_token or access_url")

    try:
        conn = await sync_service.setup_connection(
            db, str(current_user.id), setup_token=token, access_url=access_url
        )
        window_result = await db.execute(
            select(UserSettings.transfer_window_days).where(UserSettings.user_id == current_user.id)
        )
        window = window_result.scalar_one_or_none() or settings.transfer_window_days
        await sync_service.run_sync(db, conn, window_days=window, full_sync=True)
    except SimplefinError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return {"message": "SimpleFIN reconnected and synced"}


@router.get("/category-rules", response_model=list[RuleResponse])
async def list_category_rules(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(MerchantCategoryRule).order_by(MerchantCategoryRule.priority)
    )
    return [
        RuleResponse(id=str(r.id), pattern=r.pattern, category=r.category, is_regex=r.is_regex)
        for r in result.scalars()
    ]


@router.get("/categories", response_model=list[str])
async def list_categories():
    return CATEGORIES
