from decimal import Decimal
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth_middleware import get_local_user
from app.models.user import User
from app.models.account import Account
from app.models.simplefin_connection import SimplefinConnection

router = APIRouter(prefix="/accounts", tags=["accounts"])


class AccountResponse(BaseModel):
    id: str
    account_id: str
    name: str
    institution_name: str | None
    type: str
    subtype: str | None
    current_balance: float | None
    available_balance: float | None
    iso_currency_code: str
    connection_status: str
    sync_errors: list | None

    class Config:
        from_attributes = True


@router.get("", response_model=list[AccountResponse])
async def list_accounts(
    current_user: User = Depends(get_local_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Account, SimplefinConnection.status)
        .join(SimplefinConnection, SimplefinConnection.id == Account.simplefin_connection_id)
        .where(SimplefinConnection.user_id == current_user.id)
        .order_by(Account.type, Account.name)
    )
    rows = result.all()
    return [
        AccountResponse(
            id=str(row.Account.id),
            account_id=row.Account.account_id,
            name=row.Account.name,
            institution_name=row.Account.institution_name,
            type=row.Account.type,
            subtype=row.Account.subtype,
            current_balance=float(row.Account.current_balance) if row.Account.current_balance is not None else None,
            available_balance=float(row.Account.available_balance) if row.Account.available_balance is not None else None,
            iso_currency_code=row.Account.iso_currency_code,
            connection_status=row.status,
            sync_errors=row.Account.sync_errors,
        )
        for row in rows
    ]
