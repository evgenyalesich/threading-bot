import { useMemo, useState } from "react";
import { buildTradeProjection } from "../utils/tradeProjection.js";

function formatPrice(value) {
  if (!value) return "-";
  if (value >= 1) return value.toFixed(2);
  return value.toFixed(6);
}

function futuresPositionRoi(position) {
  if (!position) return null;
  const upnl = Number(position.unrealized_profit);
  const margin = Number(position.margin);
  if (Number.isFinite(upnl) && Number.isFinite(margin) && margin > 0) {
    return (upnl / margin) * 100;
  }
  const entry = Number(position.entry_price);
  const mark = Number(position.mark_price);
  const leverage = Number(position.leverage);
  const side = Number(position.position_amt) >= 0 ? 1 : -1;
  if (entry > 0 && mark > 0) {
    const priceMove = ((mark - entry) / entry) * 100 * side;
    return Number.isFinite(leverage) && leverage > 0 ? priceMove * leverage : priceMove;
  }
  return null;
}

function computePnl(order, lastPrice, futuresPosition) {
  const isClosed = ["closed", "filled", "cancelled"].includes((order.status || "").toLowerCase());
  if (isClosed) {
    if (Number.isFinite(order.realized_pnl)) return Number(order.realized_pnl);
    const entry = Number(order.price);
    const exit = Number(order.exit_price);
    const side = order.side === "BUY" ? 1 : -1;
    return entry > 0 && exit > 0 ? ((exit - entry) / entry) * 100 * side : 0;
  }
  if (futuresPosition) {
    return futuresPositionRoi(futuresPosition);
  }
  if (!lastPrice || !order.price) return null;
  const side = order.side === "BUY" ? 1 : -1;
  const percent = ((lastPrice - order.price) / order.price) * 100 * side;
  return percent;
}

function resolveExecutionBadge(order) {
  if (order.status === "rejected" || order.status === "submitted_exit_failed" || order.status === "exit_failed") {
    return { text: "exchange_rejected", className: "rejected" };
  }
  if (order.status === "stored") {
    return { text: "simulation_only", className: "simulation" };
  }
  if (order.status === "submitted" || order.status === "submitted_wait_fill" || order.status === "wait_fill" || order.client_order_id) {
    return { text: "exchange_submitted", className: "submitted" };
  }
  return { text: order.status || "unknown", className: "neutral" };
}

export default function TradeJournal({ orders, priceMap, futuresPositionMap, onSelectOrder, onCloseOrder }) {
  const [tab, setTab] = useState("orders");
  const executionItems = useMemo(
    () =>
      orders.filter((order) =>
        order.reject_reason ||
        ["rejected", "exit_failed", "submitted_exit_failed", "close_failed", "wait_fill"].includes(
          (order.status || "").toLowerCase()
        )
      ),
    [orders]
  );

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
      <div className="journal-tabs">
        <button
          type="button"
          className={tab === "orders" ? "active" : ""}
          onClick={() => setTab("orders")}
        >
          Orders
        </button>
        <button
          type="button"
          className={tab === "execution" ? "active" : ""}
          onClick={() => setTab("execution")}
        >
          Execution log
        </button>
      </div>
      <div className="journal-table">
        {(tab === "execution" ? executionItems : orders).map((order) => {
          const lastPrice = priceMap.get(order.symbol);
          const position = futuresPositionMap?.get((order.symbol || "").replace("-", "").toUpperCase());
          const pnl = computePnl(order, lastPrice, position);
          const pnlClass = pnl === null ? "neutral" : pnl >= 0 ? "positive" : "negative";
          const badge = resolveExecutionBadge(order);
          const isClosed = ["closed", "filled", "cancelled"].includes((order.status || "").toLowerCase());
          const displayEntry = !isClosed && position ? Number(position.entry_price) : Number(order.price);
          const projection = buildTradeProjection({
            entryPrice: order.price,
            stopLoss: order.stop_loss,
            takeProfit: order.take_profit,
            takeLevels: order.take_levels,
            quantity: order.quantity,
            market: order.market,
            leverage: order.leverage,
          });
          return (
            <div key={order.id} className="journal-row-wrap">
            <button
              type="button"
              className="journal-row"
              onClick={() => onSelectOrder?.(order)}
            >
              <div>
                <strong>{order.symbol}</strong>
                <span>
                  {order.side} · {order.order_type} · {order.market}/{order.trade_env || "n/a"} · {order.status} ·{" "}
                  {new Date(order.created_at).toLocaleString()}
                </span>
                <span className={`journal-badge ${badge.className}`}>{badge.text}</span>
                {order.reject_reason ? (
                  <span className="journal-reject">Binance: {order.reject_reason}</span>
                ) : null}
                <span>
                  SL/TP IDs: {order.stop_order_id || "-"} / {order.take_order_id || order.oco_order_id || "-"}
                </span>
                {projection ? (
                  <span className="journal-projection">
                    {order.market === "futures" ? "Позиция с плечом" : "Позиция"} ${projection.positionValue.toFixed(2)}
                    {order.market === "futures" ? ` · Маржа $${projection.margin.toFixed(2)}` : ""}
                    {" · "}
                    Риск {projection.stop ? `-$${projection.stop.amount.toFixed(2)}` : "-"}
                    {" · "}
                    {projection.takes.map((take) => `${take.label} +$${take.amount.toFixed(2)}`).join(" · ")}
                  </span>
                ) : null}
              </div>
              <div>
                <span className="journal-price">Вход: {formatPrice(displayEntry)}</span>
                {!isClosed && position?.mark_price ? <span className="journal-price">Mark: {formatPrice(position.mark_price)}</span> : null}
                {isClosed ? (
                  <span className="journal-price">Выход: {formatPrice(order.exit_price)}</span>
                ) : null}
                <span className={`journal-pnl ${pnlClass}`}>{pnl === null ? "-" : `${pnl.toFixed(2)}%`}</span>
              </div>
            </button>
            {tab === "orders" && !isClosed ? (
              <button type="button" className="journal-close-btn" onClick={() => onCloseOrder?.(order)}>
                Закрыть
              </button>
            ) : null}
            </div>
          );
        })}
        {tab === "execution" && executionItems.length === 0 ? (
          <div className="empty-state">Пока нет ошибок/отклонений исполнения</div>
        ) : null}
      </div>
    </div>
  );
}
