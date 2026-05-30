import { buildTradeProjection } from "../utils/tradeProjection.js";

function fmt(value, digits = 4) {
  if (!Number.isFinite(value)) return "-";
  return Number(value).toFixed(digits);
}

function clampLeverage(value) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return 1;
  return Math.min(125, Math.max(1, Math.round(parsed)));
}

export default function OrderConfirmModal({
  open,
  onClose,
  onConfirm,
  market,
  side,
  symbol,
  orderType,
  quantity,
  onQuantityChange,
  quoteAmount,
  onQuoteAmountChange,
  autoQuantity,
  leverage,
  onLeverageChange,
  entryPrice,
  stopLoss,
  takeProfit,
  takeLevels,
  minQty,
  minNotional,
  stepSize,
}) {
  if (!open) return null;

  const allocatedAmount = autoQuantity
    ? Number(quoteAmount || 0)
    : Number(quantity || 0) * Number(entryPrice || 0);
  const currentLeverage = clampLeverage(leverage);
  const estNotional = market === "futures" ? allocatedAmount * currentLeverage : allocatedAmount;
  const belowNotional = Number.isFinite(minNotional) && estNotional > 0 && estNotional < minNotional;
  const byQty = Number.isFinite(minQty) && Number.isFinite(entryPrice) ? minQty * entryPrice : 0;
  const recommendedNotional = Math.max(byQty || 0, Number(minNotional || 0));
  const recommendedMin = market === "futures" ? recommendedNotional / currentLeverage : recommendedNotional;
  const projection = buildTradeProjection({
    entryPrice,
    stopLoss,
    takeProfit,
    takeLevels,
    quantity,
    quoteAmount,
    autoQuantity,
    market,
    leverage: currentLeverage,
  });

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="order-modal" onClick={(e) => e.stopPropagation()}>
        <div className="order-modal-title">Подтверждение ордера</div>
        <div className="order-modal-grid">
          <div>Пара</div><strong>{symbol}</strong>
          <div>Рынок</div><strong>{market.toUpperCase()}</strong>
          <div>Сторона</div><strong>{side}</strong>
          <div>Тип</div><strong>{orderType}</strong>
          <div>Цена входа</div><strong>{fmt(entryPrice, 2)}</strong>
          <div>Количество</div>
          <strong>
            <input
              type="number"
              min={0}
              step="0.000001"
              value={Number(quantity || 0)}
              onChange={(event) => onQuantityChange?.(Number(event.target.value || 0))}
              disabled={autoQuantity}
            />
          </strong>
          <div>{market === "futures" ? "Маржа на сделку" : "Сумма сделки"}</div>
          <strong>
            <input
              type="number"
              min={0}
              step="0.01"
              value={Number(quoteAmount || 0)}
              onChange={(event) => onQuoteAmountChange?.(Number(event.target.value || 0))}
              disabled={!autoQuantity}
            />
          </strong>
          {market === "futures" ? (
            <>
              <div>Плечо</div>
              <strong className="order-modal-leverage">
                <input
                  className="order-modal-leverage-range"
                  type="range"
                  min={1}
                  max={125}
                  step={1}
                  value={currentLeverage}
                  onChange={(event) => onLeverageChange?.(clampLeverage(event.target.value))}
                />
                <input
                  className="order-modal-leverage-number"
                  type="number"
                  min={1}
                  max={125}
                  value={currentLeverage}
                  onChange={(event) => onLeverageChange?.(clampLeverage(event.target.value))}
                />
                <span>x{currentLeverage}</span>
              </strong>
            </>
          ) : null}
          <div>Min Qty</div><strong>{fmt(minQty, 6)}</strong>
          <div>Min Notional</div><strong>{fmt(minNotional, 2)} USDT</strong>
          <div>Шаг количества</div><strong>{fmt(stepSize, 6)}</strong>
        </div>
        <div className="order-modal-hint">
          Минимальная рекомендуемая {market === "futures" ? "маржа" : "сумма"}: {fmt(recommendedMin, 2)} USDT
        </div>
        {projection ? (
          <div className="trade-projection">
            <div className="trade-projection-title">Ожидаемый результат</div>
            <div className="trade-projection-summary">
              <span>{market === "futures" ? "Позиция с плечом" : "Позиция"} <strong>${fmt(projection.positionValue, 2)}</strong></span>
              {market === "futures" ? <span>Выделено маржи <strong>${fmt(projection.margin, 2)}</strong></span> : null}
              <span>Количество <strong>{fmt(projection.quantity, 6)}</strong></span>
            </div>
            <div className="trade-projection-level loss">
              <span>SL {fmt(stopLoss, 4)}</span>
              <strong>{projection.stop ? `-$${fmt(projection.stop.amount, 2)}` : "-"}</strong>
              <small>{projection.stop && projection.stop.roi !== null ? `${fmt(projection.stop.roi, 2)}% маржи` : "-"}</small>
            </div>
            {projection.takes.map((take) => (
              <div className="trade-projection-level profit" key={`${take.label}-${take.price}`}>
                <span>{take.label} {fmt(take.price, 4)}</span>
                <strong>+${fmt(take.amount, 2)}</strong>
                <small>
                  {take.roi !== null ? `${fmt(take.roi, 2)}% маржи` : "-"}
                  {take.rr !== null ? ` · RR 1:${fmt(take.rr, 1)}` : ""}
                </small>
              </div>
            ))}
            <div className="trade-projection-note">Оценка без комиссии и проскальзывания.</div>
          </div>
        ) : null}
        {belowNotional ? (
          <div className="order-modal-warning">
            {market === "futures" ? "Маржа" : "Сумма"} ниже минимума биржи. Увеличь значение минимум до {fmt(recommendedMin, 2)} USDT.
          </div>
        ) : null}
        <div className="order-modal-actions">
          <button className="ghost" onClick={onClose}>Отмена</button>
          <button className="primary" onClick={onConfirm} disabled={belowNotional}>Подтвердить</button>
        </div>
      </div>
    </div>
  );
}
