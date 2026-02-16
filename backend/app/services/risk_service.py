class RiskService:
    def levels(self, entry_price: float, side: str, stop_pct: float = 0.01, reward_risk: float = 3.0) -> dict[str, float]:
        if side == "long":
            stop_loss = entry_price * (1 - stop_pct)
            take_profit = entry_price * (1 + stop_pct * reward_risk)
        else:
            stop_loss = entry_price * (1 + stop_pct)
            take_profit = entry_price * (1 - stop_pct * reward_risk)
        return {"stop_loss": stop_loss, "take_profit": take_profit}
