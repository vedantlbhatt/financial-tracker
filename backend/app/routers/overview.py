from datetime import date

from fastapi import APIRouter, BackgroundTasks, Depends
from pydantic import BaseModel
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db, AsyncSessionLocal
from app.middleware.auth_middleware import get_local_user
from app.models.user import User
from app.models.account import Account
from app.models.transaction import Transaction
from app.models.simplefin_connection import SimplefinConnection
from app.models.cash_flow_rollup import CashFlowRollup
from app.services.category_service import CATEGORIES
from app.services import sync_service

router = APIRouter(prefix="/overview", tags=["overview"])
settings = get_settings()

INCOME_TEXT = (
    Transaction.description.ilike("%DIR DEP%"),
    Transaction.description.ilike("%DIRECT DEP%"),
    Transaction.description.ilike("%PAYROLL%"),
    Transaction.description.ilike("%EXP REIMB%"),
)


class OverviewAccount(BaseModel):
    id: str
    name: str
    type: str
    subtype: str | None
    current_balance: float | None
    institution_name: str | None


class CategorySlice(BaseModel):
    category: str
    total: float
    percentage: float


class IncomeDeposit(BaseModel):
    date: str
    amount: float
    payee: str
    category: str


class OverviewResponse(BaseModel):
    net_worth: float
    month_inflow: float
    month_outflow: float
    month_net: float
    month_sparkline: list[float]
    ytd_inflow: float
    ytd_outflow: float
    ytd_net: float
    recent_income: list[IncomeDeposit]
    accounts: list[OverviewAccount]
    top_categories: list[CategorySlice]
    simplefin_status: str | None
    account_errors: list | None
    last_sync_at: str | None


async def _background_sync(user_id: str) -> None:
    async with AsyncSessionLocal() as db:
        conn = (
            await db.execute(
                select(SimplefinConnection).where(SimplefinConnection.user_id == user_id)
            )
        ).scalar_one_or_none()
        if not conn:
            return
        try:
            await sync_service.run_sync(
                db, conn, window_days=settings.transfer_window_days, full_sync=False
            )
        except Exception:
            pass


def _income_filter():
    return or_(
        Transaction.auto_category == "Income",
        Transaction.user_category == "Income",
        *INCOME_TEXT,
    )


@router.get("", response_model=OverviewResponse)
async def get_overview(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_local_user),
    db: AsyncSession = Depends(get_db),
):
    background_tasks.add_task(_background_sync, str(current_user.id))

    conn_result = await db.execute(
        select(SimplefinConnection).where(SimplefinConnection.user_id == current_user.id)
    )
    conn = conn_result.scalar_one_or_none()

    acct_result = await db.execute(
        select(Account)
        .join(SimplefinConnection, SimplefinConnection.id == Account.simplefin_connection_id)
        .where(SimplefinConnection.user_id == current_user.id)
        .order_by(Account.type, Account.name)
    )
    accounts = acct_result.scalars().all()
    net_worth = sum(float(a.current_balance or 0) for a in accounts)

    today = date.today()
    month_start = date(today.year, today.month, 1)
    year_start = date(today.year, 1, 1)

    rollup_result = await db.execute(
        select(CashFlowRollup)
        .where(
            CashFlowRollup.user_id == current_user.id,
            CashFlowRollup.granularity == "daily",
            CashFlowRollup.bucket_date >= month_start,
            CashFlowRollup.bucket_date <= today,
        )
        .order_by(CashFlowRollup.bucket_date)
    )
    daily_rollups = rollup_result.scalars().all()
    month_inflow = sum(float(r.inflow) for r in daily_rollups)
    month_outflow = sum(float(r.outflow) for r in daily_rollups)
    month_net = month_inflow - month_outflow
    sparkline = [float(r.net) for r in daily_rollups]

    ytd_result = await db.execute(
        select(CashFlowRollup)
        .where(
            CashFlowRollup.user_id == current_user.id,
            CashFlowRollup.granularity == "monthly",
            CashFlowRollup.bucket_date >= year_start,
            CashFlowRollup.bucket_date <= today,
        )
    )
    ytd_rollups = ytd_result.scalars().all()
    ytd_inflow = sum(float(r.inflow) for r in ytd_rollups)
    ytd_outflow = sum(float(r.outflow) for r in ytd_rollups)
    ytd_net = ytd_inflow - ytd_outflow

    account_ids = [a.id for a in accounts]
    top_categories: list[CategorySlice] = []
    recent_income: list[IncomeDeposit] = []

    if account_ids:
        cat_expr = func.coalesce(Transaction.user_category, Transaction.auto_category, "Uncategorized")
        cat_result = await db.execute(
            select(
                cat_expr.label("cat"),
                func.sum(func.abs(Transaction.amount)).label("total"),
            )
            .where(
                Transaction.account_id.in_(account_ids),
                Transaction.is_transfer == False,  # noqa: E712
                Transaction.amount < 0,
                Transaction.date >= month_start,
            )
            .group_by(cat_expr)
            .order_by(func.sum(func.abs(Transaction.amount)).desc())
            .limit(5)
        )
        rows = cat_result.all()
        grand = sum(float(r.total or 0) for r in rows) or 1
        top_categories = [
            CategorySlice(
                category=r.cat or "Uncategorized",
                total=round(float(r.total or 0), 2),
                percentage=round(float(r.total or 0) / grand * 100, 1),
            )
            for r in rows
        ]

        income_result = await db.execute(
            select(Transaction)
            .where(
                Transaction.account_id.in_(account_ids),
                Transaction.is_transfer == False,  # noqa: E712
                Transaction.amount > 0,
                _income_filter(),
            )
            .order_by(Transaction.date.desc(), Transaction.amount.desc())
            .limit(10)
        )
        recent_income = [
            IncomeDeposit(
                date=str(tx.date),
                amount=round(float(tx.amount), 2),
                payee=tx.payee or tx.description[:60] or "Deposit",
                category=tx.user_category or tx.auto_category or "Income",
            )
            for tx in income_result.scalars()
        ]

    return OverviewResponse(
        net_worth=round(net_worth, 2),
        month_inflow=round(month_inflow, 2),
        month_outflow=round(month_outflow, 2),
        month_net=round(month_net, 2),
        month_sparkline=sparkline,
        ytd_inflow=round(ytd_inflow, 2),
        ytd_outflow=round(ytd_outflow, 2),
        ytd_net=round(ytd_net, 2),
        recent_income=recent_income,
        accounts=[
            OverviewAccount(
                id=str(a.id),
                name=a.name,
                type=a.type,
                subtype=a.subtype,
                current_balance=float(a.current_balance) if a.current_balance is not None else None,
                institution_name=a.institution_name,
            )
            for a in accounts
        ],
        top_categories=top_categories,
        simplefin_status=conn.status if conn else None,
        account_errors=conn.account_errors if conn else None,
        last_sync_at=conn.last_sync_at.isoformat() if conn and conn.last_sync_at else None,
    )


@router.get("/categories-list", response_model=list[str])
async def categories_list():
    return CATEGORIES
