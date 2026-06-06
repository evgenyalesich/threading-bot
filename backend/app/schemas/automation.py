from __future__ import annotations

from datetime import datetime

from app.schemas.base_schema import BaseSchema
from app.schemas.order_read import OrderRead
from app.schemas.signal_read import SignalRead


class AutomationConfigUpdate(BaseSchema):
    enabled: bool | None = None
    mode: str | None = None
    symbol: str | None = None
    scan_market_wide: bool | None = None
    quote: str | None = None
    max_pairs: int | None = None
    timeframe: str | None = None
    market: str | None = None
    data_env: str | None = None
    trade_env: str | None = None
    lookback_days: int | None = None
    quantity: float | None = None
    quote_amount: float | None = None
    auto_quantity: bool | None = None
    attach_orders: bool | None = None
    auto_breakeven: bool | None = None
    leverage: int | None = None
    min_confidence: float | None = None
    min_confirmations: int | None = None
    require_pattern: bool | None = None
    require_divergence: bool | None = None
    require_candle: bool | None = None
    require_volume_confirm: bool | None = None
    min_trend_strength: float | None = None
    min_reward_risk: float | None = None
    allow_candidate_patterns: bool | None = None
    quality_mode: str | None = None
    h1_timeframe: str | None = None
    trend_timeframe: str | None = None
    poll_interval_sec: int | None = None


class AutomationModeUpdate(BaseSchema):
    mode: str


class AutomationTradeEnvUpdate(BaseSchema):
    trade_env: str


class PendingApprovalRead(BaseSchema):
    signal_id: int
    symbol: str
    timeframe: str
    signal_type: str
    confidence: float
    entry_price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    rationale: str | None = None
    created_at: datetime


class AutomationLogRead(BaseSchema):
    id: str
    level: str
    event: str
    message: str
    created_at: datetime
    meta: dict | None = None


class AutomationStateRead(BaseSchema):
    enabled: bool
    worker_running: bool
    telegram_enabled: bool
    telegram_worker_running: bool
    live_state: str
    live_message: str | None = None
    mode: str
    symbol: str
    scan_market_wide: bool
    quote: str
    max_pairs: int
    timeframe: str
    market: str
    data_env: str
    trade_env: str
    lookback_days: int
    quantity: float
    quote_amount: float | None = None
    auto_quantity: bool
    attach_orders: bool
    auto_breakeven: bool
    leverage: int | None = None
    min_confidence: float
    min_confirmations: int
    require_pattern: bool
    require_divergence: bool
    require_candle: bool
    require_volume_confirm: bool
    min_trend_strength: float
    min_reward_risk: float
    allow_candidate_patterns: bool
    quality_mode: str
    h1_timeframe: str
    trend_timeframe: str
    poll_interval_sec: int
    scan_processed_pairs: int = 0
    scan_total_pairs: int = 0
    scan_matched_signals: int = 0
    scan_phase: str | None = None
    next_check_at: datetime | None = None
    last_check_at: datetime | None = None
    last_signal_at: datetime | None = None
    last_error: str | None = None
    last_no_signal_reason: str | None = None
    last_update_received_at: datetime | None = None
    last_callback_handled_at: datetime | None = None
    last_telegram_error: str | None = None
    pending_approvals: list[PendingApprovalRead]
    logs: list[AutomationLogRead]
    latest_signal: SignalRead | None = None
    latest_order: OrderRead | None = None
    recent_signals: list[SignalRead] = []
    recent_orders: list[OrderRead] = []
