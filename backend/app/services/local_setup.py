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
    """On startup: ensure local user, SimpleFIN connection, and initial sync."""
    user = await get_or_create_local_user(db)
    await _cleanup_orphan_users(db, user)

    conn = (
        await db.execute(select(SimplefinConnection).where(SimplefinConnection.user_id == user.id))
    ).scalar_one_or_none()

    if not conn and (settings.simplefin_access_url or settings.simplefin_token):
        try:
            conn = await sync_service.setup_connection(
                db,
                str(user.id),
                setup_token=settings.simplefin_token,
                access_url=settings.simplefin_access_url,
            )
            await db.flush()
            await sync_service.run_sync(
                db, conn, window_days=settings.transfer_window_days, full_sync=True
            )
            logger.info("Local SimpleFIN setup + sync complete")
        except Exception as e:
            logger.warning(f"Local SimpleFIN setup failed: {e}")
    elif conn and not conn.last_sync_at:
        try:
            await sync_service.run_sync(
                db, conn, window_days=settings.transfer_window_days, full_sync=True
            )
            logger.info("Local SimpleFIN catch-up sync complete")
        except Exception as e:
            logger.warning(f"Local SimpleFIN sync failed: {e}")
