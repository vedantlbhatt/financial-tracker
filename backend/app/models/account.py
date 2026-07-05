import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import String, DateTime, ForeignKey, Numeric, JSON, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    simplefin_connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("simplefin_connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    account_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    institution_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    type: Mapped[str] = mapped_column(String(50), nullable=False, default="other")
    subtype: Mapped[str | None] = mapped_column(String(50), nullable=True)
    current_balance: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    available_balance: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    balance_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    iso_currency_code: Mapped[str] = mapped_column(String(10), nullable=False, default="USD")
    sync_errors: Mapped[list | None] = mapped_column(JSON, nullable=True)
    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    simplefin_connection: Mapped["SimplefinConnection"] = relationship(  # noqa: F821
        "SimplefinConnection", back_populates="accounts"
    )
    transactions: Mapped[list["Transaction"]] = relationship(  # noqa: F821
        "Transaction", back_populates="account", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("simplefin_connection_id", "account_id", name="uq_account_connection_external"),
    )
