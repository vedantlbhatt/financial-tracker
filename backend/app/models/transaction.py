import uuid
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import String, DateTime, Date, ForeignKey, Numeric, Boolean, Text, Index, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class Transaction(Base):
    """
    SimpleFIN sign convention:
      amount > 0  →  inflow (credit/deposit)
      amount < 0  →  outflow (debit/charge)
    """

    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    transaction_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    payee: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    memo: Mapped[str | None] = mapped_column(Text, nullable=True)
    auto_category: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    user_category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_transfer: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    transfer_manual_override: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    iso_currency_code: Mapped[str] = mapped_column(String(10), nullable=False, default="USD")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    account: Mapped["Account"] = relationship("Account", back_populates="transactions")  # noqa: F821

    __table_args__ = (
        UniqueConstraint("account_id", "transaction_id", name="uq_tx_account_external"),
        Index("ix_transactions_account_date", "account_id", "date"),
        Index("ix_transactions_category_date", "auto_category", "date"),
        Index("ix_transactions_transfer_date", "is_transfer", "date"),
    )

    @property
    def display_name(self) -> str:
        return self.payee or self.description or "Unknown"

    @property
    def resolved_category(self) -> str:
        return self.user_category or self.auto_category or "Uncategorized"
