export default function StatsPanel({ stats }) {
  const totalTrades = Number(stats.total_trades ?? stats.totalSignals ?? 0);
  const winRate = Number.isFinite(stats.win_rate)
    ? stats.win_rate.toFixed(1)
    : stats.winRate ?? 0;
  const totalPnLValue = Number(stats.total_pnl ?? stats.totalPnL ?? 0);
  const avgPnLValue = Number(stats.avg_pnl ?? 0);
  const profitFactorValue =
    stats.profit_factor !== undefined ? stats.profit_factor : stats.profitFactor ?? 0;
  const maxDrawdownValue = Number(stats.max_drawdown ?? 0);
  const pnlValue = Number(totalPnLValue);
  const pnlClass = Number.isFinite(pnlValue) ? (pnlValue >= 0 ? "positive" : "negative") : "";
  return (
    <div className="stats-panel">
      <div className="stats-title">Статистика</div>
      <div className="stats-grid">
        <div className="stat">
          <span>Всего сделок</span>
          <strong>{totalTrades}</strong>
        </div>
        <div className="stat">
          <span>Процент побед</span>
          <strong>{winRate}%</strong>
        </div>
        <div className="stat">
          <span>Профит фактор</span>
          <strong>
            {profitFactorValue === null ? "-" : Number.isFinite(profitFactorValue) ? profitFactorValue.toFixed(2) : profitFactorValue}
          </strong>
        </div>
        <div className="stat">
          <span>Итого PnL</span>
          <strong className={pnlClass}>{totalPnLValue.toFixed(2)}%</strong>
        </div>
        <div className="stat">
          <span>Средний PnL</span>
          <strong>{avgPnLValue.toFixed(2)}%</strong>
        </div>
        <div className="stat">
          <span>Макс. просадка</span>
          <strong>{maxDrawdownValue.toFixed(2)}%</strong>
        </div>
      </div>
    </div>
  );
}
