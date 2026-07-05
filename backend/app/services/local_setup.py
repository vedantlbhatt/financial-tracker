"""Single-user local mode — no login required."""
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.user import User
from app.models.user_settings import UserSettings
from app.models.simplefin_connection import SimplefinConnection
from app.services import sync_service

logger = logging.getLogger(__name__)
settings = get_settings()

LOCAL_USER_EMAIL = "local@finance"


async def get_or_create_local_user(db: AsyncSession) -> User:
    # Reuse the first user in the DB so existing synced data isn't orphaned
    result = await db.execute(select(User).order_by(User.created_at).limit(1))
    user = result.scalar_one_or_none()
    if user:
        return user

    user = User(email=LOCAL_USER_EMAIL, hashed_password="local")
    db.add(user)
    await db.flush()
    db.add(UserSettings(user_id=user.id, transfer_window_days=settings.transfer_window_days))
    await db.flush()
    logger.info("Created local user")
    return user


async def _cleanup_orphan_users(db: AsyncSession, canonical_user: User) -> None:
    """Remove extra users created during earlier auth/local setup experiments."""
    orphans = (
        await db.execute(select(User).where(User.id != canonical_user.id))
    ).scalars().all()
    for orphan in orphans:
        await db.delete(orphan)
        logger.info("Removed orphan user %s", orphan.email)
    if orphans:
        await db.flush()


async def ensure_local_ready(db: AsyncSession) -> None:
    """On startup: ensure local user and SimpleFIN connection — no automatic bank sync."""
    user = await get_or_create_local_user(db)
    await _cleanup_orphan_users(db, user)

    conn = (
        await db.execute(select(SimplefinConnection).where(SimplefinConnection.user_id == user.id))
    ).scalar_one_or_none()

    if not conn and (settings.simplefin_access_url or settings.simplefin_token):
        try:
            await sync_service.setup_connection(
                db,
                str(user.id),
                setup_token=settings.simplefin_token,
                access_url=settings.simplefin_access_url,
            )
            logger.info("Local SimpleFIN connection saved — sync manually in Settings to pull bank data")
        except Exception as e:
            logger.warning(f"Local SimpleFIN setup failed: {e}")
