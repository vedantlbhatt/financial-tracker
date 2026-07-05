from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth_middleware import get_local_user
from app.models.user import User
from app.models.account import Account
from app.models.transaction import Transaction
from app.models.simplefin_connection import SimplefinConnection
from app.models.category_override import CategoryOverride
from app.services.rollup_service import recompute_rollups_for_user

router = APIRouter(prefix="/transactions", tags=["transactions"])


class TransactionResponse(BaseModel):
    id: str
    transaction_id: str
    account_id: str
    account_name: str
    amount: float
    date: str
    description: str
    payee: str | None
    memo: str | None
    category: str
    auto_category: str | None
    is_transfer: bool
    user_category: str | None


class CategoryUpdateRequest(BaseModel):
    category: str
    remember_merchant: bool = True


class TransferUpdateRequest(BaseModel):
    is_transfer: bool


class PaginatedTransactions(BaseModel):
    items: list[TransactionResponse]
    total: int
    page: int
    page_size: int


@router.get("", response_model=PaginatedTransactions)
async def list_transactions(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    account_id: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    search: Optional[str] = Query(None),
    include_transfers: bool = Query(False),
    uncategorized_only: bool = Query(False),
    current_user: User = Depends(get_local_user),
    db: AsyncSession = Depends(get_db),
):
    user_account_ids_result = await db.execute(
        select(Account.id, Account.name)
        .join(SimplefinConnection, SimplefinConnection.id == Account.simplefin_connection_id)
        .where(SimplefinConnection.user_id == current_user.id)
    )
    user_accounts = {str(row.id): row.name for row in user_account_ids_result}
    if not user_accounts:
        return PaginatedTransactions(items=[], total=0, page=page, page_size=page_size)

    filters = [Transaction.account_id.in_(list(user_accounts.keys()))]

    if not include_transfers:
        filters.append(Transaction.is_transfer == False)  # noqa: E712

    if uncategorized_only:
        filters.append(
            and_(
                Transaction.user_category.is_(None),
                or_(
                    Transaction.auto_category.is_(None),
                    Transaction.auto_category == "Uncategorized",
                ),
            )
        )

    if account_id:
        filters.append(Transaction.account_id == account_id)

    if date_from:
        filters.append(Transaction.date >= date_from)

    if date_to:
        filters.append(Transaction.date <= date_to)

    if search:
        term = f"%{search}%"
        filters.append(
            or_(
                Transaction.description.ilike(term),
                Transaction.payee.ilike(term),
                Transaction.memo.ilike(term),
            )
        )

    if category:
        filters.append(
            or_(
                Transaction.user_category == category,
                and_(
                    Transaction.user_category.is_(None),
                    or_(
                        Transaction.auto_category == category,
                        and_(
                            Transaction.auto_category.is_(None),
                            category == "Uncategorized",
                        ),
                    ),
                ),
            )
        )

    count_result = await db.execute(
        select(func.count()).select_from(Transaction).where(and_(*filters))
    )
    total = count_result.scalar_one()

    result = await db.execute(
        select(Transaction)
        .where(and_(*filters))
        .order_by(Transaction.date.desc(), Transaction.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    txs = result.scalars().all()

    items = [
        TransactionResponse(
            id=str(tx.id),
            transaction_id=tx.transaction_id,
            account_id=str(tx.account_id),
            account_name=user_accounts.get(str(tx.account_id), "Unknown"),
            amount=float(tx.amount),
            date=str(tx.date),
            description=tx.description,
            payee=tx.payee,
            memo=tx.memo,
            category=tx.resolved_category,
            auto_category=tx.auto_category,
            is_transfer=tx.is_transfer,
            user_category=tx.user_category,
        )
        for tx in txs
    ]

    return PaginatedTransactions(items=items, total=total, page=page, page_size=page_size)


@router.put("/{transaction_id}/category")
async def update_category(
    transaction_id: str,
    body: CategoryUpdateRequest,
    current_user: User = Depends(get_local_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Transaction)
        .join(Account, Account.id == Transaction.account_id)
        .join(SimplefinConnection, SimplefinConnection.id == Account.simplefin_connection_id)
        .where(
            Transaction.transaction_id == transaction_id,
            SimplefinConnection.user_id == current_user.id,
        )
    )
    tx = result.scalar_one_or_none()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")

    tx.user_category = body.category

    merchant_key = tx.payee or tx.description
    if body.remember_merchant and merchant_key:
        existing_override = await db.execute(
            select(CategoryOverride).where(
                CategoryOverride.user_id == current_user.id,
                CategoryOverride.merchant_name_pattern == merchant_key,
            )
        )
        override = existing_override.scalar_one_or_none()
        if override:
            override.override_category = body.category
        else:
            db.add(
                CategoryOverride(
                    user_id=current_user.id,
                    merchant_name_pattern=merchant_key,
                    override_category=body.category,
                )
            )

    await recompute_rollups_for_user(db, str(current_user.id))
    return {"message": "Category updated"}


@router.put("/{transaction_id}/transfer")
async def update_transfer_flag(
    transaction_id: str,
    body: TransferUpdateRequest,
    current_user: User = Depends(get_local_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Transaction)
        .join(Account, Account.id == Transaction.account_id)
        .join(SimplefinConnection, SimplefinConnection.id == Account.simplefin_connection_id)
        .where(
            Transaction.transaction_id == transaction_id,
            SimplefinConnection.user_id == current_user.id,
        )
    )
    tx = result.scalar_one_or_none()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")

    tx.is_transfer = body.is_transfer
    tx.transfer_manual_override = True
    await recompute_rollups_for_user(db, str(current_user.id))
    return {"message": "Transfer flag updated"}
