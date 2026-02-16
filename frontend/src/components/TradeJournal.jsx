function formatPrice(value) {
  if (!value) return "-";
  if (value >= 1) return value.toFixed(2);
  return value.toFixed(6);
}

function computePnl(order, lastPrice) {
  if (!lastPrice || !order.price) return null;
  const side = order.side === "BUY" ? 1 : -1;
  const percent = ((lastPrice - order.price) / order.price) * 100 * side;
  return percent;
}

export default function TradeJournal({ orders, priceMap, onSelectOrder }) {
  if (!orders.length) {
    return (
      <div className="trade-journal">
        <div className="panel-title">Журнал ордеров</div>
        <div className="empty-state">Ордеров пока нет</div>
      </div>
    );
  }

  return (
    <div className="trade-journal">
      <div className="panel-title">Журнал ордеров</div>
      <div className="journal-table">
        {orders.map((order) => {
          const lastPrice = priceMap.get(order.symbol);
          const pnl = computePnl(order, lastPrice);
          const pnlClass = pnl === null ? "neutral" : pnl >= 0 ? "positive" : "negative";
          return (
            <button
              key={order.id}
              type="button"
              className="journal-row"
              onClick={() => onSelectOrder?.(order)}
            >
              <div>
                <strong>{order.symbol}</strong>
                <span>
                  {order.side} · {order.order_type} · {order.market} · {order.status} ·{" "}
                  {new Date(order.created_at).toLocaleString()}
                </span>
              </div>
              <div>
                <span className="journal-price">Вход: {formatPrice(order.price)}</span>
                <span className={`journal-pnl ${pnlClass}`}>{pnl === null ? "-" : `${pnl.toFixed(2)}%`}</span>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
