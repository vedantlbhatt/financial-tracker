"""APScheduler background worker — polls SimpleFIN every few hours."""
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select

from app.config import get_settings
from app.database import AsyncSessionLocal
from app.models.simplefin_connection import SimplefinConnection
from app.models.user_settings import UserSettings
from app.services import sync_service

logger = logging.getLogger(__name__)
settings = get_settings()
scheduler = AsyncIOScheduler()


async def _sync_all_connections() -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(SimplefinConnection).where(SimplefinConnection.status.in_(["active", "needs_attention"]))
        )
        connections = result.scalars().all()
        for conn in connections:
            try:
                window = settings.transfer_window_days
                settings_result = await db.execute(
                    select(UserSettings).where(UserSettings.user_id == conn.user_id)
                )
                user_settings = settings_result.scalar_one_or_none()
                if user_settings:
                    window = user_settings.transfer_window_days
                summary = await sync_service.run_sync(db, conn, window_days=window)
                logger.info(f"Cron sync user {conn.user_id}: {summary}")
            except Exception as e:
                logger.error(f"Cron sync failed for user {conn.user_id}: {e}")


def start_scheduler() -> None:
    interval_hours = max(1, settings.sync_interval_hours)
    scheduler.add_job(
        _sync_all_connections,
        trigger=IntervalTrigger(hours=interval_hours),
        id="sync_all_connections",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    logger.info(f"Background sync scheduler started (every {interval_hours} hours)")


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
