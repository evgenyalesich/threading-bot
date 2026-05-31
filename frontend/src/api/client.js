const API_BASE = import.meta.env.VITE_API_BASE || "/api";

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });

  if (!response.ok) {
    const text = await response.text();
    // FastAPI typically returns {"detail": "..."}; keep a human-readable message.
    let message = text || "Request failed";
    try {
      const parsed = JSON.parse(text);
      const detail = parsed?.detail;
      if (typeof detail === "string" && detail) {
        message = detail;
      }
    } catch {
      // ignore JSON parse errors; fall back to raw text
    }
    throw new Error(message);
  }

  return response.json();
}

export async function syncMarket(symbol, timeframe, lookbackDays, market, binanceSymbol, dataEnv) {
  return request("/market/sync", {
    method: "POST",
    body: JSON.stringify({
      symbol,
      timeframe,
      lookback_days: lookbackDays,
      market,
      binance_symbol: binanceSymbol,
      data_env: dataEnv,
    }),
  });
}

export async function fetchCandles(symbol, timeframe, limit = 200, before) {
  const params = new URLSearchParams({ symbol, timeframe, limit: String(limit) });
  if (before) {
    params.set("before", before);
  }
  return request(`/market/candles?${params.toString()}`);
}

export async function runAnalysis(
  symbol,
  timeframe,
  lookbackDays,
  market,
  autoExecute,
  quantity,
  quoteAmount,
  autoQuantity,
  tradeEnv,
  attachOrders,
  autoBreakeven,
  filters
) {
  return request("/analysis/run", {
    method: "POST",
    body: JSON.stringify({
      symbol,
      timeframe,
      lookback_days: lookbackDays,
      market,
      auto_execute: autoExecute,
      quantity,
      quote_amount: quoteAmount,
      auto_quantity: autoQuantity,
      trade_env: tradeEnv,
      attach_orders: attachOrders,
      auto_breakeven: autoBreakeven,
      ...filters,
    }),
  });
}

export async function fetchSignals(symbol, limit = 50, timeframe) {
  const params = new URLSearchParams({ limit: String(limit) });
  if (symbol) {
    params.set("symbol", symbol);
  }
  if (timeframe) {
    params.set("timeframe", timeframe);
  }
  return request(`/signals?${params.toString()}`);
}

export async function fetchSignalById(signalId) {
  return request(`/signals/${signalId}`);
}

export async function resolveSymbol(symbol, market = "spot") {
  const params = new URLSearchParams({ symbol, market });
  return request(`/symbols/resolve?${params.toString()}`);
}

export async function fetchMappings(market) {
  const params = new URLSearchParams();
  if (market) {
    params.set("market", market);
  }
  return request(`/symbols?${params.toString()}`);
}

export async function createMapping(payload) {
  return request("/symbols", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function updateMapping(id, payload) {
  return request(`/symbols/${id}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export async function deleteMapping(id) {
  return request(`/symbols/${id}`, {
    method: "DELETE",
  });
}

export async function fetchPairs(market = "spot", quote, minVolatility, dataEnv = "real") {
  const params = new URLSearchParams({ market, data_env: dataEnv });
  if (quote) {
    params.set("quote", quote);
  }
  if (typeof minVolatility === "number") {
    params.set("min_volatility", String(minVolatility));
  }
  return request(`/market/pairs?${params.toString()}`);
}

export async function scanMarket(payload) {
  return request("/analysis/scan", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function backfillSignals(payload) {
  return request("/analysis/backfill", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function runBacktest(payload) {
  return request("/analysis/backtest", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function explainAnalysis(payload) {
  return request("/analysis/explain", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function fetchOrders(limit = 50) {
  const params = new URLSearchParams({ limit: String(limit) });
  return request(`/orders?${params.toString()}`);
}

export async function placeOrder(payload) {
  return request("/orders", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function moveStopToBreakeven(orderId) {
  return request(`/orders/${orderId}/breakeven`, {
    method: "POST",
  });
}

export async function moveStopToPrice(orderId, price) {
  return request(`/orders/${orderId}/stop`, {
    method: "POST",
    body: JSON.stringify({ price }),
  });
}

export async function moveTakeToPrice(orderId, price) {
  return request(`/orders/${orderId}/take`, {
    method: "POST",
    body: JSON.stringify({ price }),
  });
}

export async function closeOrderPosition(orderId) {
  return request(`/orders/${orderId}/close`, {
    method: "POST",
  });
}

export async function fetchIndicators(symbol, timeframe, limit = 240) {
  const params = new URLSearchParams({ symbol, timeframe, limit: String(limit) });
  return request(`/market/indicators?${params.toString()}`);
}

export async function fetchAccountSummary(market = "spot", tradeEnv = "testnet") {
  const params = new URLSearchParams({ market, trade_env: tradeEnv });
  return request(`/account/summary?${params.toString()}`);
}

export async function fetchAccountTrades(market = "spot", tradeEnv = "testnet", symbol, limit = 50) {
  const params = new URLSearchParams({ market, trade_env: tradeEnv, limit: String(limit) });
  if (symbol) params.set("symbol", symbol);
  return request(`/account/trades?${params.toString()}`);
}
