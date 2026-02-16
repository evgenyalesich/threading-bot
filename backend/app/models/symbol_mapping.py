from datetime import datetime

from sqlalchemy import DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SymbolMapping(Base):
    __tablename__ = "symbol_mappings"
    __table_args__ = (
        Index("ix_symbol_mappings_yfinance_market", "yfinance_symbol", "market", unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    yfinance_symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    binance_symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    market: Mapped[str] = mapped_column(String(16), nullable=False, default="spot")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
