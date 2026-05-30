from __future__ import annotations

from app.schemas.base_schema import BaseSchema


class SpotBalanceItem(BaseSchema):
    asset: str
    free: float
    locked: float


class FuturesAssetItem(BaseSchema):
    asset: str
    wallet_balance: float
    available_balance: float
    unrealized_profit: float | None = None


class FuturesPositionItem(BaseSchema):
    symbol: str
    position_amt: float
    entry_price: float
    mark_price: float | None = None
    unrealized_profit: float | None = None
    margin: float | None = None
    leverage: int | None = None
    side: str | None = None


class AccountSummary(BaseSchema):
    status: str
    market: str
    trade_env: str
    spot_balances: list[SpotBalanceItem] | None = None
    futures_assets: list[FuturesAssetItem] | None = None
    futures_positions: list[FuturesPositionItem] | None = None
    error: str | None = None
