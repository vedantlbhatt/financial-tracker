from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.services.local_setup import get_or_create_local_user


async def get_local_user(db: AsyncSession = Depends(get_db)) -> User:
    """Always returns the single local user — no JWT, no login."""
    return await get_or_create_local_user(db)
