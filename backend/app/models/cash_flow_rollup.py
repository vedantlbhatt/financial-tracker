import uuid
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import String, DateTime, Date, ForeignKey, Numeric, Index, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class CashFlowRollup(Base):
    """
    Pre-aggregated cash flow data per user per time bucket.
    Refreshed after every successful SimpleFIN sync.
    SimpleFIN sign convention:
      - inflow  = SUM(amount)       WHERE amount > 0 AND NOT is_transfer
      - outflow = SUM(ABS(amount))  WHERE amount < 0 AND NOT is_transfer
    """
    __tablename__ = "cash_flow_rollups"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # The start date of this bucket
    bucket_date: Mapped[date] = mapped_column(Date, nullable=False)
    # daily | weekly | monthly | yearly
    granularity: Mapped[str] = mapped_column(String(20), nullable=False)
    inflow: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False, default=0)
    outflow: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False, default=0)
    net: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship("User", back_populates="cash_flow_rollups")  # noqa: F821

    __table_args__ = (
        UniqueConstraint("user_id", "granularity", "bucket_date", name="uq_rollup_user_gran_date"),
        Index("ix_rollup_user_gran_date", "user_id", "granularity", "bucket_date"),
    )
