import { useMemo, useState } from "react";

function formatPrice(value) {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  if (Math.abs(value) >= 1) return value.toFixed(2);
  return value.toFixed(6);
}

function formatTime(epochSeconds) {
  if (!epochSeconds) return "-";
  return new Date(epochSeconds * 1000).toLocaleString();
}

export default function TradeHistoryPanel({ trades, source = "simulation" }) {
  const [expandedId, setExpandedId] = useState(null);
  const [page, setPage] = useState(0);
  const pageSize = 100;
  const ordered = useMemo(() => [...trades].sort((a, b) => b.entry_time - a.entry_time), [trades]);
  const total = ordered.length;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const safePage = Math.min(Math.max(page, 0), totalPages - 1);
  const pageItems = ordered.slice(safePage * pageSize, safePage * pageSize + pageSize);

  if (!total) {
    return (
      <div className="trade-history-panel">
        <div className="trade-history-title">История сделок</div>
        <div className="trade-history-empty">Сделок пока нет</div>
      </div>
    );
  }

  return (
    <div className="trade-history-panel">
      <div className="trade-history-title">
        История сделок <span style={{ opacity: 0.7 }}>({total})</span>{" "}
        <span style={{ opacity: 0.7, fontSize: 12 }}>
          {source === "backtest"
            ? "Источник: Бэктест"
            : source === "orders"
              ? "Источник: Биржевые/локальные ордера"
              : "Источник: Симуляция"}
        </span>
      </div>
      <div className="trade-history-controls">
        <button type="button" onClick={() => setPage((p) => Math.max(0, p - 1))} disabled={safePage === 0}>
          Назад
        </button>
        <span>
          Стр. {safePage + 1}/{totalPages}
        </span>
        <button
          type="button"
          onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
          disabled={safePage >= totalPages - 1}
        >
          Вперед
        </button>
      </div>
      <div className="trade-history-table">
        <div className="trade-history-row head">
          <span>Время входа</span>
          <span>Время выхода</span>
          <span>Сторона</span>
          <span>Вход</span>
          <span>Выход</span>
          <span>Результат</span>
          <span>PnL</span>
          <span>TP</span>
        </div>
        {pageItems.map((trade) => {
          const pnl = Number.isFinite(trade.pnl) ? trade.pnl : 0;
          const pnlText = `${pnl > 0 ? "+" : ""}${pnl.toFixed(2)}%`;
          const hitText = trade.tp_hits?.length
            ? trade.tp_hits.map((hit) => `TP${hit.level}`).join(", ")
            : trade.exit_reason?.startsWith("TP")
              ? trade.exit_reason
              : "-";
          const isOpen = expandedId === trade.id;
          return (
            <div key={trade.id}>
              <div
                className={`trade-history-row ${trade.exit_reason?.toLowerCase()}`}
                onClick={() => setExpandedId(isOpen ? null : trade.id)}
                role="button"
                tabIndex={0}
              >
                <span>{formatTime(trade.entry_time)}</span>
                <span>{trade.exit_reason === "OPEN" ? "-" : formatTime(trade.exit_time)}</span>
                <span className={`trade-side ${trade.side}`}>{trade.side.toUpperCase()}</span>
                <span>{formatPrice(trade.entry)}</span>
                <span>{formatPrice(trade.exit_price)}</span>
                <span className="trade-exit">{trade.exit_reason}</span>
                <span className={pnl >= 0 ? "trade-pnl positive" : "trade-pnl negative"}>
                  {pnlText}
                </span>
                <span className="trade-hits">{hitText}</span>
              </div>
              {isOpen ? (
                <div className="trade-history-detail">
                  <div>
                    <strong>Причина:</strong>{" "}
                    {trade.rationale || "Нет описания"}
                  </div>
                  {Number.isFinite(trade.confidence) ? (
                    <div>
                      <strong>Уверенность:</strong> {(trade.confidence * 100).toFixed(1)}%
                    </div>
                  ) : null}
                  {trade.trade_plan?.stop_loss || trade.trade_plan?.take_profit || trade.trade_plan?.take_levels ? (
                    <div>
                      <strong>План:</strong>{" "}
                      {Number.isFinite(trade.trade_plan?.stop_loss) ? `SL ${formatPrice(trade.trade_plan.stop_loss)} ` : ""}
                      {Array.isArray(trade.trade_plan?.take_levels)
                        ? `TP ${trade.trade_plan.take_levels.filter(Number.isFinite).slice(0, 3).map(formatPrice).join(", ")}`
                        : Number.isFinite(trade.trade_plan?.take_profit)
                          ? `TP ${formatPrice(trade.trade_plan.take_profit)}`
                          : ""}
                    </div>
                  ) : null}
                  {trade.chart_pattern ? (
                    <div>
                      <strong>Фигура:</strong> {trade.chart_pattern.replace(/_/g, " ")}
                    </div>
                  ) : null}
                  {trade.candle_bullish?.length || trade.candle_bearish?.length ? (
                    <div>
                      <strong>Свечи:</strong>{" "}
                      {[...(trade.candle_bullish || []).slice(0, 4), ...(trade.candle_bearish || []).slice(0, 4)]
                        .map((name) => name.replace("CDL", ""))
                        .join(", ")}
                    </div>
                  ) : null}
                </div>
              ) : null}
            </div>
          );
        })}
      </div>
    </div>
  );
}
