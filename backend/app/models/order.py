from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    exchange: Mapped[str] = mapped_column(String(16), nullable=False)
    market: Mapped[str] = mapped_column(String(16), nullable=False, default="spot")
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    order_type: Mapped[str] = mapped_column(String(16), nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    leverage: Mapped[int | None] = mapped_column(nullable=True)
    timeframe: Mapped[str | None] = mapped_column(String(16), nullable=True)
    signal_id: Mapped[int | None] = mapped_column(ForeignKey("signals.id"), nullable=True)
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    stop_loss: Mapped[float | None] = mapped_column(Float, nullable=True)
    take_profit: Mapped[float | None] = mapped_column(Float, nullable=True)
    take_levels: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    breakeven_at: Mapped[float | None] = mapped_column(Float, nullable=True)
    auto_breakeven: Mapped[bool] = mapped_column(Boolean, default=False)
    breakeven_moved: Mapped[bool] = mapped_column(Boolean, default=False)
    stop_order_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    take_order_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    oco_order_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    trade_env: Mapped[str | None] = mapped_column(String(16), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="new")
    client_order_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
