from datetime import date, timedelta
from typing import Optional, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth_middleware import get_local_user
from app.models.user import User
from app.models.cash_flow_rollup import CashFlowRollup

router = APIRouter(prefix="/cash-flow", tags=["cash-flow"])


class CashFlowBucket(BaseModel):
    date: str
    inflow: float
    outflow: float
    net: float
    cumulative_net: float


class CashFlowSummary(BaseModel):
    total_inflow: float
    total_outflow: float
    net: float


class CashFlowResponse(BaseModel):
    buckets: list[CashFlowBucket]
    summary: CashFlowSummary
    granularity: str


@router.get("", response_model=CashFlowResponse)
async def get_cash_flow(
    granularity: Literal["daily", "weekly", "monthly", "yearly"] = Query("monthly"),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    current_user: User = Depends(get_local_user),
    db: AsyncSession = Depends(get_db),
):
    # Default date range: current month (matches Overview)
    if not date_to:
        date_to = date.today()
    if not date_from:
        date_from = date(date_to.year, date_to.month, 1)

    filters = [
        CashFlowRollup.user_id == current_user.id,
        CashFlowRollup.granularity == granularity,
        CashFlowRollup.bucket_date >= date_from,
        CashFlowRollup.bucket_date <= date_to,
    ]

    result = await db.execute(
        select(CashFlowRollup)
        .where(and_(*filters))
        .order_by(CashFlowRollup.bucket_date)
    )
    rollups = result.scalars().all()

    cumulative = 0.0
    buckets = []
    total_inflow = 0.0
    total_outflow = 0.0

    for r in rollups:
        inflow = float(r.inflow)
        outflow = float(r.outflow)
        net = float(r.net)
        cumulative += net
        total_inflow += inflow
        total_outflow += outflow
        buckets.append(
            CashFlowBucket(
                date=str(r.bucket_date),
                inflow=round(inflow, 2),
                outflow=round(outflow, 2),
                net=round(net, 2),
                cumulative_net=round(cumulative, 2),
            )
        )

    return CashFlowResponse(
        buckets=buckets,
        summary=CashFlowSummary(
            total_inflow=round(total_inflow, 2),
            total_outflow=round(total_outflow, 2),
            net=round(total_inflow - total_outflow, 2),
        ),
        granularity=granularity,
    )
