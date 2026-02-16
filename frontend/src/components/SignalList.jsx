function formatPrice(value) {
  if (value === null || value === undefined) return "-";
  if (value >= 1) return value.toFixed(2);
  return value.toFixed(6);
}

export default function SignalList({ signals }) {
  if (!signals.length) {
    return <div className="empty-state">Сигналов пока нет</div>;
  }

  return (
    <div className="signal-list">
      {signals.map((signal) => (
        <div key={signal.id} className={`signal-card ${signal.signal_type}`}>
          {signal.meta?.chart_pattern?.name ? (
            <div className="signal-tag">
              {signal.meta.chart_pattern.name.replace(/_/g, " ")}
            </div>
          ) : null}
          <div className="signal-header">
            <span className="signal-type">{signal.signal_type.toUpperCase()}</span>
            <span className="signal-confidence">{Math.round(signal.confidence * 100)}%</span>
          </div>
          <div className="signal-meta">
            <span>{signal.symbol}</span>
            <span>{signal.timeframe}</span>
          </div>
          <div className="signal-levels">
            <span>Вход: {formatPrice(signal.entry_price)}</span>
            <span>SL: {formatPrice(signal.stop_loss)}</span>
            <span>TP: {formatPrice(signal.take_profit)}</span>
          </div>
          {signal.meta?.trade_plan?.take_levels ? (
            <div className="signal-levels secondary">
              {signal.meta.trade_plan.take_levels.map((level, index) => (
                <span key={`${signal.id}-tp-${index}`}>TP{index + 1}: {formatPrice(level)}</span>
              ))}
              {signal.meta.trade_plan.breakeven_at ? (
                <span>БУ @ {formatPrice(signal.meta.trade_plan.breakeven_at)}</span>
              ) : null}
            </div>
          ) : null}
          {signal.meta?.candles?.bullish?.length || signal.meta?.candles?.bearish?.length ? (
            <div className="signal-tags">
              {signal.meta?.candles?.bullish?.slice(0, 3).map((name) => (
                <span key={`${signal.id}-bull-${name}`} className="tag bullish">
                  {name.replace("CDL", "")}
                </span>
              ))}
              {signal.meta?.candles?.bearish?.slice(0, 3).map((name) => (
                <span key={`${signal.id}-bear-${name}`} className="tag bearish">
                  {name.replace("CDL", "")}
                </span>
              ))}
            </div>
          ) : null}
          {signal.rationale ? <div className="signal-rationale">{signal.rationale}</div> : null}
          <div className="signal-time">
            {new Date(signal.created_at).toLocaleString()}
          </div>
        </div>
      ))}
    </div>
  );
}
