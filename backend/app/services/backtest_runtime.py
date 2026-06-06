from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from app.schemas.backtest_progress import BacktestProgressRead


@dataclass(slots=True)
class BacktestRuntimeState:
    status: str = "idle"
    mode: str = "single_pair"
    selected_symbol: str | None = None
    processed_pairs: int = 0
    total_pairs: int = 0
    matched_trades: int = 0
    current_symbol: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    last_error: str | None = None


class BacktestRuntime:
    def __init__(self) -> None:
        self._state = BacktestRuntimeState()

    def start(self, mode: str, total_pairs: int, selected_symbol: str | None = None) -> None:
        self._state = BacktestRuntimeState(
            status="running",
            mode=mode,
            selected_symbol=selected_symbol,
            total_pairs=max(int(total_pairs), 0),
            started_at=datetime.now(UTC),
        )

    def advance(self, symbol: str, processed_pairs: int, matched_trades: int) -> None:
        self._state.current_symbol = symbol
        self._state.processed_pairs = max(int(processed_pairs), 0)
        self._state.matched_trades = max(int(matched_trades), 0)

    def finish(self, processed_pairs: int, matched_trades: int) -> None:
        self._state.status = "completed"
        self._state.processed_pairs = max(int(processed_pairs), 0)
        self._state.matched_trades = max(int(matched_trades), 0)
        self._state.finished_at = datetime.now(UTC)
        self._state.current_symbol = None
        self._state.last_error = None

    def fail(self, error: str) -> None:
        self._state.status = "error"
        self._state.last_error = str(error)[:500]
        self._state.finished_at = datetime.now(UTC)

    def snapshot(self) -> BacktestProgressRead:
        return BacktestProgressRead(
            status=self._state.status,
            mode=self._state.mode,
            selected_symbol=self._state.selected_symbol,
            processed_pairs=self._state.processed_pairs,
            total_pairs=self._state.total_pairs,
            matched_trades=self._state.matched_trades,
            current_symbol=self._state.current_symbol,
            started_at=self._state.started_at,
            finished_at=self._state.finished_at,
            last_error=self._state.last_error,
        )


_runtime: BacktestRuntime | None = None


def get_backtest_runtime() -> BacktestRuntime:
    global _runtime
    if _runtime is None:
        _runtime = BacktestRuntime()
    return _runtime
