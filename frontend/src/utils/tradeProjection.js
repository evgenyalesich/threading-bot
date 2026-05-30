function positiveNumber(value) {
  const number = Number(value);
  return Number.isFinite(number) && number > 0 ? number : null;
}

function levelProjection(entry, level, quantity, margin) {
  const price = positiveNumber(level);
  if (!price) return null;
  const amount = Math.abs(price - entry) * quantity;
  return {
    price,
    amount,
    roi: margin > 0 ? (amount / margin) * 100 : null,
  };
}

export function buildTradeProjection({
  entryPrice,
  stopLoss,
  takeProfit,
  takeLevels,
  quantity,
  quoteAmount,
  autoQuantity = false,
  market = "spot",
  leverage = 1,
}) {
  const entry = positiveNumber(entryPrice);
  if (!entry) return null;

  const safeLeverage = market === "futures" ? positiveNumber(leverage) || 1 : 1;
  const allocatedAmount = positiveNumber(quoteAmount);
  const resolvedQuantity = autoQuantity
    ? (allocatedAmount * safeLeverage) / entry
    : positiveNumber(quantity);
  if (!Number.isFinite(resolvedQuantity) || resolvedQuantity <= 0) return null;

  const positionValue = resolvedQuantity * entry;
  const margin = positionValue / safeLeverage;
  const stop = levelProjection(entry, stopLoss, resolvedQuantity, margin);
  const rawTakes = Array.isArray(takeLevels) && takeLevels.length ? takeLevels : [takeProfit];
  const takes = rawTakes
    .map((level, index) => {
      const projection = levelProjection(entry, level, resolvedQuantity, margin);
      return projection ? { ...projection, label: `TP${index + 1}` } : null;
    })
    .filter(Boolean);

  return {
    quantity: resolvedQuantity,
    positionValue,
    margin,
    stop,
    takes: takes.map((take) => ({
      ...take,
      rr: stop?.amount > 0 ? take.amount / stop.amount : null,
    })),
  };
}
