"""SimpleFIN daily API request budget (Bridge free tier: 24/day)."""
from datetime import date, timezone, datetime
import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.simplefin_api_usage import SimplefinApiUsage

settings = get_settings()


class QuotaExceededError(Exception):
    def __init__(self, used: int, limit: int):
        self.used = used
        self.limit = limit
        super().__init__(f"SimpleFIN daily limit reached ({used}/{limit} requests used today)")


def _today_utc() -> date:
    return datetime.now(timezone.utc).date()


async def get_usage_today(db: AsyncSession, connection_id: uuid.UUID) -> int:
    today = _today_utc()
    result = await db.execute(
        select(SimplefinApiUsage.request_count).where(
            SimplefinApiUsage.simplefin_connection_id == connection_id,
            SimplefinApiUsage.usage_date == today,
        )
    )
    return int(result.scalar_one_or_none() or 0)


async def remaining(db: AsyncSession, connection_id: uuid.UUID) -> int:
    limit = settings.simplefin_daily_request_limit
    return max(0, limit - await get_usage_today(db, connection_id))


async def assert_can_sync(db: AsyncSession, connection_id: uuid.UUID, needed: int = 1) -> None:
    used = await get_usage_today(db, connection_id)
    limit = settings.simplefin_daily_request_limit
    if used + needed > limit:
        raise QuotaExceededError(used, limit)


async def record_requests(db: AsyncSession, connection_id: uuid.UUID, count: int) -> int:
    if count <= 0:
        return await get_usage_today(db, connection_id)

    today = _today_utc()
    stmt = (
        pg_insert(SimplefinApiUsage)
        .values(
            simplefin_connection_id=connection_id,
            usage_date=today,
            request_count=count,
        )
        .on_conflict_do_update(
            constraint="uq_simplefin_usage_connection_date",
            set_=dict(request_count=SimplefinApiUsage.request_count + count),
        )
        .returning(SimplefinApiUsage.request_count)
    )
    result = await db.execute(stmt)
    return int(result.scalar_one())


async def quota_snapshot(db: AsyncSession, connection_id: uuid.UUID) -> dict:
    used = await get_usage_today(db, connection_id)
    limit = settings.simplefin_daily_request_limit
    return {
        "requests_used_today": used,
        "requests_remaining_today": max(0, limit - used),
        "daily_request_limit": limit,
    }
