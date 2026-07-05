"""
Cash-flow rollup aggregation.

SimpleFIN sign convention:
  amount > 0  →  inflow
  amount < 0  →  outflow

Rollup math (transfer-excluded):
  inflow  = SUM(amount)       WHERE amount > 0 AND NOT is_transfer
  outflow = SUM(ABS(amount))  WHERE amount < 0 AND NOT is_transfer
  net     = inflow - outflow
"""
import logging
from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.simplefin_connection import SimplefinConnection
from app.models.cash_flow_rollup import CashFlowRollup

logger = logging.getLogger(__name__)

GRANULARITIES = ["daily", "weekly", "monthly", "yearly"]

DATE_TRUNC_MAP = {
    "daily": "day",
    "weekly": "week",
    "monthly": "month",
    "yearly": "year",
}


async def recompute_rollups_for_user(db: AsyncSession, user_id: str) -> None:
    for granularity in GRANULARITIES:
        await _recompute_granularity(db, user_id, granularity)
    await db.commit()
    logger.info(f"Rollups recomputed for user {user_id}")


async def _recompute_granularity(db: AsyncSession, user_id: str, granularity: str) -> None:
    pg_trunc = DATE_TRUNC_MAP[granularity]

    result = await db.execute(
        select(Account.id)
        .join(SimplefinConnection, SimplefinConnection.id == Account.simplefin_connection_id)
        .where(SimplefinConnection.user_id == user_id)
    )
    account_ids = [str(row.id) for row in result]
    if not account_ids:
        return

    agg_result = await db.execute(
        text("""
            SELECT
                DATE_TRUNC(:trunc, t.date)::date AS bucket_date,
                SUM(CASE WHEN t.amount > 0 THEN t.amount ELSE 0 END) AS inflow,
                SUM(CASE WHEN t.amount < 0 THEN ABS(t.amount) ELSE 0 END) AS outflow
            FROM transactions t
            WHERE t.account_id = ANY(CAST(:account_ids AS uuid[]))
              AND t.is_transfer = false
            GROUP BY DATE_TRUNC(:trunc, t.date)
            ORDER BY bucket_date
        """),
        {"trunc": pg_trunc, "account_ids": account_ids},
    )
    rows = agg_result.fetchall()

    for row in rows:
        inflow = Decimal(str(row.inflow or 0))
        outflow = Decimal(str(row.outflow or 0))
        net = inflow - outflow

        stmt = (
            pg_insert(CashFlowRollup)
            .values(
                user_id=user_id,
                bucket_date=row.bucket_date,
                granularity=granularity,
                inflow=inflow,
                outflow=outflow,
                net=net,
            )
            .on_conflict_do_update(
                constraint="uq_rollup_user_gran_date",
                set_=dict(inflow=inflow, outflow=outflow, net=net),
            )
        )
        await db.execute(stmt)

    await db.flush()
