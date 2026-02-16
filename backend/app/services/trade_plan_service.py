from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TradePlan:
    entry: float
    stop_loss: float
    take_profit: float
    take_levels: list[float]
    breakeven_at: float
    reward_risk: float
    stop_type: str


class TradePlanService:
    def __init__(
        self,
        fixed_stop_pct: float = 0.01,
        reward_risk: float = 3.0,
        buffer_pct: float = 0.001,
    ) -> None:
        self._fixed_stop_pct = fixed_stop_pct
        self._reward_risk = reward_risk
        self._buffer_pct = buffer_pct

    def build(
        self,
        entry: float,
        side: str,
        support_levels: list[float] | None = None,
        resistance_levels: list[float] | None = None,
        stop_hint: float | None = None,
    ) -> TradePlan:
        support_levels = support_levels or []
        resistance_levels = resistance_levels or []

        stop_loss, stop_type = self._resolve_stop(entry, side, support_levels, resistance_levels, stop_hint)
        risk = abs(entry - stop_loss)
        if risk <= 0:
            risk = entry * self._fixed_stop_pct
            stop_loss = entry - risk if side == "long" else entry + risk
            stop_type = "fixed"

        targets = self._resolve_targets(entry, side, risk, support_levels, resistance_levels)
        breakeven_at = targets[0] if targets else entry
        take_profit = targets[-1] if targets else (entry + risk * self._reward_risk if side == "long" else entry - risk * self._reward_risk)

        return TradePlan(
            entry=entry,
            stop_loss=stop_loss,
            take_profit=take_profit,
            take_levels=targets,
            breakeven_at=breakeven_at,
            reward_risk=self._reward_risk,
            stop_type=stop_type,
        )

    def _resolve_stop(
        self,
        entry: float,
        side: str,
        support_levels: list[float],
        resistance_levels: list[float],
        stop_hint: float | None,
    ) -> tuple[float, str]:
        buffer = entry * self._buffer_pct
        if stop_hint and stop_hint > 0:
            if side == "long" and stop_hint < entry:
                return stop_hint - buffer, "pattern"
            if side == "short" and stop_hint > entry:
                return stop_hint + buffer, "pattern"

        if side == "long" and support_levels:
            below = [level for level in support_levels if level < entry]
            if below:
                level = max(below)
                return level - buffer, "level"
        if side == "short" and resistance_levels:
            above = [level for level in resistance_levels if level > entry]
            if above:
                level = min(above)
                return level + buffer, "level"

        stop = entry * (1 - self._fixed_stop_pct) if side == "long" else entry * (1 + self._fixed_stop_pct)
        return stop, "fixed"

    def _resolve_targets(
        self,
        entry: float,
        side: str,
        risk: float,
        support_levels: list[float],
        resistance_levels: list[float],
    ) -> list[float]:
        levels = resistance_levels if side == "long" else support_levels
        levels = sorted({float(level) for level in levels if level})
        levels = [level for level in levels if level > entry] if side == "long" else [level for level in levels if level < entry]
        levels.sort()
        if side == "short":
            levels = list(reversed(levels))

        targets: list[float] = []
        min_target = entry + risk * 0.6 if side == "long" else entry - risk * 0.6
        for level in levels:
            if side == "long" and level < min_target:
                continue
            if side == "short" and level > min_target:
                continue
            targets.append(level)
            if len(targets) >= 3:
                break

        while len(targets) < 3:
            step = len(targets) + 1
            target = entry + risk * step if side == "long" else entry - risk * step
            targets.append(target)

        final_target = entry + risk * self._reward_risk if side == "long" else entry - risk * self._reward_risk
        if side == "long" and targets[-1] < final_target:
            targets[-1] = final_target
        if side == "short" and targets[-1] > final_target:
            targets[-1] = final_target

        return targets
