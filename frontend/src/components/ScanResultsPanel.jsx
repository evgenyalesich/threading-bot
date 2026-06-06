function formatPrice(value) {
  if (value === null || value === undefined) return "-";
  if (value >= 1) return value.toFixed(2);
  return value.toFixed(6);
}

function ConfidenceBar({ value }) {
  const pct = Math.round(value * 100);
  const color = pct >= 80 ? "#22c55e" : pct >= 60 ? "#eab308" : "#ef4444";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
      <div
        style={{
          width: 40,
          height: 5,
          background: "#333",
          borderRadius: 3,
          overflow: "hidden",
        }}
      >
        <div
          style={{
            width: `${pct}%`,
            height: "100%",
            background: color,
            borderRadius: 3,
          }}
        />
      </div>
      <span style={{ color, fontWeight: 600, fontSize: 11 }}>{pct}%</span>
    </div>
  );
}

export default function ScanResultsPanel({
  results,
  running,
  mode,
  processedPairs,
  universePairs,
  selectedSymbol,
  diagnostics,
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
  onlyNewSignalsMinutes,
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
  onOnlyNewSignalsMinutesChange,
  onModeChange,
  onRunScan,
  onSelectResult,
}) {
  const longResults = results.filter((r) => r.signal.signal_type === "long");
  const shortResults = results.filter((r) => r.signal.signal_type === "short");
  const topReasons = Object.entries(diagnostics?.reason_counts || {})
    .sort((a, b) => b[1] - a[1])
    .slice(0, 6);

  return (
    <div className="scan-panel">
      <div className="panel-title-row">
        <div>
          <div className="panel-title">Сканер рынка</div>
          <div className="journal-subtitle">
            {mode === "single" ? `Single Pair · ${selectedSymbol || "--"}` : "Market-Wide · весь отфильтрованный рынок"}
          </div>
        </div>
        <div className="segmented-toggle compact">
          <button
            type="button"
            className={mode === "single" ? "active" : ""}
            onClick={() => onModeChange("single")}
          >
            Single Pair
          </button>
          <button
            type="button"
            className={mode === "market" ? "active" : ""}
            onClick={() => onModeChange("market")}
          >
            Market-Wide
          </button>
        </div>
      </div>
      <div className="workspace-summary-grid">
        <div className="workspace-summary-card">
          <span>Обработано пар</span>
          <strong>{processedPairs ?? 0}</strong>
          <small>из universe {universePairs ?? 0}</small>
        </div>
        <div className="workspace-summary-card">
          <span>Лимит сигналов</span>
          <strong>{limit}</strong>
          <small>макс. пар {mode === "market" ? maxPairs : 1}</small>
        </div>
      </div>
      {diagnostics ? (
        <div className="scan-diagnostics">
          <div className="signals-title">Диагностика сканера</div>
          <div className="workspace-summary-grid">
            <div className="workspace-summary-card">
              <span>Всего пар</span>
              <strong>{diagnostics.total_pairs ?? 0}</strong>
              <small>после quote/volatility: {diagnostics.eligible_pairs ?? 0}</small>
            </div>
            <div className="workspace-summary-card">
              <span>Сигналы</span>
              <strong>{diagnostics.matched_signals ?? 0}</strong>
              <small>обработано пар: {diagnostics.processed_pairs ?? 0}</small>
            </div>
          </div>
          <div className="diagnostic-reason-list">
            {topReasons.length ? topReasons.map(([reason, count]) => (
              <div key={reason} className="diagnostic-reason-pill">
                <strong>{reason}</strong>
                <span>{count}</span>
              </div>
            )) : (
              <div className="empty-state">Причины отсечения пока не собраны.</div>
            )}
          </div>
        </div>
      ) : null}
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
          <label>Мин. уверенность</label>
          <input
            type="number"
            step="0.05"
            min="0"
            max="1"
            value={minConfidence}
            onChange={(event) => onMinConfidenceChange(Number(event.target.value) || 0)}
          />
        </div>
        <label className="toggle-row">
          <input
            type="checkbox"
            checked={autoSync}
            onChange={(event) => onAutoSyncChange(event.target.checked)}
          />
          <span>Авто-синхронизация истории</span>
        </label>
        <div className="control-group">
          <label>Только новые (мин)</label>
          <input
            type="number"
            min="0"
            value={onlyNewSignalsMinutes}
            onChange={(event) => onOnlyNewSignalsMinutesChange(Number(event.target.value) || 0)}
          />
        </div>
      </div>

      <button className="primary scan-btn" onClick={onRunScan} disabled={running}>
        {running ? "⏳ Сканирую..." : "▶ Запустить сканер"}
      </button>

      {results.length > 0 && (
        <div className="scan-summary">
          <span className="scan-summary-long">▲ LONG: {longResults.length}</span>
          <span className="scan-summary-short">▼ SHORT: {shortResults.length}</span>
          <span className="scan-summary-total">Всего: {results.length}</span>
        </div>
      )}

      <div className="scan-results">
        {results.length === 0 && !running ? (
          <div className="empty-state">Нажмите «Запустить сканер» для поиска сигналов</div>
        ) : null}
        {running && results.length === 0 ? (
          <div className="empty-state">Сканирование...</div>
        ) : null}

        {longResults.length > 0 && (
          <div className="scan-group">
            <div className="scan-group-header scan-group-long">▲ LONG ({longResults.length})</div>
            {longResults.map((item) => (
              <ScanCard key={`${item.binance_symbol}-${item.signal.id}`} item={item} onSelect={onSelectResult} />
            ))}
          </div>
        )}

        {shortResults.length > 0 && (
          <div className="scan-group">
            <div className="scan-group-header scan-group-short">▼ SHORT ({shortResults.length})</div>
            {shortResults.map((item) => (
              <ScanCard key={`${item.binance_symbol}-${item.signal.id}`} item={item} onSelect={onSelectResult} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function ScanCard({ item, onSelect }) {
  const isLong = item.signal.signal_type === "long";
  const risk = Math.abs(item.signal.entry_price - item.signal.stop_loss);
  const reward = Math.abs(item.signal.take_profit - item.signal.entry_price);
  const rr = risk > 0 ? (reward / risk).toFixed(1) : "—";

  return (
    <button
      type="button"
      className={`scan-row ${item.signal.signal_type}`}
      onClick={() => onSelect(item)}
    >
      <div className="scan-row-top">
        <div className="scan-row-symbol">
          <span className={`scan-direction ${isLong ? "scan-long" : "scan-short"}`}>
            {isLong ? "▲" : "▼"}
          </span>
          <strong>{item.binance_symbol}</strong>
          <span className="scan-tf">{item.timeframe}</span>
        </div>
        <div className="scan-row-right">
          <ConfidenceBar value={item.confidence} />
          <span className="scan-rank">★ {item.rank.toFixed(1)}</span>
        </div>
      </div>
      <div className="scan-levels">
        <span className="scan-entry">Вход: {formatPrice(item.signal.entry_price)}</span>
        <span className="scan-sl">SL: {formatPrice(item.signal.stop_loss)}</span>
        <span className="scan-tp">TP: {formatPrice(item.signal.take_profit)}</span>
        <span className="scan-rr">R:R {rr}</span>
      </div>
    </button>
  );
}
