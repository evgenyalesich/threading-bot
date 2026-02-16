function formatPrice(value) {
  if (value === null || value === undefined) return "-";
  if (value >= 1) return value.toFixed(2);
  return value.toFixed(6);
}

export default function ScanResultsPanel({
  results,
  running,
  limit,
  maxPairs,
  minVolatility,
  minConfidence,
  minConfirmations,
  requirePattern,
  requireDivergence,
  requireCandle,
  requireVolumeConfirm,
  autoSync,
  onLimitChange,
  onMaxPairsChange,
  onMinVolatilityChange,
  onMinConfidenceChange,
  onMinConfirmationsChange,
  onRequirePatternChange,
  onRequireDivergenceChange,
  onRequireCandleChange,
  onRequireVolumeConfirmChange,
  onAutoSyncChange,
  onRunScan,
  onSelectResult,
}) {
  return (
    <div className="scan-panel">
      <div className="panel-title">Сканер рынка</div>
      <div className="scan-controls">
        <div className="control-group">
          <label>Макс. пар</label>
          <input
            type="number"
            value={maxPairs}
            onChange={(event) => onMaxPairsChange(Number(event.target.value) || 0)}
          />
        </div>
        <div className="control-group">
          <label>Лимит сигналов</label>
          <input
            type="number"
            value={limit}
            onChange={(event) => onLimitChange(Number(event.target.value) || 0)}
          />
        </div>
        <div className="control-group">
          <label>Мин. волатильность %</label>
          <input
            type="number"
            step="0.1"
            value={minVolatility}
            onChange={(event) => onMinVolatilityChange(Number(event.target.value) || 0)}
          />
        </div>
        <div className="control-group">
          <label>Мин. уверенность</label>
          <input
            type="number"
            step="0.01"
            min="0"
            max="1"
            value={minConfidence}
            onChange={(event) => onMinConfidenceChange(Number(event.target.value) || 0)}
          />
        </div>
        <div className="control-group">
          <label>Мин. подтверждений</label>
          <input
            type="number"
            step="1"
            min="0"
            max="6"
            value={minConfirmations}
            onChange={(event) => onMinConfirmationsChange(Number(event.target.value) || 0)}
          />
        </div>
        <label className="toggle-row">
          <input
            type="checkbox"
            checked={requirePattern}
            onChange={(event) => onRequirePatternChange(event.target.checked)}
          />
          <span>Требовать фигуру</span>
        </label>
        <label className="toggle-row">
          <input
            type="checkbox"
            checked={requireDivergence}
            onChange={(event) => onRequireDivergenceChange(event.target.checked)}
          />
          <span>Требовать дивергенцию</span>
        </label>
        <label className="toggle-row">
          <input
            type="checkbox"
            checked={requireCandle}
            onChange={(event) => onRequireCandleChange(event.target.checked)}
          />
          <span>Требовать свечной паттерн</span>
        </label>
        <label className="toggle-row">
          <input
            type="checkbox"
            checked={requireVolumeConfirm}
            onChange={(event) => onRequireVolumeConfirmChange(event.target.checked)}
          />
          <span>Требовать подтверждение объемом</span>
        </label>
        <label className="toggle-row">
          <input
            type="checkbox"
            checked={autoSync}
            onChange={(event) => onAutoSyncChange(event.target.checked)}
          />
          <span>Авто-синхронизация истории</span>
        </label>
      </div>
      <button className="primary" onClick={onRunScan} disabled={running}>
        {running ? "Сканирую..." : "Запуск скана"}
      </button>
      <div className="scan-results">
        {results.length === 0 ? <div className="empty-state">Нет результатов</div> : null}
        {results.map((item) => (
          <button
            key={`${item.binance_symbol}-${item.signal.id}`}
            type="button"
            className={`scan-row ${item.signal.signal_type}`}
            onClick={() => onSelectResult(item)}
          >
            <div className="scan-main">
              <div>
                <strong>{item.symbol}</strong>
                <span>
                  {item.binance_symbol} · {item.timeframe}
                </span>
              </div>
              <div className="scan-metrics">
                <span>Ранг {item.rank.toFixed(1)}</span>
                <span>{Math.round(item.confidence * 100)}%</span>
                <span>{item.volatility_score.toFixed(2)}% вол</span>
              </div>
            </div>
            <div className="scan-levels">
              <span>Вход: {formatPrice(item.signal.entry_price)}</span>
              <span>SL: {formatPrice(item.signal.stop_loss)}</span>
              <span>TP: {formatPrice(item.signal.take_profit)}</span>
            </div>
            {item.signal.rationale ? (
              <div className="scan-rationale">{item.signal.rationale}</div>
            ) : null}
          </button>
        ))}
      </div>
    </div>
  );
}
