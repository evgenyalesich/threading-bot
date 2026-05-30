import { buildTradeProjection } from "../utils/tradeProjection.js";

function formatNum(value, digits = 6) {
  if (value === null || value === undefined || value === "") return "-";
  const num = Number(value);
  if (!Number.isFinite(num)) return "-";
  if (Math.abs(num) >= 100) return num.toFixed(2);
  if (Math.abs(num) >= 1) return num.toFixed(4);
  return num.toFixed(digits);
}

function formatTime(value) {
  if (!value) return "-";
  const ts = typeof value === "number" ? value : Date.parse(value);
  if (!Number.isFinite(ts)) return "-";
  return new Date(ts).toLocaleString();
}

function sameSymbol(a, b) {
  return String(a || "").replace("-", "").toUpperCase() === String(b || "").replace("-", "").toUpperCase();
}

export default function OrderDetailsModal({ open, order, trades = [], loading, onClose }) {
  if (!open || !order) return null;

  const relatedTrades = trades.filter((trade) => sameSymbol(trade.symbol, order.symbol));
  const takeLevels = Array.isArray(order.take_levels) ? order.take_levels.filter((v) => Number.isFinite(v)) : [];
  const projection = buildTradeProjection({
    entryPrice: order.price,
    stopLoss: order.stop_loss,
    takeProfit: order.take_profit,
    takeLevels,
    quantity: order.quantity,
    market: order.market,
    leverage: order.leverage,
  });

  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <div className="modal-card order-details-modal" onClick={(event) => event.stopPropagation()}>
        <header>
          <div>
            <h3>Детали ордера</h3>
            <span>
              {order.symbol} · {order.market}/{order.trade_env || "n/a"} · {order.status}
            </span>
          </div>
          <button className="ghost" type="button" onClick={onClose}>
            Закрыть
          </button>
        </header>

        <div className="modal-content">
          <div className="order-detail-grid">
            <div><span>Сторона</span><strong>{order.side}</strong></div>
            <div><span>Тип</span><strong>{order.order_type}</strong></div>
            <div><span>Количество</span><strong>{formatNum(order.quantity)}</strong></div>
            <div><span>Вход</span><strong>{formatNum(order.price)}</strong></div>
            <div><span>Выход</span><strong>{formatNum(order.exit_price)}</strong></div>
            <div><span>SL</span><strong>{formatNum(order.stop_loss)}</strong></div>
            <div><span>TP</span><strong>{formatNum(order.take_profit)}</strong></div>
            <div><span>Плечо</span><strong>{order.leverage ? `x${order.leverage}` : "-"}</strong></div>
            <div><span>Закрыт</span><strong>{formatTime(order.closed_at)}</strong></div>
          </div>

          <div className="order-detail-section">
            <div className="account-subtitle">Защитные ордера</div>
            <div className="order-detail-line">Entry ID: {order.client_order_id || "-"}</div>
            <div className="order-detail-line">Stop ID: {order.stop_order_id || "-"}</div>
            <div className="order-detail-line">Take ID: {order.take_order_id || order.oco_order_id || "-"}</div>
            {takeLevels.length ? (
              <div className="order-detail-line">TP уровни: {takeLevels.map((level) => formatNum(level)).join(", ")}</div>
            ) : null}
            {order.reject_reason ? <div className="journal-reject">Binance: {order.reject_reason}</div> : null}
          </div>

          {projection ? (
            <div className="order-detail-section trade-projection">
              <div className="account-subtitle">Ожидаемый результат</div>
              <div className="trade-projection-summary">
                <span>{order.market === "futures" ? "Позиция с плечом" : "Позиция"} <strong>${formatNum(projection.positionValue, 2)}</strong></span>
                {order.market === "futures" ? <span>Выделено маржи <strong>${formatNum(projection.margin, 2)}</strong></span> : null}
              </div>
              <div className="trade-projection-level loss">
                <span>SL {formatNum(order.stop_loss)}</span>
                <strong>{projection.stop ? `-$${formatNum(projection.stop.amount, 2)}` : "-"}</strong>
                <small>{projection.stop && projection.stop.roi !== null ? `${formatNum(projection.stop.roi, 2)}% маржи` : "-"}</small>
              </div>
              {projection.takes.map((take) => (
                <div className="trade-projection-level profit" key={`${take.label}-${take.price}`}>
                  <span>{take.label} {formatNum(take.price)}</span>
                  <strong>+${formatNum(take.amount, 2)}</strong>
                  <small>
                    {take.roi !== null ? `${formatNum(take.roi, 2)}% маржи` : "-"}
                    {take.rr !== null ? ` · RR 1:${formatNum(take.rr, 1)}` : ""}
                  </small>
                </div>
              ))}
              <div className="trade-projection-note">Оценка без комиссии и проскальзывания.</div>
            </div>
          ) : null}

          <div className="order-detail-section">
            <div className="account-subtitle">Исполнения Binance</div>
            {loading ? <div className="empty-state">Загрузка...</div> : null}
            {!loading && !relatedTrades.length ? <div className="empty-state">Исполнений по этой паре нет</div> : null}
            {!loading && relatedTrades.length ? (
              <div className="order-fill-list">
                {relatedTrades.slice(0, 30).map((trade) => (
                  <div className="order-fill-row" key={`${trade.id ?? trade.orderId ?? "fill"}-${trade.time}`}>
                    <strong>{trade.side || trade.positionSide || "-"}</strong>
                    <span>qty {trade.qty || trade.executedQty || trade.size || "-"}</span>
                    <span>price {formatNum(trade.price || trade.avgPrice)}</span>
                    <span>{formatTime(trade.time)}</span>
                  </div>
                ))}
              </div>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
}
