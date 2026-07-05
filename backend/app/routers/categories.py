from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth_middleware import get_local_user
from app.models.user import User
from app.models.account import Account
from app.models.transaction import Transaction
from app.models.simplefin_connection import SimplefinConnection
from app.models.category_override import CategoryOverride
from app.services.category_service import CATEGORIES

router = APIRouter(prefix="/categories", tags=["categories"])


class CategorySummary(BaseModel):
    category: str
    total: float
    count: int
    percentage: float


class CategoryBreakdownResponse(BaseModel):
    categories: list[CategorySummary]
    period_total_outflow: float


class MerchantSummary(BaseModel):
    merchant: str
    total: float
    count: int


class CategoryTrendPoint(BaseModel):
    month: str
    total: float


class CategoryTrend(BaseModel):
    category: str
    points: list[CategoryTrendPoint]


class OverrideResponse(BaseModel):
    id: str
    merchant_name_pattern: str
    override_category: str


class OverrideCreateRequest(BaseModel):
    merchant_name_pattern: str
    override_category: str


@router.get("/breakdown", response_model=CategoryBreakdownResponse)
async def category_breakdown(
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    current_user: User = Depends(get_local_user),
    db: AsyncSession = Depends(get_db),
):
    user_account_ids_result = await db.execute(
        select(Account.id)
        .join(SimplefinConnection, SimplefinConnection.id == Account.simplefin_connection_id)
        .where(SimplefinConnection.user_id == current_user.id)
    )
    account_ids = [row.id for row in user_account_ids_result]
    if not account_ids:
        return CategoryBreakdownResponse(categories=[], period_total_outflow=0)

    filters = [
        Transaction.account_id.in_(account_ids),
        Transaction.is_transfer == False,  # noqa: E712
        Transaction.amount < 0,
    ]
    if date_from:
        filters.append(Transaction.date >= date_from)
    if date_to:
        filters.append(Transaction.date <= date_to)

    cat_expr = func.coalesce(Transaction.user_category, Transaction.auto_category, "Uncategorized")
    result = await db.execute(
        select(
            cat_expr.label("cat"),
            func.sum(func.abs(Transaction.amount)).label("total"),
            func.count(Transaction.id).label("count"),
        )
        .where(and_(*filters))
        .group_by(cat_expr)
        .order_by(func.sum(func.abs(Transaction.amount)).desc())
    )
    rows = result.all()

    grand_total = sum(float(row.total or 0) for row in rows)
    categories = [
        CategorySummary(
            category=row.cat or "Uncategorized",
            total=round(float(row.total or 0), 2),
            count=int(row.count),
            percentage=round(float(row.total or 0) / grand_total * 100, 1) if grand_total else 0,
        )
        for row in rows
    ]
    return CategoryBreakdownResponse(categories=categories, period_total_outflow=round(grand_total, 2))


@router.get("/merchants", response_model=list[MerchantSummary])
async def top_merchants(
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_local_user),
    db: AsyncSession = Depends(get_db),
):
    account_ids_result = await db.execute(
        select(Account.id)
        .join(SimplefinConnection, SimplefinConnection.id == Account.simplefin_connection_id)
        .where(SimplefinConnection.user_id == current_user.id)
    )
    account_ids = [row.id for row in account_ids_result]
    if not account_ids:
        return []

    filters = [
        Transaction.account_id.in_(account_ids),
        Transaction.is_transfer == False,  # noqa: E712
        Transaction.amount < 0,
    ]
    if date_from:
        filters.append(Transaction.date >= date_from)
    if date_to:
        filters.append(Transaction.date <= date_to)

    merchant_expr = func.coalesce(Transaction.payee, Transaction.description)
    result = await db.execute(
        select(
            merchant_expr.label("merchant"),
            func.sum(func.abs(Transaction.amount)).label("total"),
            func.count(Transaction.id).label("count"),
        )
        .where(and_(*filters))
        .group_by(merchant_expr)
        .order_by(func.sum(func.abs(Transaction.amount)).desc())
        .limit(limit)
    )
    return [
        MerchantSummary(
            merchant=row.merchant or "Unknown",
            total=round(float(row.total or 0), 2),
            count=int(row.count),
        )
        for row in result.all()
    ]


@router.get("/trends", response_model=list[CategoryTrend])
async def category_trends(
    months: int = Query(6, ge=1, le=24),
    current_user: User = Depends(get_local_user),
    db: AsyncSession = Depends(get_db),
):
    account_ids_result = await db.execute(
        select(Account.id)
        .join(SimplefinConnection, SimplefinConnection.id == Account.simplefin_connection_id)
        .where(SimplefinConnection.user_id == current_user.id)
    )
    account_ids = [row.id for row in account_ids_result]
    if not account_ids:
        return []

    cat_expr = func.coalesce(Transaction.user_category, Transaction.auto_category, "Uncategorized")
    month_expr = func.date_trunc("month", Transaction.date)

    result = await db.execute(
        select(
            cat_expr.label("cat"),
            month_expr.label("month"),
            func.sum(func.abs(Transaction.amount)).label("total"),
        )
        .where(
            Transaction.account_id.in_(account_ids),
            Transaction.is_transfer == False,  # noqa: E712
            Transaction.amount < 0,
        )
        .group_by(cat_expr, month_expr)
        .order_by(cat_expr, month_expr)
    )

    trends: dict[str, list[CategoryTrendPoint]] = {}
    for row in result.all():
        cat = row.cat or "Uncategorized"
        month_str = row.month.strftime("%Y-%m") if row.month else ""
        trends.setdefault(cat, []).append(
            CategoryTrendPoint(month=month_str, total=round(float(row.total or 0), 2))
        )

    return [CategoryTrend(category=cat, points=pts[-months:]) for cat, pts in trends.items()]


@router.get("/available", response_model=list[str])
async def available_categories():
    return sorted(CATEGORIES)


@router.get("/overrides", response_model=list[OverrideResponse])
async def list_overrides(
    current_user: User = Depends(get_local_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CategoryOverride)
        .where(CategoryOverride.user_id == current_user.id)
        .order_by(CategoryOverride.merchant_name_pattern)
    )
    overrides = result.scalars().all()
    return [
        OverrideResponse(
            id=str(o.id),
            merchant_name_pattern=o.merchant_name_pattern,
            override_category=o.override_category,
        )
        for o in overrides
    ]


@router.post("/overrides", response_model=OverrideResponse, status_code=201)
async def create_override(
    body: OverrideCreateRequest,
    current_user: User = Depends(get_local_user),
    db: AsyncSession = Depends(get_db),
):
    override = CategoryOverride(
        user_id=current_user.id,
        merchant_name_pattern=body.merchant_name_pattern,
        override_category=body.override_category,
    )
    db.add(override)
    await db.flush()
    return OverrideResponse(
        id=str(override.id),
        merchant_name_pattern=override.merchant_name_pattern,
        override_category=override.override_category,
    )


@router.delete("/overrides/{override_id}", status_code=204)
async def delete_override(
    override_id: str,
    current_user: User = Depends(get_local_user),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import delete

    await db.execute(
        delete(CategoryOverride).where(
            CategoryOverride.id == override_id,
            CategoryOverride.user_id == current_user.id,
        )
    )
