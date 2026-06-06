import { useEffect, useMemo, useRef, useState } from "react";
import ChartPanel from "./components/ChartPanel.jsx";
import ControlPanel from "./components/ControlPanel.jsx";
import PairsPanel from "./components/PairsPanel.jsx";
import ScanResultsPanel from "./components/ScanResultsPanel.jsx";
import OrderDetailsModal from "./components/OrderDetailsModal.jsx";
import SignalList from "./components/SignalList.jsx";
import StatsPanel from "./components/StatsPanel.jsx";
import TradeHistoryPanel from "./components/TradeHistoryPanel.jsx";
import TradeJournal from "./components/TradeJournal.jsx";
import AnalysisDebugPanel from "./components/AnalysisDebugPanel.jsx";
import AccountPanel from "./components/AccountPanel.jsx";
import OrderConfirmModal from "./components/OrderConfirmModal.jsx";
import AutomationCenter from "./components/AutomationCenter.jsx";
import OrderBookPanel from "./components/OrderBookPanel.jsx";
import {
  approveAutomationSignal,
  closeOrderPosition,
  backfillSignals,
  disableAutomation,
  enableAutomation,
  fetchCandles,
  fetchIndicators,
  fetchOrderBook,
  fetchOrders,
  fetchPairs,
  fetchSignals,
  fetchAutomationState,
  fetchBacktestStatus,
  explainAnalysis,
  fetchAccountSummary,
  fetchAccountTrades,
  moveStopToBreakeven,
  moveStopToPrice,
  moveTakeToPrice,
  placeOrder,
  rejectAutomationSignal,
  resolveSymbol,
  runAnalysis,
  runAutomationNow,
  runBacktest,
  scanMarket,
  setAutomationMode,
  setAutomationTradeEnv,
  syncMarket,
  updateAutomationConfig,
} from "./api/client.js";

function toEpochSeconds(value) {
  return Math.floor(new Date(value).getTime() / 1000);
}

function timeframeToMs(tf) {
  if (!tf || tf.length < 2) return null;
  const unit = tf.slice(-1);
  const value = Number(tf.slice(0, -1));
  if (!Number.isFinite(value) || value <= 0) return null;
  if (unit === "m") return value * 60 * 1000;
  if (unit === "h") return value * 60 * 60 * 1000;
  if (unit === "d") return value * 24 * 60 * 60 * 1000;
  return null;
}

function resolvePriceStep(basePrice) {
  const base = Math.abs(Number(basePrice) || 0);
  if (base >= 10000) return 25;
  if (base >= 1000) return 5;
  if (base >= 100) return 0.5;
  if (base >= 1) return 0.01;
  return 0.0001;
}

function formatCompactNumber(value, digits = 2) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "--";
  return numeric.toLocaleString("ru-RU", {
    minimumFractionDigits: 0,
    maximumFractionDigits: digits,
  });
}

function humanizeApiError(code) {
  const map = {
    quote_amount_required: "Нужна сумма (Quote Amount).",
    quote_amount_invalid: "Сумма (Quote Amount) должна быть больше 0.",
    price_required: "Не удалось определить цену. Попробуй синхронизировать историю.",
    symbol_not_found: "Символ не найден на бирже для выбранного рынка.",
    min_qty: "Количество меньше минимально допустимого.",
    min_notional: "Сумма сделки меньше минимально допустимой (min notional).",
    qty_too_small: "Количество получилось слишком маленьким.",
    order_sizing_error: "Ошибка расчета количества ордера.",
    entry_price_required: "Нет цены входа (нельзя перенести в безубыток).",
    binance_timeout: "Binance API не отвечает (таймаут).",
    binance_unreachable: "Binance API недоступен.",
  };
  return map[code] || code;
}

function humanizeNoSignalReason(reason) {
  const map = {
    no_candles_in_db: "Нет свечей в базе. Сначала синхронизируй историю.",
    no_trend_data_or_insufficient: "Недостаточно данных тренда. Синхронизируй trend timeframe.",
    insufficient_entry_bars: "Недостаточно баров для расчета сигнала.",
    stoch_not_confirming: "Stochastic не подтверждает вход.",
    rsi_not_confirming: "RSI не подтверждает вход.",
    confidence_below_min: "Уверенность ниже минимального порога.",
    confirmations_below_min: "Недостаточно подтверждений для входа.",
    below_ema200_no_long: "Цена ниже EMA200, лонг отфильтрован.",
    above_ema200_no_short: "Цена выше EMA200, шорт отфильтрован.",
    higher_timeframe_bias_missing: "На 4H нет чистого направления, поэтому вход пропущен.",
    higher_timeframe_mismatch: "Вход против 4H тренда запрещен.",
    trend_too_flat: "Тренд слишком плоский, пропускаю флэт.",
    trend_less_informative: "Тренд слабый, поэтому стратегия ослабила его вес.",
    volatility_too_low: "Волатильность слишком низкая.",
    volatility_spike_skip: "Слишком резкий всплеск волатильности.",
    weak_signal_candle: "Сигнальная свеча слабая.",
    risk_too_wide: "Стоп слишком далеко от входа.",
    risk_too_tight: "Стоп слишком близко к входу.",
    zero_risk: "Некорректный риск-профиль сделки (zero risk).",
    pattern_required: "Стратегия ждала фигуру, но не нашла ее.",
    divergence_required: "Нужна дивергенция, но подтверждения не хватило.",
    candle_required: "Нужен свечной паттерн, но подтверждения не хватило.",
    volume_confirm_required: "Нужен объемный фильтр, но он не подтвердился.",
    explain_failed: "Не удалось получить объяснение.",
  };
  return map[reason] || reason;
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

function buildTradeHistory(candles, signals, limit) {
  if (!candles.length || !signals.length) return [];
  const chartData = candles.map((candle) => ({
    time: toEpochSeconds(candle.open_time),
    open: candle.open,
    high: candle.high,
    low: candle.low,
    close: candle.close,
  }));
  const orderedSignals = [...signals].sort(
    (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
  );
  const limitedSignals = limit > 0 ? orderedSignals.slice(-limit) : orderedSignals;
  const results = [];

  limitedSignals.forEach((signal) => {
    const plan = signal.meta?.trade_plan ?? {};
    const entry = Number.isFinite(plan.entry) ? plan.entry : signal.entry_price;
    const stop = Number.isFinite(plan.stop_loss) ? plan.stop_loss : signal.stop_loss;
    const rawTps = Array.isArray(plan.take_levels)
      ? plan.take_levels
      : [plan.take_profit ?? signal.take_profit];
    const takeLevels = rawTps.filter((level) => Number.isFinite(level));
    if (!Number.isFinite(entry)) return;
    const entryTime = toEpochSeconds(signal.created_at);
    const startIndex = chartData.findIndex((candle) => candle.time >= entryTime);
    if (startIndex < 0) return;
    const side = signal.signal_type === "short" ? -1 : 1;
    const tpHits = [];
    let currentStop = stop;
    let movedToBe = false;
    let exit = null;

    for (let i = startIndex; i < chartData.length; i += 1) {
      const candle = chartData[i];
      const hitStop =
        Number.isFinite(currentStop) &&
        (side > 0 ? candle.low <= currentStop : candle.high >= currentStop);
      if (hitStop) {
        exit = {
          time: candle.time,
          price: currentStop,
          reason: movedToBe && Math.abs(currentStop - entry) < entry * 0.0001 ? "BE" : "SL",
        };
        break;
      }

      if (takeLevels.length) {
        takeLevels.forEach((level, index) => {
          if (tpHits.some((hit) => hit.level === index + 1)) return;
          const hitTp = side > 0 ? candle.high >= level : candle.low <= level;
          if (!hitTp) return;
          tpHits.push({
            level: index + 1,
            price: level,
            time: candle.time,
          });
          if (!movedToBe && index === 0) {
            currentStop = level;
            movedToBe = true;
          }
        });
        if (tpHits.length && tpHits.length >= takeLevels.length) {
          const lastHit = tpHits[tpHits.length - 1];
          exit = {
            time: lastHit.time,
            price: lastHit.price,
            reason: `TP${lastHit.level}`,
          };
          break;
        }
      }
    }

    const lastCandle = chartData[chartData.length - 1];
    const exitData =
      exit ?? { time: lastCandle.time, price: lastCandle.close, reason: "OPEN" };
    const pnl = ((exitData.price - entry) / entry) * 100 * side;
    results.push({
      id: signal.id,
      symbol: signal.symbol,
      timeframe: signal.timeframe,
      side: signal.signal_type,
      entry,
      entry_time: entryTime,
      exit_price: exitData.price,
      exit_time: exitData.time,
      exit_reason: exitData.reason,
      pnl,
      tp_hits: tpHits,
      rationale: signal.rationale,
      chart_pattern: signal.meta?.chart_pattern?.name ?? null,
      candle_bullish: signal.meta?.candles?.bullish ?? [],
      candle_bearish: signal.meta?.candles?.bearish ?? [],
    });
  });

  return results;
}

export default function App() {
  const [symbol, setSymbol] = useState("BTCUSDT");
  const [timeframe, setTimeframe] = useState("1h");
  const [lookbackDays, setLookbackDays] = useState(120);
  const [market, setMarket] = useState("spot");
  const [dataEnv, setDataEnv] = useState("real");
  const [tradeEnv, setTradeEnv] = useState("testnet");
  const [quantity, setQuantity] = useState(0.001);
  const [quoteAmount, setQuoteAmount] = useState(0.5);
  const [autoQuantity, setAutoQuantity] = useState(true);
  const [attachOrders, setAttachOrders] = useState(true);
  const [autoBreakeven, setAutoBreakeven] = useState(true);
  const [binanceSymbol, setBinanceSymbol] = useState(null);
  const [candles, setCandles] = useState([]);
  const [signals, setSignals] = useState([]);
  const [orders, setOrders] = useState([]);
  const [pairs, setPairs] = useState([]);
  const [pairsLoading, setPairsLoading] = useState(false);
  const [pairSearch, setPairSearch] = useState("");
  const [minVolatility, setMinVolatility] = useState(0);
  const [maxPrice, setMaxPrice] = useState(0);
  const [maxNotional, setMaxNotional] = useState(0);
  const [quoteAsset, setQuoteAsset] = useState("ALL");
  const [selectedPair, setSelectedPair] = useState(null);
  const [scanResults, setScanResults] = useState([]);
  const [scanMeta, setScanMeta] = useState(null);
  const [scanDiagnostics, setScanDiagnostics] = useState(null);
  const [scanRunning, setScanRunning] = useState(false);
  const [scanMode, setScanMode] = useState("market");
  const [scanLimit, setScanLimit] = useState(50);
  const [scanMaxPairs, setScanMaxPairs] = useState(631);
  const [scanAutoSync, setScanAutoSync] = useState(false);
  const [onlyNewSignalsMinutes, setOnlyNewSignalsMinutes] = useState(60);
  const [newSignalModal, setNewSignalModal] = useState({ open: false, first: null, count: 0 });
  const [stopDragConfirmModal, setStopDragConfirmModal] = useState({
    open: false,
    order: null,
    nextStop: null,
  });
  const [chartStopInput, setChartStopInput] = useState("");
  const [chartTakeInput, setChartTakeInput] = useState("");
  const [activeOrder, setActiveOrder] = useState(null);
  const [indicatorData, setIndicatorData] = useState(null);
  const [mode, setMode] = useState("semi");
  const [h1Timeframe, setH1Timeframe] = useState("1h");
  const [trendTimeframe, setTrendTimeframe] = useState("4h");
  const [strategy, setStrategy] = useState("adaptive_pattern_confluence");

  const [status, setStatus] = useState("Ожидание");
  const [sidebarWidth, setSidebarWidth] = useState(360);
  const [chartHeight, setChartHeight] = useState(520);
  const [showSidePanel, setShowSidePanel] = useState(true);
  const [showEma, setShowEma] = useState(true);
  const [showFib, setShowFib] = useState(true);
  const [showDivergence, setShowDivergence] = useState(true);
  const [showCandlePatterns, setShowCandlePatterns] = useState(false);
  const [showChartPatterns, setShowChartPatterns] = useState(true);
  const [showElliott, setShowElliott] = useState(false);
  const [showSupportRes, setShowSupportRes] = useState(true);
  const [showTradePlan, setShowTradePlan] = useState(true);
  const [showBBands, setShowBBands] = useState(false);
  const [showVolume, setShowVolume] = useState(true);
  const [showAtr, setShowAtr] = useState(false);
  const [showRsi, setShowRsi] = useState(true);
  const [showPatternLabels, setShowPatternLabels] = useState(true);
  const [patternLimit, setPatternLimit] = useState(15);
  const [showPatternFill, setShowPatternFill] = useState(true);
  const [patternFillBands, setPatternFillBands] = useState(4);
  const [patternFillLimit, setPatternFillLimit] = useState(3);
  const [showUnconfirmedPatterns, setShowUnconfirmedPatterns] = useState(true);
  const [showTradeExits, setShowTradeExits] = useState(true);
  const [tradeHistoryLimit, setTradeHistoryLimit] = useState(20);
  const [showTradePaths, setShowTradePaths] = useState(true);
  const [chartBars, setChartBars] = useState(1200);
  const [backfillStride, setBackfillStride] = useState(1);
  const [backfillMaxBars, setBackfillMaxBars] = useState(20000);
  const [autoFit, setAutoFit] = useState(false);
  const [minConfidence, setMinConfidence] = useState(0.35);
  const [minConfirmations, setMinConfirmations] = useState(1);
  const [requirePattern, setRequirePattern] = useState(false);
  const [requireDivergence, setRequireDivergence] = useState(false);
  const [requireCandle, setRequireCandle] = useState(false);
  const [requireVolumeConfirm, setRequireVolumeConfirm] = useState(false);
  const [requireTrendFilter, setRequireTrendFilter] = useState(true);
  const [confluenceTolerance, setConfluenceTolerance] = useState(0);
  const [backtestStats, setBacktestStats] = useState(null);
  const [backtestTrades, setBacktestTrades] = useState([]);
  const [backtestMeta, setBacktestMeta] = useState(null);
  const [backtestRunning, setBacktestRunning] = useState(false);
  const [backtestMode, setBacktestMode] = useState("market");
  const [backtestProgress, setBacktestProgress] = useState(null);
  const [analysisDebug, setAnalysisDebug] = useState(null);
  const [accountSummary, setAccountSummary] = useState(null);
  const [accountTrades, setAccountTrades] = useState([]);
  const [automationState, setAutomationState] = useState(null);
  const [automationLoading, setAutomationLoading] = useState(false);
  const [orderBook, setOrderBook] = useState(null);
  const [orderBookLoading, setOrderBookLoading] = useState(false);
  const [orderBookError, setOrderBookError] = useState("");
  const [confirmOrderOpen, setConfirmOrderOpen] = useState(false);
  const [leverage, setLeverage] = useState(25);
  const [fitRequest, setFitRequest] = useState(0);
  const [activeTab, setActiveTab] = useState("trade");
  const [wsConnected, setWsConnected] = useState(false);
  const [tradeWsConnected, setTradeWsConnected] = useState(false);
  const [lastTickAt, setLastTickAt] = useState(null);
  const [lastSyncAt, setLastSyncAt] = useState(null);
  const [autoSyncRunning, setAutoSyncRunning] = useState(false);
  const [wsRetryTick, setWsRetryTick] = useState(0);
  const [liveTickSeq, setLiveTickSeq] = useState(0);
  const [feedSource, setFeedSource] = useState("idle");
  const [tradeReconnectCount, setTradeReconnectCount] = useState(0);
  const [nowTs, setNowTs] = useState(Date.now());
  const syncAttemptsRef = useRef(new Set());
  const breakevenTriggeredRef = useRef(new Set());
  const bgSyncLocksRef = useRef(new Set());
  const bgSyncDoneRef = useRef(new Set());
  const candlesRequestSeqRef = useRef(0);
  const streamContextRef = useRef("");

  const signalsForTimeframe = useMemo(
    () => signals.filter((item) => item.timeframe === timeframe),
    [signals, timeframe]
  );
  const latestSignalForTimeframe = useMemo(() => signalsForTimeframe[0], [signalsForTimeframe]);
  const latestOrderForSymbol = useMemo(() => {
    if (!orders.length) return null;
    const symbolKey = (binanceSymbol || symbol || "").replace("-", "").toUpperCase();
    const bySymbol = orders.filter((order) => {
      const orderSymbol = (order.symbol || "").replace("-", "").toUpperCase();
      return orderSymbol === symbolKey;
    });
    if (!bySymbol.length) return null;
    return [...bySymbol].sort(
      (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
    )[0];
  }, [orders, binanceSymbol, symbol]);
  const latestActiveOrder = useMemo(() => {
    if (!orders.length) return null;
    const symbolKey = (binanceSymbol || symbol || "").replace("-", "").toUpperCase();
    return (
      orders.find((order) => {
        const orderSymbol = (order.symbol || "").replace("-", "").toUpperCase();
        if (orderSymbol !== symbolKey) return false;
        return !["cancelled", "filled", "closed"].includes((order.status || "").toLowerCase());
      }) || null
    );
  }, [orders, binanceSymbol, symbol]);
  const chartTradePlan = useMemo(() => {
    const fromSignal = latestSignalForTimeframe?.meta?.trade_plan ?? null;
    const sourceOrder = latestOrderForSymbol || {};
    if (!sourceOrder.id && !fromSignal) return null;
    const sourceSignal = fromSignal || {};
    const levels = Array.isArray(sourceOrder.take_levels)
      ? sourceOrder.take_levels.filter((v) => Number.isFinite(v))
      : Array.isArray(sourceSignal.take_levels)
        ? sourceSignal.take_levels.filter((v) => Number.isFinite(v))
        : [];
    const entry = Number.isFinite(sourceOrder.price) ? sourceOrder.price : sourceSignal.entry;
    const stopLoss = Number.isFinite(sourceOrder.stop_loss) ? sourceOrder.stop_loss : sourceSignal.stop_loss;
    const takeProfit = Number.isFinite(sourceOrder.take_profit) ? sourceOrder.take_profit : sourceSignal.take_profit;
    return {
      entry,
      stop_loss: stopLoss,
      take_profit: takeProfit,
      take_levels: levels,
      source: sourceOrder.id ? "order" : "signal",
    };
  }, [latestOrderForSymbol, latestSignalForTimeframe]);
  const latestSignalPlan = latestSignalForTimeframe?.meta?.trade_plan ?? null;
  const latestSignalEntry = Number.isFinite(latestSignalPlan?.entry)
    ? latestSignalPlan.entry
    : latestSignalForTimeframe?.entry_price ?? null;
  const latestSignalStop = Number.isFinite(latestSignalPlan?.stop_loss)
    ? latestSignalPlan.stop_loss
    : latestSignalForTimeframe?.stop_loss ?? null;
  const latestSignalTake = Number.isFinite(latestSignalPlan?.take_profit)
    ? latestSignalPlan.take_profit
    : latestSignalForTimeframe?.take_profit ?? null;
  const futuresPositionMap = useMemo(() => {
    const rows = accountSummary?.market === "futures" ? accountSummary.futures_positions || [] : [];
    return new Map(rows.map((position) => [(position.symbol || "").replace("-", "").toUpperCase(), position]));
  }, [accountSummary]);
  const activePosition = useMemo(() => {
    const symbolKey = (binanceSymbol || symbol || "").replace("-", "").toUpperCase();
    return futuresPositionMap.get(symbolKey) || null;
  }, [binanceSymbol, symbol, futuresPositionMap]);
  const activePositionRoi = useMemo(() => futuresPositionRoi(activePosition), [activePosition]);

  useEffect(() => {
    if (latestActiveOrder?.stop_loss) {
      setChartStopInput(String(latestActiveOrder.stop_loss));
    } else {
      setChartStopInput("");
    }
  }, [latestActiveOrder?.id, latestActiveOrder?.stop_loss]);

  useEffect(() => {
    if (latestActiveOrder?.take_profit) {
      setChartTakeInput(String(latestActiveOrder.take_profit));
    } else {
      setChartTakeInput("");
    }
  }, [latestActiveOrder?.id, latestActiveOrder?.take_profit]);
  useEffect(() => {
    refreshAutomationState();
    const timer = window.setInterval(() => {
      refreshAutomationState();
    }, 8000);
    return () => window.clearInterval(timer);
  }, []);
  useEffect(() => {
    if (!backtestRunning) return undefined;
    let active = true;
    const poll = async () => {
      try {
        const snapshot = await fetchBacktestStatus();
        if (!active) return;
        setBacktestProgress(snapshot);
        if (snapshot?.status === "running") {
          const done = Number(snapshot.processed_pairs ?? 0);
          const total = Number(snapshot.total_pairs ?? 0);
          const trades = Number(snapshot.matched_trades ?? 0);
          const current = snapshot.current_symbol ? ` · ${snapshot.current_symbol}` : "";
          setStatus(`Бэктест: ${done}/${total} пар, ${trades} сделок${current}`);
        }
      } catch {
        // keep polling silently
      }
    };
    poll();
    const timer = window.setInterval(poll, 1000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [backtestRunning]);
  const priceMap = useMemo(() => new Map(pairs.map((pair) => [pair.symbol, pair.last_price])), [pairs]);
  const currentPair = useMemo(() => {
    if (selectedPair?.symbol === binanceSymbol) {
      return selectedPair;
    }
    return pairs.find((pair) => pair.symbol === binanceSymbol) ?? selectedPair;
  }, [selectedPair, pairs, binanceSymbol]);
  const currentPrice = candles.length ? Number(candles[candles.length - 1]?.close) : currentPair?.last_price ?? null;
  const refreshAutomationState = async () => {
    try {
      const snapshot = await fetchAutomationState();
      setAutomationState(snapshot);
    } catch (error) {
      console.error("Failed to refresh automation state", error);
    }
  };

  const handleStrategyChange = (nextStrategy) => {
    setStrategy(nextStrategy);
    if (nextStrategy === "three_screens") {
      setTimeframe("15m");
      setH1Timeframe("15m");
      setTrendTimeframe("1h");
      setShowRsi(true);
    }
  };

  useEffect(() => {
    if (activeTab !== "trade" || !binanceSymbol) return undefined;
    let active = true;
    const loadOrderBook = async () => {
      try {
        setOrderBookLoading(true);
        const book = await fetchOrderBook(binanceSymbol, market, dataEnv, 50);
        if (!active) return;
        setOrderBook(book);
        setOrderBookError("");
      } catch (error) {
        if (!active) return;
        setOrderBookError(error?.message || "orderbook_unavailable");
      } finally {
        if (active) setOrderBookLoading(false);
      }
    };
    loadOrderBook();
    const timer = window.setInterval(loadOrderBook, 4500);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [activeTab, binanceSymbol, market, dataEnv]);

  const filteredPairs = useMemo(() => {
    return pairs
      .filter((pair) => {
        if (pairSearch) {
          const search = pairSearch.toUpperCase();
          const target = `${pair.symbol} ${pair.base_asset ?? ""} ${pair.quote_asset ?? ""}`.toUpperCase();
          if (!target.includes(search)) return false;
        }
        if (minVolatility > 0 && pair.volatility_score < minVolatility) return false;
        if (maxPrice > 0 && pair.last_price > maxPrice) return false;
        if (maxNotional > 0 && pair.min_notional && pair.min_notional > maxNotional) return false;
        return true;
      })
      .sort((a, b) => b.volatility_score - a.volatility_score);
  }, [pairs, pairSearch, minVolatility, maxPrice, maxNotional]);

  const stats = useMemo(() => {
    const total = signalsForTimeframe.length;
    const pnlValues = orders
      .map((order) => {
        if (["closed", "filled", "cancelled"].includes((order.status || "").toLowerCase())) {
          return Number.isFinite(order.realized_pnl) ? Number(order.realized_pnl) : null;
        }
        const position = futuresPositionMap.get((order.symbol || "").replace("-", "").toUpperCase());
        if (position) {
          return futuresPositionRoi(position);
        }
        const lastPrice = priceMap.get(order.symbol);
        if (!lastPrice || !order.price) return null;
        const side = order.side === "BUY" ? 1 : -1;
        return ((lastPrice - order.price) / order.price) * 100 * side;
      })
      .filter((value) => value !== null);

    const wins = pnlValues.filter((value) => value > 0).length;
    const losses = pnlValues.filter((value) => value < 0).length;
    const winRate = pnlValues.length ? Math.round((wins / pnlValues.length) * 100) : 0;
    const profit = pnlValues.filter((value) => value > 0).reduce((sum, value) => sum + value, 0);
    const loss = pnlValues.filter((value) => value < 0).reduce((sum, value) => sum + Math.abs(value), 0);
    const profitFactor = loss > 0 ? (profit / loss).toFixed(2) : profit > 0 ? "∞" : "0";
    const totalPnL = pnlValues.reduce((sum, value) => sum + value, 0).toFixed(2);

    return {
      totalSignals: total,
      winRate,
      profitFactor,
      totalPnL,
    };
  }, [signalsForTimeframe, orders, priceMap, futuresPositionMap]);

  const activeStats = backtestStats ?? stats;

  const tradeHistory = useMemo(
    () => buildTradeHistory(candles, signalsForTimeframe, tradeHistoryLimit),
    [candles, signalsForTimeframe, tradeHistoryLimit]
  );
  const orderTrades = useMemo(() => {
    return orders
      .map((order) => {
        const isClosed = ["closed", "filled", "cancelled"].includes((order.status || "").toLowerCase());
        const position = futuresPositionMap.get((order.symbol || "").replace("-", "").toUpperCase());
        const fallbackLast = Number(priceMap.get(order.symbol));
        const orderSymbol = (order.symbol || "").replace("-", "").toUpperCase();
        const selectedSymbol = (binanceSymbol || symbol || "").replace("-", "").toUpperCase();
        const current = orderSymbol === selectedSymbol && candles.length
          ? Number(candles[candles.length - 1].close)
          : fallbackLast;
        const entry = !isClosed && position ? Number(position.entry_price) : Number(order.price || current || 0);
        const exitPrice = isClosed
          ? Number(order.exit_price || order.price || entry)
          : position
            ? Number(position.mark_price || current || entry)
            : Number(current || entry);
        const side = (order.side || "").toUpperCase() === "SELL" ? "short" : "long";
        const sideMul = side === "long" ? 1 : -1;
        let pnl = 0;
        if (isClosed) {
          if (Number.isFinite(order.realized_pnl)) {
            pnl = Number(order.realized_pnl);
          } else if (Number(order.exit_price) > 0 && Number(order.price) > 0) {
            pnl = ((Number(order.exit_price) - Number(order.price)) / Number(order.price)) * 100 * sideMul;
          }
        } else if (position) {
          pnl = futuresPositionRoi(position) ?? 0;
        } else if (entry > 0) {
          pnl = ((exitPrice - entry) / entry) * 100 * sideMul;
        }
        return {
          id: `order-${order.id}`,
          symbol: order.symbol,
          timeframe: order.timeframe || timeframe,
          side,
          entry,
          entry_time: toEpochSeconds(order.created_at),
          exit_price: exitPrice,
          exit_time: isClosed ? toEpochSeconds(order.closed_at || order.created_at) : null,
          exit_reason: isClosed ? (order.status || "CLOSED").toUpperCase() : "OPEN",
          pnl,
          tp_hits: [],
          rationale: order.reject_reason || null,
          trade_plan: {
            stop_loss: order.stop_loss,
            take_profit: order.take_profit,
            take_levels: order.take_levels,
          },
        };
      });
  }, [orders, timeframe, candles, priceMap, futuresPositionMap, binanceSymbol, symbol]);

  const chartOrderTrades = useMemo(() => {
    const symbolKey = (binanceSymbol || symbol || "").replace("-", "").toUpperCase();
    return orderTrades.filter((trade) => (trade.symbol || "").replace("-", "").toUpperCase() === symbolKey);
  }, [orderTrades, binanceSymbol, symbol]);

  const displayedTrades = activeTab === "backtest" ? backtestTrades : orderTrades;
  const tradeHistorySource = activeTab === "backtest" ? "backtest" : "orders";
  const chartTrades = useMemo(() => {
    if (!displayedTrades.length) return [];
    const chartSource = activeTab === "backtest" ? displayedTrades : chartOrderTrades;
    const ordered = [...chartSource].sort((a, b) => a.entry_time - b.entry_time);
    const limit = Math.max(5, Number(tradeHistoryLimit) || 20);
    return ordered.slice(-limit);
  }, [displayedTrades, chartOrderTrades, activeTab, tradeHistoryLimit]);

  const chartLimit = useMemo(() => Math.max(chartBars, 200), [chartBars]);
  const indicatorLimit = useMemo(() => Math.min(Math.max(chartLimit, 240), 5000), [chartLimit]);
  const maxCandles = useMemo(() => chartLimit + 200, [chartLimit]);
  const pageSize = 1000;
  const maxCandlesTotal = useMemo(() => Math.max(maxCandles, 15000), [maxCandles]);
  const syncTimeframes = useMemo(() => {
    const merged = [timeframe, h1Timeframe, trendTimeframe].filter(Boolean);
    return [...new Set(merged)];
  }, [timeframe, h1Timeframe, trendTimeframe]);

  const syncTimeframesForSymbol = async (targetSymbol, options = {}) => {
    if (!targetSymbol) return { ok: 0, fail: 0 };
    const { silent = false, includeBackfill = false, doSync = true } = options;
    let ok = 0;
    let fail = 0;
    const localSymbol = symbol;
    const localMarket = market;
    const localDays = lookbackDays;
    const localDataEnv = dataEnv;
    if (doSync) {
      const queue = [...syncTimeframes];
      const workers = Array.from({ length: Math.min(2, queue.length) }, async () => {
        while (queue.length) {
          const tf = queue.shift();
          if (!tf) continue;
          try {
            await syncMarket(localSymbol, tf, localDays, localMarket, targetSymbol, localDataEnv);
            ok += 1;
          } catch {
            fail += 1;
          }
        }
      });
      await Promise.all(workers);
    }
    if (!silent && doSync) {
      if (ok > 0 && fail === 0) {
        setStatus(`Синхронизировано ТФ: ${syncTimeframes.join(", ")}`);
      } else if (ok > 0) {
        setStatus(`Частично синхронизировано (${ok}/${syncTimeframes.length})`);
      } else {
        setStatus("Ошибка синхронизации");
      }
    }
    if (ok > 0 && doSync) {
      setLastSyncAt(Date.now());
    }
    if (includeBackfill) {
      try {
        await backfillSignals({
          symbol: localSymbol,
          timeframe,
          strategy,
          lookback_days: localDays,
          stride: backfillStride,
          max_bars: backfillMaxBars,
        });
      } catch {
        // keep candles even if backfill failed
      }
    }
    return { ok, fail };
  };

  useEffect(() => {
    setBacktestStats(null);
    setBacktestTrades([]);
    setAnalysisDebug(null);
  }, [symbol, timeframe, market]);

  useEffect(() => {
    streamContextRef.current = `${symbol}|${timeframe}|${market}|${dataEnv}|${binanceSymbol ?? ""}`;
    candlesRequestSeqRef.current += 1;
    setCandles([]);
    setIndicatorData(null);
    setLastTickAt(null);
    setFeedSource("switching_pair");
  }, [symbol, timeframe, market, dataEnv, binanceSymbol]);

  useEffect(() => {
    let active = true;
    async function loadAccount() {
      try {
        const summary = await fetchAccountSummary(market, tradeEnv);
        if (active) setAccountSummary(summary);
      } catch (e) {
        if (active) {
          setAccountSummary({ status: "error", market, trade_env: tradeEnv, error: e?.message ?? "ошибка" });
        }
      }
    }
    async function loadTrades() {
      try {
        const trades = await fetchAccountTrades(market, tradeEnv, binanceSymbol, 50);
        if (active) setAccountTrades(trades?.trades ?? []);
      } catch (e) {
        if (active) {
          setAccountTrades([]);
        }
      }
    }
    loadAccount();
    loadTrades();
    const accountInterval = setInterval(loadAccount, 2000);
    const tradesInterval = setInterval(loadTrades, 10000);
    return () => {
      active = false;
      clearInterval(accountInterval);
      clearInterval(tradesInterval);
    };
  }, [market, tradeEnv, binanceSymbol]);

  useEffect(() => {
    let active = true;
    let retryTimer = null;
    const requestSeq = candlesRequestSeqRef.current;
    const isStale = () => !active || requestSeq !== candlesRequestSeqRef.current;

    async function load() {
      try {
        let data = await fetchCandles(symbol, timeframe, chartLimit);
        if (isStale()) return;
        // After service reboot binanceSymbol can be unresolved for a short time;
        // use symbol fallback so auto-sync still works.
        const syncSymbol =
          binanceSymbol || (symbol && !symbol.includes("-") ? symbol.toUpperCase() : null);
        const syncKey = `${symbol}:${timeframe}:${market}:${dataEnv}`;
        const shouldSync = syncSymbol && data.length < 20 && !syncAttemptsRef.current.has(syncKey);
        if (shouldSync) {
          syncAttemptsRef.current.add(syncKey);
          setStatus(data.length ? "Догружаю историю..." : "История загружается...");
          void (async () => {
            try {
              await syncMarket(symbol, timeframe, lookbackDays, market, syncSymbol, dataEnv);
              const fresh = await fetchCandles(symbol, timeframe, chartLimit);
              if (isStale()) return;
              if (fresh.length) {
                setCandles(fresh);
                setLastSyncAt(Date.now());
                setStatus("Готово");
              }
            } catch {
              if (active && !data.length) setStatus("История отсутствует");
            }
          })();
        }
        if (isStale()) return;
        setCandles(data);
        const [signalData, indicators] = await Promise.all([
          fetchSignals(symbol, 200).catch(() => []),
          data.length ? fetchIndicators(symbol, timeframe, indicatorLimit).catch(() => null) : Promise.resolve(null),
        ]);
        if (isStale()) return;
        setSignals(signalData);
        setIndicatorData(indicators);
        if (data.length === 0) {
          if (isStale()) return;
          if (!shouldSync) setStatus("История отсутствует");
        } else {
          if (isStale()) return;
          if (!shouldSync) setStatus("Готово");
        }
      } catch (error) {
        if (isStale()) return;
        setStatus("Ошибка загрузки, повторяю...");
        retryTimer = setTimeout(async () => {
          if (isStale()) return;
          try {
            const retry = await fetchCandles(symbol, timeframe, chartLimit);
            if (isStale()) return;
            if (retry.length) {
              setCandles(retry);
              setStatus("Готово");
            }
          } catch {
            // keep previous chart data on repeated failure
          }
        }, 1200);
      }
    }

    load();
    return () => {
      active = false;
      if (retryTimer) clearTimeout(retryTimer);
    };
  }, [symbol, timeframe, market, binanceSymbol, lookbackDays, dataEnv, chartLimit, indicatorLimit]);

  useEffect(() => {
    // Keep current stream symbol while switching market to avoid race-condition
    // where an async market-change cleanup overwrites a freshly selected pair.
    setSelectedPair((prev) => {
      if (!prev) return null;
      return prev.market === market ? prev : null;
    });
  }, [market]);

  useEffect(() => {
    setLastTickAt(null);
    setFeedSource("switching_env");
    setWsConnected(false);
    setTradeWsConnected(false);
  }, [dataEnv]);

  useEffect(() => {
    async function resolve() {
      if (selectedPair?.symbol && selectedPair.market === market) {
        setBinanceSymbol(selectedPair.symbol);
        return;
      }
      if (symbol && !symbol.includes("-")) {
        setBinanceSymbol(symbol);
        return;
      }
      try {
        const response = await resolveSymbol(symbol, market);
        if (response.status === "ok") {
          setBinanceSymbol(response.symbol);
        } else {
          setBinanceSymbol(null);
        }
      } catch (error) {
        setBinanceSymbol(null);
      }
    }

    resolve();
  }, [symbol, market, selectedPair]);

  useEffect(() => {
    const syncSymbol = binanceSymbol || (symbol && !symbol.includes("-") ? symbol.toUpperCase() : null);
    if (!syncSymbol) return undefined;

    const baseKey = `${syncSymbol}:${market}:${dataEnv}:${lookbackDays}`;
    const lockKey = `${baseKey}:${syncTimeframes.join(",")}`;
    const initialTimer = setTimeout(() => {
      if (!bgSyncDoneRef.current.has(lockKey) && !bgSyncLocksRef.current.has(lockKey)) {
        bgSyncLocksRef.current.add(lockKey);
        void (async () => {
          try {
            await syncTimeframesForSymbol(syncSymbol, { silent: true, includeBackfill: false });
            bgSyncDoneRef.current.add(lockKey);
          } finally {
            bgSyncLocksRef.current.delete(lockKey);
          }
        })();
      }
    }, 1200);

    const interval = setInterval(() => {
      const tickLock = `${lockKey}:tick`;
      if (bgSyncLocksRef.current.has(tickLock)) return;
      bgSyncLocksRef.current.add(tickLock);
      setAutoSyncRunning(true);
      void (async () => {
        try {
          await syncTimeframesForSymbol(syncSymbol, { silent: true, includeBackfill: false });
        } finally {
          bgSyncLocksRef.current.delete(tickLock);
          setAutoSyncRunning(false);
        }
      })();
    }, 300000);

    return () => {
      clearTimeout(initialTimer);
      clearInterval(interval);
    };
  }, [binanceSymbol, symbol, market, dataEnv, lookbackDays, syncTimeframes]);

  useEffect(() => {
    let active = true;
    async function loadPairs() {
      setPairsLoading(true);
      try {
        const quote = quoteAsset === "ALL" ? null : quoteAsset;
        const data = await fetchPairs(market, quote, undefined, dataEnv);
        if (active) {
          setPairs(data);
        }
      } catch (error) {
        if (active) {
          setPairs([]);
        }
      } finally {
        if (active) {
          setPairsLoading(false);
        }
      }
    }

    loadPairs();
    const interval = setInterval(loadPairs, 30000);
    return () => {
      active = false;
      clearInterval(interval);
    };
  }, [market, quoteAsset, dataEnv]);

  useEffect(() => {
    if (!pairs.length) return;
    const current = (binanceSymbol || symbol || "").toUpperCase();
    const exists = pairs.some((item) => (item.symbol || "").toUpperCase() === current);
    if (exists) return;
    const fallback = pairs[0];
    if (!fallback?.symbol) return;
    setSelectedPair({ ...fallback, market });
    setSymbol(fallback.symbol);
    setBinanceSymbol(fallback.symbol);
    setStatus(`Переключена пара на ${fallback.symbol} для ${market.toUpperCase()}`);
  }, [pairs, binanceSymbol, symbol, market]);

  useEffect(() => {
    async function loadOrders() {
      try {
        const data = await fetchOrders(100);
        setOrders(data);
      } catch (error) {
        setOrders([]);
      }
    }

    loadOrders();
  }, []);

  useEffect(() => {
    if (!autoBreakeven || orders.length === 0) return;
    const priceBySymbol = new Map(priceMap);
    if (candles.length && binanceSymbol) {
      priceBySymbol.set(binanceSymbol, candles[candles.length - 1].close);
    }

    orders.forEach((order) => {
      if (!order.auto_breakeven || order.breakeven_moved) return;
      const tp1 = Array.isArray(order.take_levels) ? order.take_levels[0] : order.take_profit;
      const trigger = Number.isFinite(tp1) ? tp1 : order.breakeven_at;
      if (!trigger || !order.price) return;
      if (breakevenTriggeredRef.current.has(order.id)) return;
      const lastPrice = priceBySymbol.get(order.symbol);
      if (!lastPrice) return;
      const shouldMove =
        (order.side === "BUY" && lastPrice >= trigger) ||
        (order.side === "SELL" && lastPrice <= trigger);
      if (!shouldMove) return;
      breakevenTriggeredRef.current.add(order.id);
      void (async () => {
        try {
          if (Number.isFinite(tp1)) {
            await moveStopToPrice(order.id, tp1);
          } else {
            await moveStopToBreakeven(order.id);
          }
          const updatedOrders = await fetchOrders(100);
          setOrders(updatedOrders);
        } catch (error) {
          breakevenTriggeredRef.current.delete(order.id);
        }
      })();
    });
  }, [orders, autoBreakeven, priceMap, candles, binanceSymbol]);

  useEffect(() => {
    const timer = setInterval(() => setNowTs(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    if (!binanceSymbol) return;

    const isDev = window.location.port === "5173";
    const defaultWsBase = isDev ? "ws://localhost:8000" : window.location.origin.replace("http", "ws");
    const wsBase = import.meta.env.VITE_WS_BASE || defaultWsBase;
    const wsUrl = `${wsBase}/api/stream?symbol=${encodeURIComponent(
      symbol
    )}&timeframe=${timeframe}&market=${market}&binance_symbol=${encodeURIComponent(
      binanceSymbol
    )}&data_env=${dataEnv}`;
    const contextKey = streamContextRef.current;
    let isCleanup = false;
    let reconnectTimer = null;
    const socket = new WebSocket(wsUrl);
    socket.onopen = () => {
      if (isCleanup) return;
      setWsConnected(true);
    };

    socket.onmessage = (event) => {
      if (isCleanup || streamContextRef.current !== contextKey) return;
      const payload = JSON.parse(event.data);
      if (payload.type === "error") {
        setStatus(`Стрим: ${payload.message}`);
        return;
      }
      if (payload.type !== "kline") return;

      const candle = payload.data;
      // Use kline stream only for candle finalization to avoid intrabar jitter.
      if (candle.is_final) {
        setCandles((prev) => {
          if (!prev.length) return [candle];
          const last = prev[prev.length - 1];
          if (last.open_time === candle.open_time) {
            const updated = [...prev];
            updated[updated.length - 1] = {
              ...last,
              open: Number(candle.open),
              high: Number(candle.high),
              low: Number(candle.low),
              close: Number(candle.close),
              volume: Number(candle.volume ?? last.volume ?? 0),
              is_final: true,
            };
            return updated;
          }
          const next = [...prev, candle];
          return next.length > maxCandlesTotal ? next.slice(next.length - maxCandlesTotal) : next;
        });
        setLastTickAt(Date.now());
        setLiveTickSeq((v) => v + 1);
        setFeedSource("WS kline final");
        void (async () => {
          try {
            const indicators = await fetchIndicators(symbol, timeframe, indicatorLimit);
            if (isCleanup || streamContextRef.current !== contextKey) return;
            setIndicatorData(indicators);
          } catch (indicatorError) {
            // keep last indicators on failure
          }
        })();
      }
    };

    socket.onerror = () => {
      if (isCleanup) return;
      setWsConnected(false);
      setStatus("Ошибка стрима");
    };

    socket.onclose = (event) => {
      if (isCleanup) return;
      setWsConnected(false);
      setStatus(`WS закрыт (${event.code}), переподключаю...`);
      reconnectTimer = setTimeout(() => setWsRetryTick((v) => v + 1), 2000);
    };

    return () => {
      isCleanup = true;
      setWsConnected(false);
      if (reconnectTimer) clearTimeout(reconnectTimer);
      // Avoid closing CONNECTING sockets to prevent "closed before established" noise.
      if (socket.readyState === WebSocket.OPEN) {
        socket.close(1000, "switch_context");
      }
    };
  }, [binanceSymbol, symbol, timeframe, market, dataEnv, maxCandlesTotal, indicatorLimit, wsRetryTick]);

  useEffect(() => {
    if (!binanceSymbol) return undefined;
    const isDev = window.location.port === "5173";
    const defaultWsBase = isDev ? "ws://localhost:8000" : window.location.origin.replace("http", "ws");
    const wsBase = import.meta.env.VITE_WS_BASE || defaultWsBase;
    const wsUrl = `${wsBase}/api/stream/trades?symbol=${encodeURIComponent(
      symbol
    )}&market=${market}&binance_symbol=${encodeURIComponent(binanceSymbol)}&data_env=${dataEnv}`;
    const contextKey = streamContextRef.current;
    const intervalMs = timeframeToMs(timeframe) ?? 60_000;
    let closed = false;
    let reconnectTimer = null;
    let lastTradeTs = Date.now();
    let socket = null;

    const applyPrice = (price, tradeTimeMs) => {
      if (streamContextRef.current !== contextKey) return;
      if (!Number.isFinite(price) || price <= 0) return;
      const openTimeMs = Math.floor(tradeTimeMs / intervalMs) * intervalMs;
      const openTimeIso = new Date(openTimeMs).toISOString();
      setCandles((prev) => {
        if (!prev.length) {
          return [
            {
              open_time: openTimeIso,
              open: price,
              high: price,
              low: price,
              close: price,
              volume: 0,
            },
          ];
        }
        const next = [...prev];
        const last = next[next.length - 1];
        if (last.open_time === openTimeIso) {
          const nextClose = Number(price);
          const nextHigh = Math.max(Number(last.high || nextClose), nextClose);
          const nextLow = Math.min(Number(last.low || nextClose), nextClose);
          if (
            Number(last.close) === nextClose &&
            Number(last.high) === nextHigh &&
            Number(last.low) === nextLow
          ) {
            return prev;
          }
          next[next.length - 1] = { ...last, close: nextClose, high: nextHigh, low: nextLow };
          return next;
        }
        next.push({
          open_time: openTimeIso,
          open: Number(last.close || price),
          high: Math.max(Number(last.close || price), price),
          low: Math.min(Number(last.close || price), price),
          close: price,
          volume: 0,
        });
        return next.slice(-maxCandlesTotal);
      });
      setLastTickAt(Date.now());
      setLiveTickSeq((v) => v + 1);
      setFeedSource("WS aggTrade");
      lastTradeTs = Date.now();
    };

    const clearTimers = () => {
      if (reconnectTimer) {
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
      }
    };

    const connect = () => {
      if (closed) return;
      socket = new WebSocket(wsUrl);
      socket.onopen = () => {
        if (closed) return;
        setTradeWsConnected(true);
        lastTradeTs = Date.now();
        setFeedSource("WS aggTrade");
      };
      socket.onmessage = (event) => {
        if (closed || streamContextRef.current !== contextKey) return;
        try {
          const payload = JSON.parse(event.data);
          if (payload?.type !== "trade") return;
          const price = Number(payload?.data?.price);
          const tradeTime = new Date(payload?.data?.time || Date.now()).getTime();
          applyPrice(price, tradeTime);
        } catch {
          // ignore malformed payloads
        }
      };
      socket.onclose = () => {
        if (closed) return;
        clearTimers();
        setTradeWsConnected(false);
        setTradeReconnectCount((v) => v + 1);
        reconnectTimer = setTimeout(connect, 1200);
      };
      socket.onerror = () => {
        setTradeWsConnected(false);
        try {
          socket?.close();
        } catch {
          // ignore close errors
        }
      };
    };

    connect();
    return () => {
      closed = true;
      setTradeWsConnected(false);
      clearTimers();
      try {
        socket?.close();
      } catch {
        // ignore close errors
      }
    };
  }, [binanceSymbol, timeframe, market, maxCandlesTotal, symbol, dataEnv]);

  useEffect(() => {
    let active = true;
    const contextKey = streamContextRef.current;
    const intervalMs = timeframeToMs(timeframe) ?? 60_000;
    const interval = setInterval(async () => {
      if (!active || streamContextRef.current !== contextKey) return;
      const staleMs = lastTickAt ? Date.now() - lastTickAt : Number.POSITIVE_INFINITY;
      const wsHealthy = wsConnected && tradeWsConnected && staleMs < 2_500;
      if (wsHealthy) return;
      try {
        const data = await fetchCandles(symbol, timeframe, 3);
        if (!active || streamContextRef.current !== contextKey) return;
        if (!data.length) return;
        setCandles((prev) => {
          if (!prev.length) return data;
          const existing = new Set(prev.map((c) => c.open_time));
          const merged = [...prev, ...data.filter((c) => !existing.has(c.open_time))];
          return merged.slice(-maxCandlesTotal);
        });
        setLastTickAt(Date.now());
        setLiveTickSeq((v) => v + 1);
        setFeedSource("REST fallback");
      } catch {
        // keep retrying silently
      }
      try {
        const list = await fetchPairs(market, undefined, undefined, dataEnv);
        if (!active || streamContextRef.current !== contextKey) return;
        const symbolKey = (binanceSymbol || symbol || "").replace("-", "").toUpperCase();
        const pair = list.find((item) => (item.symbol || "").replace("-", "").toUpperCase() === symbolKey);
        const lastPrice = Number(pair?.last_price);
        if (!Number.isFinite(lastPrice) || lastPrice <= 0) return;
        const now = Date.now();
        const openTimeMs = Math.floor(now / intervalMs) * intervalMs;
        const openTimeIso = new Date(openTimeMs).toISOString();
        setCandles((prev) => {
          if (!prev.length) {
            return [
              {
                open_time: openTimeIso,
                open: lastPrice,
                high: lastPrice,
                low: lastPrice,
                close: lastPrice,
                volume: 0,
              },
            ];
          }
          const next = [...prev];
          const last = next[next.length - 1];
          if (last.open_time === openTimeIso) {
            next[next.length - 1] = {
              ...last,
              high: Math.max(Number(last.high || lastPrice), lastPrice),
              low: Math.min(Number(last.low || lastPrice), lastPrice),
              close: lastPrice,
            };
            return next;
          }
          next.push({
            open_time: openTimeIso,
            open: Number(last.close || lastPrice),
            high: Math.max(Number(last.close || lastPrice), lastPrice),
            low: Math.min(Number(last.close || lastPrice), lastPrice),
            close: lastPrice,
            volume: 0,
          });
          return next.slice(-maxCandlesTotal);
        });
        setLastTickAt(Date.now());
      } catch {
        // keep retrying silently
      }
    }, 1000);
    return () => {
      active = false;
      clearInterval(interval);
    };
  }, [wsConnected, tradeWsConnected, lastTickAt, symbol, timeframe, maxCandlesTotal, market, dataEnv, binanceSymbol]);

  const handleLoadMoreCandles = async (beforeIso) => {
    try {
      const more = await fetchCandles(symbol, timeframe, pageSize, beforeIso);
      if (!more.length) return;
      setCandles((prev) => {
        if (!prev.length) return more;
        const existing = new Set(prev.map((c) => c.open_time));
        const merged = [...more.filter((c) => !existing.has(c.open_time)), ...prev];
        if (merged.length > maxCandlesTotal) {
          return merged.slice(merged.length - maxCandlesTotal);
        }
        return merged;
      });
    } catch (e) {
      // ignore pagination errors
    }
  };

  const handleSync = async () => {
    const syncSymbol = binanceSymbol || (symbol && !symbol.includes("-") ? symbol.toUpperCase() : null);
    if (!syncSymbol) {
      setStatus("Сначала выбери торговую пару Binance");
      return;
    }
    setStatus("Синхронизация истории...");
    try {
      await syncTimeframesForSymbol(syncSymbol, { silent: true, includeBackfill: false });
      const data = await fetchCandles(symbol, timeframe, chartLimit);
      setCandles(data);
      setStatus(data.length ? "История синхронизирована" : "История отсутствует");
      if (data.length) {
        try {
          setStatus("Заполняю сигналы по истории...");
          await syncTimeframesForSymbol(syncSymbol, {
            silent: true,
            includeBackfill: true,
            doSync: false,
          });
          const signalData = await fetchSignals(symbol, 200);
          setSignals(signalData);
          try {
            const indicators = await fetchIndicators(symbol, timeframe, indicatorLimit);
            setIndicatorData(indicators);
          } catch (indicatorError) {
            setIndicatorData(null);
          }
          setStatus("История синхронизирована");
        } catch (backfillError) {
          setStatus("История синхронизирована (ошибка заполнения сигналов)");
        }
      }
    } catch (error) {
      setStatus("Ошибка синхронизации");
    }
  };

  const handleAnalyze = async () => {
    if (autoQuantity && quoteAmount <= 0) {
      setStatus("Нужна сумма (Quote Amount)");
      return;
    }
    setStatus("Запуск анализа...");
    try {
      setAnalysisDebug(null);
      const response = await runAnalysis(
        symbol,
        timeframe,
        lookbackDays,
        market,
        mode === "auto",
        quantity,
        autoQuantity ? quoteAmount : null,
        autoQuantity,
        tradeEnv,
        attachOrders,
        autoBreakeven,
        {
          h1_timeframe: h1Timeframe,
          trend_timeframe: trendTimeframe,
          strategy,
          min_confidence: minConfidence,
          min_confirmations: minConfirmations,
          require_pattern: requirePattern,
          require_divergence: requireDivergence,
          require_candle: requireCandle,
          require_volume_confirm: requireVolumeConfirm,
          require_trend_filter: requireTrendFilter,
          confluence_tolerance: Number(confluenceTolerance) || 0,
          leverage: market === "futures" ? leverage : null,
        }
      );
      if (response.signal) {
        setSignals((prev) => {
          if (prev.length && prev[0].id === response.signal.id) return prev;
          return [response.signal, ...prev];
        });
      }
      const signalData = await fetchSignals(symbol, 200);
      setSignals(signalData);
      const updatedOrders = await fetchOrders(100);
      setOrders(updatedOrders);
      if (candles.length) {
        try {
          const indicators = await fetchIndicators(symbol, timeframe, indicatorLimit);
          setIndicatorData(indicators);
        } catch (indicatorError) {
          // ignore indicator refresh
        }
      }
      if (response.status === "order_submitted") {
        setStatus("Ордер отправлен");
      } else if (response.status === "order_stored") {
        setStatus("Ордер сохранен (нет ключей биржи)");
      } else if (response.status === "spot_short_not_supported") {
        setStatus("Шорт на споте не поддерживается");
      } else if (response.status === "order_sizing_error") {
        setStatus(`Ошибка расчета количества: ${humanizeApiError(response.error ?? "unknown")}`);
      } else if (response.status === "symbol_not_mapped") {
        setStatus("Нет маппинга символа");
      } else if (response.status === "no_signal") {
        setStatus("Сигнала нет");
        try {
          const explained = await explainAnalysis({
            symbol,
            timeframe,
            strategy,
            lookback_days: lookbackDays,
            market,
            data_env: dataEnv,
            min_confidence: minConfidence,
            min_confirmations: minConfirmations,
            require_pattern: requirePattern,
            require_divergence: requireDivergence,
            require_candle: requireCandle,
            require_volume_confirm: requireVolumeConfirm,
            require_trend_filter: requireTrendFilter,
            confluence_tolerance: Number(confluenceTolerance) || 0,
          });
          const debug = explained.debug ?? null;
          setAnalysisDebug(debug);
          const reasons = Array.isArray(debug?.reasons) ? debug.reasons : [];
          if (reasons.length) {
            setStatus(`Сигнала нет: ${humanizeNoSignalReason(reasons[0])}`);
          }
        } catch (e) {
          setAnalysisDebug({ reasons: ["explain_failed"] });
          setStatus("Сигнала нет: Не удалось получить объяснение");
        }
      } else {
        setStatus("Сигнал готов");
      }
    } catch (error) {
      setStatus("Ошибка анализа");
    }
  };

  const handleBacktest = async () => {
    setBacktestRunning(true);
    setBacktestProgress({
      status: "running",
      mode: backtestMode === "market" ? "market_wide" : "single_pair",
      selected_symbol: backtestMode === "single" ? symbol : null,
      processed_pairs: 0,
      total_pairs: backtestMode === "market" ? scanMaxPairs : 1,
      matched_trades: 0,
      current_symbol: null,
    });
    setStatus("Запуск бэктеста...");
    try {
      const response = await runBacktest({
        symbol,
        market_wide: backtestMode === "market",
        quote: quoteAsset === "ALL" ? "" : quoteAsset,
        max_pairs: scanMaxPairs,
        timeframe,
        strategy,
        lookback_days: lookbackDays,
        max_bars: backfillMaxBars,
        stride: backfillStride,
        market,
        data_env: dataEnv,
        auto_sync: false,
        h1_timeframe: h1Timeframe,
        trend_timeframe: trendTimeframe,
        min_confidence: minConfidence,
        min_confirmations: minConfirmations,
        require_pattern: requirePattern,
        require_divergence: requireDivergence,
        require_candle: requireCandle,
        require_volume_confirm: requireVolumeConfirm,
        require_trend_filter: requireTrendFilter,
        confluence_tolerance: Number(confluenceTolerance) || 0,
      });
      setBacktestStats(response.stats ?? null);
      setBacktestTrades(response.trades ?? []);
      setBacktestMeta({
        mode: response.mode ?? (backtestMode === "market" ? "market_wide" : "single_pair"),
        selectedSymbol: response.selected_symbol ?? symbol,
        processedPairs: Number(response.processed_pairs ?? 0),
        universePairs: Number(response.universe_pairs ?? 0),
      });
      setBacktestProgress({
        status: "completed",
        mode: response.mode ?? (backtestMode === "market" ? "market_wide" : "single_pair"),
        selected_symbol: response.selected_symbol ?? symbol,
        processed_pairs: Number(response.processed_pairs ?? 0),
        total_pairs: Number(response.processed_pairs ?? 0),
        matched_trades: Number(response.stats?.total_trades ?? 0),
        current_symbol: null,
      });
      const totalTrades = response.stats?.total_trades ?? 0;
      setStatus(
        `Бэктест готов: ${totalTrades} сделок, ${Number(response.processed_pairs ?? 0)} пар`
      );
    } catch (error) {
      setBacktestProgress((prev) => ({
        ...(prev || {}),
        status: "error",
        last_error: error?.message ?? "unknown",
      }));
      setStatus("Ошибка бэктеста");
    } finally {
      setBacktestRunning(false);
    }
  };

  const handlePlaceOrder = async () => {
    setConfirmOrderOpen(false);
    if (!latestSignalForTimeframe || !binanceSymbol) return;
    if (market === "spot" && latestSignalForTimeframe.signal_type === "short") {
      setStatus("Шорт на споте не поддерживается");
      return;
    }
    if (autoQuantity && quoteAmount <= 0) {
      setStatus("Нужна сумма (Quote Amount)");
      return;
    }
    setStatus("Отправка ордера...");
    try {
      const lastPrice = candles.length ? candles[candles.length - 1].close : null;
      const placed = await placeOrder({
        exchange: "binance",
        market,
        symbol: binanceSymbol,
        side: latestSignalForTimeframe.signal_type === "long" ? "BUY" : "SELL",
        order_type: "MARKET",
        quantity,
        leverage: market === "futures" ? leverage : null,
        trade_env: tradeEnv,
        quote_amount: autoQuantity ? quoteAmount : null,
        auto_quantity: autoQuantity,
        timeframe,
        signal_id: latestSignalForTimeframe.id,
        price: lastPrice,
        stop_loss:
          latestSignalForTimeframe.meta?.trade_plan?.stop_loss ?? latestSignalForTimeframe.stop_loss,
        take_profit:
          latestSignalForTimeframe.meta?.trade_plan?.take_profit ?? latestSignalForTimeframe.take_profit,
        take_levels: latestSignalForTimeframe.meta?.trade_plan?.take_levels ?? null,
        breakeven_at: latestSignalForTimeframe.meta?.trade_plan?.breakeven_at ?? null,
        auto_breakeven: autoBreakeven,
        attach_orders: attachOrders,
      });
      const updatedOrders = await fetchOrders(100);
      setOrders(updatedOrders);
      await refreshAutomationState();
      if (placed?.status === "rejected") {
        setStatus(`Ордер отклонен: ${placed.reject_reason || "причина не указана"}`);
      } else if (placed?.status === "exit_failed") {
        setStatus(`Вход открыт, но SL/TP не выставились: ${placed.reject_reason || "причина не указана"}`);
      } else if (placed?.status === "stored") {
        setStatus("Симуляция: ордер сохранен локально (ключи/доступ недоступны)");
      } else {
        setStatus("Ордер отправлен");
      }
    } catch (error) {
      const code = error?.message ?? "unknown";
      let hint = "";
      if ((code === "min_qty" || code === "min_notional") && currentPair) {
        const price =
          (candles.length ? Number(candles[candles.length - 1].close) : null) ??
          (Number.isFinite(currentPair.last_price) ? Number(currentPair.last_price) : null);
        const minQty = Number(currentPair.min_qty ?? 0);
        const step = Number(currentPair.step_size ?? 0);
        const minNotional = Number(currentPair.min_notional ?? 0);
        const quote = currentPair.quote_asset || "USDT";
        if (price && price > 0) {
          const byQty = minQty > 0 ? minQty * price : 0;
          const required = Math.max(byQty, minNotional);
          if (required > 0) {
            const requiredInput = market === "futures" && leverage > 0 ? required / leverage : required;
            hint = ` Минимум для ${currentPair.symbol}: примерно ${requiredInput.toFixed(2)} ${quote} ${
              market === "futures" ? "маржи" : "суммы"
            } (minQty=${minQty}, шаг=${step}).`;
          }
        }
      }
      setStatus(`Ошибка ордера: ${humanizeApiError(code)}${hint}`);
    }
  };

  const handleOpenConfirmOrder = () => {
    if (!latestSignalForTimeframe || !binanceSymbol) return;
    setConfirmOrderOpen(true);
  };

  const handleSelectPair = async (pair) => {
    setSelectedPair({ ...pair, market });
    setSymbol(pair.symbol);
    setBinanceSymbol(pair.symbol);
  };

  const handleScan = async () => {
    setScanRunning(true);
    setStatus("Сканирую рынок...");
    try {
      const response = await scanMarket({
        symbol,
        market_wide: scanMode === "market",
        market,
        timeframe,
        strategy,
        lookback_days: lookbackDays,
        quote: quoteAsset === "ALL" ? "" : quoteAsset,
        data_env: dataEnv,
        h1_timeframe: h1Timeframe,
        trend_timeframe: trendTimeframe,
        min_volatility: minVolatility,
        max_pairs: scanMaxPairs,
        limit: scanLimit,
        auto_sync: scanAutoSync,
        store_signals: true,
        only_new_signals_minutes: onlyNewSignalsMinutes,
        min_confidence: minConfidence,
        min_confirmations: minConfirmations,
        require_pattern: requirePattern,
        require_divergence: requireDivergence,
        require_candle: requireCandle,
        require_volume_confirm: requireVolumeConfirm,
        require_trend_filter: requireTrendFilter,
        confluence_tolerance: Number(confluenceTolerance) || 0,
      });
      setScanResults(response.signals ?? []);
      setScanMeta({
        mode: response.mode ?? (scanMode === "market" ? "market_wide" : "single_pair"),
        selectedSymbol: response.selected_symbol ?? symbol,
        processedPairs: Number(response.processed_pairs ?? 0),
        universePairs: Number(response.universe_pairs ?? 0),
      });
      setScanDiagnostics(response.diagnostics ?? null);
      const count = Number(response.new_signals_count || 0);
      if (count > 0 && Array.isArray(response.signals) && response.signals.length > 0) {
        setNewSignalModal({ open: true, first: response.signals[0], count });
      }
      setStatus(
        `Скан готов: сигналов ${response.scanned}, новых ${count}, пар ${Number(response.processed_pairs ?? 0)}`
      );
    } catch (error) {
      const message = error?.message ? String(error.message) : "unknown";
      setStatus(`Ошибка сканирования: ${message}`);
      setScanResults([]);
      setScanMeta(null);
      setScanDiagnostics(null);
    } finally {
      setScanRunning(false);
    }
  };

  const handleSelectScanResult = async (item) => {
    const nextSymbol = item?.binance_symbol ?? item?.symbol;
    if (!nextSymbol) return;
    setSymbol(nextSymbol);
    if (item.timeframe && item.timeframe !== timeframe) {
      setTimeframe(item.timeframe);
    }
    setSelectedPair({ symbol: nextSymbol, market });
    setBinanceSymbol(nextSymbol);
  };

  const handleCloseOrder = async (order) => {
    if (!order?.id) return;
    setStatus("Закрываю позицию...");
    try {
      await closeOrderPosition(order.id);
      const updatedOrders = await fetchOrders(100);
      setOrders(updatedOrders);
      await refreshAutomationState();
      setStatus("Позиция закрыта");
    } catch (error) {
      setStatus(`Ошибка закрытия: ${error?.message ?? "unknown"}`);
    }
  };

  const handleMoveStopToBreakeven = async (order) => {
    if (!order?.id) return;
    setStatus("Переношу SL в безубыток...");
    try {
      await moveStopToBreakeven(order.id);
      const updatedOrders = await fetchOrders(100);
      setOrders(updatedOrders);
      await refreshAutomationState();
      setStatus("SL перенесен в безубыток");
    } catch (error) {
      setStatus(`Ошибка BE: ${humanizeApiError(error?.message ?? "unknown")}`);
    }
  };

  const handleMoveStopToPrice = async (order, stopPrice) => {
    if (!order?.id || !Number.isFinite(stopPrice) || stopPrice <= 0) return;
    setStatus("Обновляю SL...");
    try {
      await moveStopToPrice(order.id, stopPrice);
      const updatedOrders = await fetchOrders(100);
      setOrders(updatedOrders);
      await refreshAutomationState();
      setStatus(`SL обновлен: ${stopPrice}`);
    } catch (error) {
      setStatus(`Ошибка SL: ${humanizeApiError(error?.message ?? "unknown")}`);
    }
  };

  const handleMoveTakeToPrice = async (order, takePrice) => {
    if (!order?.id || !Number.isFinite(takePrice) || takePrice <= 0) return;
    setStatus("Обновляю TP...");
    try {
      await moveTakeToPrice(order.id, takePrice);
      const updatedOrders = await fetchOrders(100);
      setOrders(updatedOrders);
      await refreshAutomationState();
      setStatus(`TP обновлен: ${takePrice}`);
    } catch (error) {
      setStatus(`Ошибка TP: ${humanizeApiError(error?.message ?? "unknown")}`);
    }
  };

  const handleNudgeChartStop = (direction) => {
    const basePrice = Number(latestActiveOrder?.stop_loss || latestActiveOrder?.price || 0);
    const currentValue = Number(chartStopInput || basePrice);
    if (!Number.isFinite(currentValue) || currentValue <= 0) return;
    const next = currentValue + resolvePriceStep(basePrice || currentValue) * direction;
    if (next <= 0) return;
    setChartStopInput(String(next));
  };

  const handleNudgeChartTake = (direction) => {
    const basePrice = Number(latestActiveOrder?.take_profit || latestActiveOrder?.price || 0);
    const currentValue = Number(chartTakeInput || basePrice);
    if (!Number.isFinite(currentValue) || currentValue <= 0) return;
    const next = currentValue + resolvePriceStep(basePrice || currentValue) * direction;
    if (next <= 0) return;
    setChartTakeInput(String(next));
  };

  const handleRequestStopDragConfirm = (order, nextStop) => {
    if (!order?.id || !Number.isFinite(nextStop) || nextStop <= 0) return;
    setStopDragConfirmModal({
      open: true,
      order,
      nextStop,
    });
  };

  const handleSyncWorkspaceToAutomation = async () => {
    setAutomationLoading(true);
    try {
      const snapshot = await updateAutomationConfig({
        symbol: binanceSymbol || symbol,
        scan_market_wide: true,
        quote: quoteAsset === "ALL" ? "" : quoteAsset,
        max_pairs: scanMaxPairs,
        timeframe,
        market,
        data_env: dataEnv,
        trade_env: tradeEnv,
        lookback_days: lookbackDays,
        quantity,
        quote_amount: quoteAmount,
        auto_quantity: autoQuantity,
        attach_orders: attachOrders,
        auto_breakeven: autoBreakeven,
        leverage: market === "futures" ? leverage : null,
        min_confidence: minConfidence,
        min_confirmations: minConfirmations,
        require_pattern: requirePattern,
        require_divergence: requireDivergence,
        require_candle: requireCandle,
        require_volume_confirm: requireVolumeConfirm,
        require_trend_filter: requireTrendFilter,
        confluence_tolerance: Number(confluenceTolerance) || 0,
        h1_timeframe: h1Timeframe,
        trend_timeframe: trendTimeframe,
        strategy,
        mode,
      });
      setAutomationState(snapshot);
      setStatus("Automation center обновлен из текущего workspace");
    } catch (error) {
      setStatus(`Ошибка automation sync: ${error?.message ?? "unknown"}`);
    } finally {
      setAutomationLoading(false);
    }
  };

  const runAutomationAction = async (action, successStatus, failurePrefix = "Ошибка automation") => {
    setAutomationLoading(true);
    try {
      const snapshot = await action();
      setAutomationState(snapshot);
      if (successStatus) {
        setStatus(successStatus);
      }
    } catch (error) {
      setStatus(`${failurePrefix}: ${error?.message ?? "unknown"}`);
    } finally {
      setAutomationLoading(false);
    }
  };

  const formatLiveTime = (value) => {
    if (!value) return "--";
    return new Date(value).toLocaleTimeString();
  };
  const tickLagMs = lastTickAt ? Math.max(0, nowTs - lastTickAt) : null;
  const reconnectCount = wsRetryTick + tradeReconnectCount;

  return (
    <div className="app-shell">
      <header className="top-bar">
        <div>
          <h1>Торговый бот</h1>
          <p>EMA200 + фигуры + дивергенции + Фибо + Elliott</p>
          <div className="app-tabs">
            <button
              type="button"
              className={activeTab === "trade" ? "active" : ""}
              onClick={() => setActiveTab("trade")}
            >
              Trade
            </button>
            <button
              type="button"
              className={activeTab === "backtest" ? "active" : ""}
              onClick={() => setActiveTab("backtest")}
            >
              Backtest
            </button>
            <button
              type="button"
              className={activeTab === "scanner" ? "active" : ""}
              onClick={() => setActiveTab("scanner")}
            >
              Scanner
            </button>
          </div>
        </div>
        <div className="top-actions">
          <button className="ghost layout-toggle" onClick={() => setShowSidePanel((prev) => !prev)}>
            {showSidePanel ? "Скрыть панели" : "Показать панели"}
          </button>
          <button className="ghost layout-toggle" onClick={() => setFitRequest((value) => value + 1)}>
            Вписать график
          </button>
          <div className="live-status">
            <span className={wsConnected ? "ok" : "bad"}>WS: {wsConnected ? "connected" : "disconnected"}</span>
            <span>feed: {feedSource}</span>
            <span>last tick: {formatLiveTime(lastTickAt)}</span>
            <span>tick lag: {tickLagMs === null ? "--" : `${tickLagMs} ms`}</span>
            <span>reconnects: {reconnectCount}</span>
            <span>last sync: {formatLiveTime(lastSyncAt)}</span>
            <span className={autoSyncRunning ? "ok" : ""}>auto-sync: {autoSyncRunning ? "running" : "idle"}</span>
          </div>
          <div className="status-pill">{status}</div>
        </div>
      </header>

      <main
        className="dashboard"
        style={{
          gridTemplateColumns: showSidePanel ? `minmax(0, 1fr) ${sidebarWidth}px` : "minmax(0, 1fr)",
        }}
      >
        {activeTab === "trade" ? (
        <section className="chart-card">
          <div className="chart-header">
            <div>
              <h2>{currentPair?.base_asset ? `${currentPair.base_asset}/${currentPair.quote_asset}` : symbol}</h2>
              <span>
                Timeframe {timeframe} · {market.toUpperCase()} · Binance {binanceSymbol ?? "n/a"}
              </span>
            </div>
            <div className="chart-tags">
              <select
                className="timeframe-select"
                value={timeframe}
                onChange={(event) => setTimeframe(event.target.value)}
              >
                <option value="1m">1m</option>
                <option value="5m">5m</option>
                <option value="15m">15m</option>
                <option value="1h">1h</option>
                <option value="4h">4h</option>
              </select>
              <button
                type="button"
                className={showEma ? "active" : ""}
                onClick={() => setShowEma((prev) => !prev)}
              >
                EMA200
              </button>
              <button
                type="button"
                className={showFib ? "active" : ""}
                onClick={() => setShowFib((prev) => !prev)}
              >
                FIB
              </button>
              <button
                type="button"
                className={showDivergence ? "active" : ""}
                onClick={() => setShowDivergence((prev) => !prev)}
              >
                Divergence
              </button>
            </div>
          </div>
          <div className="chart-body">
            {latestActiveOrder ? (
              <div className="chart-position-pill">
                <div className="chart-position-pill-head">
                  <strong>{latestActiveOrder.symbol} · {latestActiveOrder.side}</strong>
                  <span className={Number(activePositionRoi) >= 0 ? "positive" : "negative"}>
                    {Number.isFinite(activePositionRoi) ? `${activePositionRoi.toFixed(2)}%` : "--"}
                  </span>
                </div>
                <div className="chart-position-pill-grid">
                  <span>Entry {formatCompactNumber(latestActiveOrder.price, 6)}</span>
                  <span>SL {formatCompactNumber(latestActiveOrder.stop_loss, 6)}</span>
                  <span>TP {formatCompactNumber(latestActiveOrder.take_profit, 6)}</span>
                </div>
                <button
                  type="button"
                  className="ghost"
                  onClick={() => handleMoveStopToBreakeven(latestActiveOrder)}
                >
                  SL в BE
                </button>
              </div>
            ) : null}
            <ChartPanel
              candles={candles}
              signals={signals}
              openOrders={orders.filter((o) => (o.symbol || "").toUpperCase() === (binanceSymbol || symbol || "").toUpperCase())}
              pricePrecision={currentPair?.price_precision}
              indicatorData={indicatorData}
              height={chartHeight}
              dataKey={`${symbol}-${timeframe}-${market}`}
              tradeHistory={chartTrades}
              tradeMarkerMode={activeTab === "backtest" ? "trades" : "signals"}
              showEma={showEma}
              showFib={showFib}
              showDivergence={showDivergence}
              showCandlePatterns={showCandlePatterns}
              showChartPatterns={showChartPatterns}
              showElliott={showElliott}
              showSupportRes={showSupportRes}
              showTradePlan={showTradePlan}
              showBBands={showBBands}
              showVolume={showVolume}
              showAtr={showAtr}
              showRsi={showRsi}
              showPatternLabels={showPatternLabels}
              patternLimit={patternLimit}
              showPatternFill={showPatternFill}
              patternFillBands={patternFillBands}
              patternFillLimit={patternFillLimit}
              showUnconfirmedPatterns={showUnconfirmedPatterns}
              showTradeExits={showTradeExits}
              tradeHistoryLimit={tradeHistoryLimit}
              showTradePaths={showTradePaths}
              autoFit={autoFit}
              fitRequest={fitRequest}
              liveTickSeq={liveTickSeq}
              onLoadMoreCandles={handleLoadMoreCandles}
              signalTradePlan={chartTradePlan}
              activeOrder={latestActiveOrder}
              onMoveStopToPrice={handleMoveStopToPrice}
              onMoveTakeToPrice={handleMoveTakeToPrice}
              onRequestStopDragConfirm={handleRequestStopDragConfirm}
              onMoveStopToBreakeven={handleMoveStopToBreakeven}
              onNudgeStop={handleNudgeChartStop}
              onNudgeTake={handleNudgeChartTake}
            />
            {candles.length === 0 ? (
              <div className="chart-empty">Нет данных. Нажми "Синхронизировать историю".</div>
            ) : null}
          </div>
          <TradeHistoryPanel trades={displayedTrades} source={tradeHistorySource} />
        </section>
        ) : null}
        {activeTab === "backtest" ? (
          <section className="chart-card">
            <div className="workspace-header">
              <div>
                <div className="panel-title">Backtest Workspace</div>
                <div className="journal-subtitle">
                  {backtestMode === "single"
                    ? `Single Pair · ${backtestMeta?.selectedSymbol || symbol}`
                    : "Market-Wide · агрегированный результат по рынку"}
                </div>
              </div>
              <div className="segmented-toggle compact workspace-toggle">
                <button
                  type="button"
                  className={backtestMode === "single" ? "active" : ""}
                  onClick={() => setBacktestMode("single")}
                >
                  Single Pair
                </button>
                <button
                  type="button"
                  className={backtestMode === "market" ? "active" : ""}
                  onClick={() => setBacktestMode("market")}
                >
                  Market-Wide
                </button>
              </div>
            </div>
            <div className="workspace-summary-grid">
              <div className="workspace-summary-card">
                <span>Обработано пар</span>
                <strong>{backtestRunning ? backtestProgress?.processed_pairs ?? 0 : backtestMeta?.processedPairs ?? 0}</strong>
                <small>
                  из universe {backtestRunning ? backtestProgress?.total_pairs ?? 0 : backtestMeta?.universePairs ?? 0}
                </small>
              </div>
              <div className="workspace-summary-card">
                <span>{backtestRunning ? "Прогресс" : "Фокус"}</span>
                <strong>
                  {backtestRunning
                    ? `${backtestProgress?.matched_trades ?? 0} сделок`
                    : backtestMode === "single"
                      ? backtestMeta?.selectedSymbol || symbol
                      : `${quoteAsset === "ALL" ? "ALL" : quoteAsset} · ${market}`}
                </strong>
                <small>
                  {backtestRunning
                    ? `${backtestProgress?.current_symbol || "подготовка..."}`
                    : `${timeframe} · ${lookbackDays}d history`}
                </small>
              </div>
            </div>
            <StatsPanel stats={activeStats} />
            <TradeHistoryPanel trades={displayedTrades} source={tradeHistorySource} />
            <AnalysisDebugPanel debug={analysisDebug} />
          </section>
        ) : null}
        {activeTab === "scanner" ? (
          <section className="chart-card">
            <div className="panel-title">Scanner Workspace</div>
            <ScanResultsPanel
              results={scanResults}
              running={scanRunning}
              mode={scanMode}
              processedPairs={scanMeta?.processedPairs ?? 0}
              universePairs={scanMeta?.universePairs ?? 0}
              selectedSymbol={scanMeta?.selectedSymbol ?? symbol}
              diagnostics={scanDiagnostics}
              limit={scanLimit}
              maxPairs={scanMaxPairs}
              minVolatility={minVolatility}
              minConfidence={minConfidence}
              minConfirmations={minConfirmations}
              requirePattern={requirePattern}
              requireDivergence={requireDivergence}
              requireCandle={requireCandle}
              requireVolumeConfirm={requireVolumeConfirm}
              requireTrendFilter={requireTrendFilter}
              confluenceTolerance={confluenceTolerance}
              autoSync={scanAutoSync}
              onlyNewSignalsMinutes={onlyNewSignalsMinutes}
              onLimitChange={setScanLimit}
              onMaxPairsChange={setScanMaxPairs}
              onMinVolatilityChange={setMinVolatility}
              onMinConfidenceChange={setMinConfidence}
              onMinConfirmationsChange={setMinConfirmations}
              onRequirePatternChange={setRequirePattern}
              onRequireDivergenceChange={setRequireDivergence}
              onRequireCandleChange={setRequireCandle}
              onRequireVolumeConfirmChange={setRequireVolumeConfirm}
              onRequireTrendFilterChange={setRequireTrendFilter}
              onConfluenceToleranceChange={setConfluenceTolerance}
              onAutoSyncChange={setScanAutoSync}
              onOnlyNewSignalsMinutesChange={setOnlyNewSignalsMinutes}
              onModeChange={setScanMode}
              onRunScan={handleScan}
              onSelectResult={handleSelectScanResult}
            />
          </section>
        ) : null}
        {showSidePanel ? (
          <aside className="side-panel">
            <ControlPanel
              lookbackDays={lookbackDays}
              market={market}
              dataEnv={dataEnv}
              tradeEnv={tradeEnv}
              quantity={quantity}
              quoteAmount={quoteAmount}
              autoQuantity={autoQuantity}
              attachOrders={attachOrders}
              autoBreakeven={autoBreakeven}
              leverage={leverage}
              sidebarWidth={sidebarWidth}
              chartHeight={chartHeight}
              showSidePanel={showSidePanel}
              showEma={showEma}
              showFib={showFib}
              showDivergence={showDivergence}
              showCandlePatterns={showCandlePatterns}
              showChartPatterns={showChartPatterns}
              showElliott={showElliott}
              showSupportRes={showSupportRes}
              showTradePlan={showTradePlan}
              showBBands={showBBands}
              showVolume={showVolume}
              showAtr={showAtr}
              showRsi={showRsi}
              showPatternLabels={showPatternLabels}
              patternLimit={patternLimit}
              showPatternFill={showPatternFill}
              patternFillBands={patternFillBands}
              patternFillLimit={patternFillLimit}
              showUnconfirmedPatterns={showUnconfirmedPatterns}
              showTradeExits={showTradeExits}
              tradeHistoryLimit={tradeHistoryLimit}
              showTradePaths={showTradePaths}
              chartBars={chartBars}
              backfillStride={backfillStride}
              backfillMaxBars={backfillMaxBars}
              autoFit={autoFit}
              minConfidence={minConfidence}
              strategy={strategy}
              minConfirmations={minConfirmations}
              requirePattern={requirePattern}
              requireDivergence={requireDivergence}
              requireCandle={requireCandle}
              requireVolumeConfirm={requireVolumeConfirm}
              onLookbackChange={setLookbackDays}
              onMarketChange={setMarket}
              onDataEnvChange={setDataEnv}
              onTradeEnvChange={setTradeEnv}
              onQuantityChange={setQuantity}
              onQuoteAmountChange={setQuoteAmount}
              onAutoQuantityChange={setAutoQuantity}
              onAttachOrdersChange={setAttachOrders}
              onAutoBreakevenChange={setAutoBreakeven}
              onLeverageChange={setLeverage}
              onSidebarWidthChange={setSidebarWidth}
              onChartHeightChange={setChartHeight}
              onShowSidePanelChange={setShowSidePanel}
              onShowEmaChange={setShowEma}
              onShowFibChange={setShowFib}
              onShowDivergenceChange={setShowDivergence}
              onShowCandlePatternsChange={setShowCandlePatterns}
              onShowChartPatternsChange={setShowChartPatterns}
              onShowElliottChange={setShowElliott}
              onShowSupportResChange={setShowSupportRes}
              onShowTradePlanChange={setShowTradePlan}
              onShowBBandsChange={setShowBBands}
              onShowVolumeChange={setShowVolume}
              onShowAtrChange={setShowAtr}
              onShowRsiChange={setShowRsi}
              onShowPatternLabelsChange={setShowPatternLabels}
              onPatternLimitChange={setPatternLimit}
              onShowPatternFillChange={setShowPatternFill}
              onPatternFillBandsChange={setPatternFillBands}
              onPatternFillLimitChange={setPatternFillLimit}
              onShowUnconfirmedPatternsChange={setShowUnconfirmedPatterns}
              onShowTradeExitsChange={setShowTradeExits}
              onTradeHistoryLimitChange={setTradeHistoryLimit}
              onShowTradePathsChange={setShowTradePaths}
              onChartBarsChange={setChartBars}
              onBackfillStrideChange={setBackfillStride}
              onBackfillMaxBarsChange={setBackfillMaxBars}
              onAutoFitChange={setAutoFit}
              onMinConfidenceChange={setMinConfidence}
              onStrategyChange={handleStrategyChange}
              onMinConfirmationsChange={setMinConfirmations}
              onRequirePatternChange={setRequirePattern}
              onRequireDivergenceChange={setRequireDivergence}
              onRequireCandleChange={setRequireCandle}
              onRequireVolumeConfirmChange={setRequireVolumeConfirm}
              h1Timeframe={h1Timeframe}
              onH1TimeframeChange={setH1Timeframe}
              trendTimeframe={trendTimeframe}
              onTrendTimeframeChange={setTrendTimeframe}
              onBacktest={handleBacktest}
              backtestRunning={backtestRunning}
              onSync={handleSync}
              onAnalyze={handleAnalyze}
              mode={mode}
              onModeChange={setMode}
              onOpenConfirmOrder={handleOpenConfirmOrder}
              canConfirmOrder={activeTab === "trade" && mode === "semi" && latestSignalForTimeframe && binanceSymbol}
              status={status}
              wsConnected={wsConnected}
              tradeWsConnected={tradeWsConnected}
              feedSource={feedSource}
              autoSyncRunning={autoSyncRunning}
              lastSyncLabel={formatLiveTime(lastSyncAt)}
              currentPair={currentPair}
              currentPrice={currentPrice}
              latestSignal={latestSignalForTimeframe}
              latestActiveOrder={latestActiveOrder}
              positionRoi={activePositionRoi}
              chartStopInput={chartStopInput}
              chartTakeInput={chartTakeInput}
              onChartStopInputChange={setChartStopInput}
              onChartTakeInputChange={setChartTakeInput}
              onMoveStopToBreakeven={handleMoveStopToBreakeven}
              onMoveStopToPrice={handleMoveStopToPrice}
              onMoveTakeToPrice={handleMoveTakeToPrice}
              onCloseOrder={handleCloseOrder}
              onNudgeChartStop={handleNudgeChartStop}
              onNudgeChartTake={handleNudgeChartTake}
            />
            {activeTab === "trade" ? (
              <AutomationCenter
                state={automationState}
                loading={automationLoading}
                onSyncWorkspace={handleSyncWorkspaceToAutomation}
                onEnable={() => runAutomationAction(enableAutomation, "Automation включена")}
                onDisable={() => runAutomationAction(disableAutomation, "Automation остановлена")}
                onRunNow={() => runAutomationAction(runAutomationNow, "Automation цикл выполнен")}
                onSetMode={(nextMode) =>
                  runAutomationAction(() => setAutomationMode(nextMode), `Automation mode: ${nextMode.toUpperCase()}`)
                }
                onSetTradeEnv={(nextTradeEnv) =>
                  runAutomationAction(() => setAutomationTradeEnv(nextTradeEnv), `Automation env: ${nextTradeEnv}`)
                }
                onApprove={(signalId) =>
                  runAutomationAction(
                    async () => {
                      const snapshot = await approveAutomationSignal(signalId);
                      const updatedOrders = await fetchOrders(100);
                      setOrders(updatedOrders);
                      return snapshot;
                    },
                    `Сигнал ${signalId} подтвержден`
                  )
                }
                onReject={(signalId) =>
                  runAutomationAction(() => rejectAutomationSignal(signalId), `Сигнал ${signalId} отклонен`)
                }
              />
            ) : null}
            {activeTab === "trade" ? (
              <OrderBookPanel
                book={orderBook}
                loading={orderBookLoading}
                error={orderBookError}
              />
            ) : null}
            {activeTab === "scanner" || activeTab === "trade" ? (
            <PairsPanel
              pairs={filteredPairs}
              selectedSymbol={binanceSymbol || symbol}
              search={pairSearch}
              minVolatility={minVolatility}
              maxPrice={maxPrice}
              maxNotional={maxNotional}
              quoteAsset={quoteAsset}
              onSearchChange={setPairSearch}
              onMinVolatilityChange={setMinVolatility}
              onMaxPriceChange={setMaxPrice}
              onMaxNotionalChange={setMaxNotional}
              onQuoteAssetChange={setQuoteAsset}
              onSelectPair={handleSelectPair}
              loading={pairsLoading}
            />
            ) : null}
            {activeTab === "backtest" ? <StatsPanel stats={activeStats} /> : null}
            {activeTab === "trade" ? <AccountPanel summary={accountSummary} trades={accountTrades} /> : null}
            {activeTab !== "scanner" ? <AnalysisDebugPanel debug={analysisDebug} /> : null}
            {activeTab === "trade" ? (
            <div className="signals-panel">
              <div className="signals-title">Сигналы</div>
              <SignalList signals={signalsForTimeframe} />
            </div>
            ) : null}
            {activeTab === "trade" ? (
              <TradeJournal
                orders={orders}
                priceMap={priceMap}
                futuresPositionMap={futuresPositionMap}
                onSelectOrder={setActiveOrder}
                onCloseOrder={handleCloseOrder}
                onMoveStopToBreakeven={handleMoveStopToBreakeven}
                onMoveStopToPrice={handleMoveStopToPrice}
              />
            ) : null}
          </aside>
        ) : null}
      </main>
      <OrderDetailsModal
        open={Boolean(activeOrder)}
        order={activeOrder}
        trades={accountTrades}
        loading={!accountSummary}
        onClose={() => setActiveOrder(null)}
      />
      <OrderConfirmModal
        open={confirmOrderOpen}
        onClose={() => setConfirmOrderOpen(false)}
        onConfirm={handlePlaceOrder}
        market={market}
        side={latestSignalForTimeframe?.signal_type === "short" ? "SELL" : "BUY"}
        symbol={binanceSymbol || symbol}
        orderType="MARKET"
        quantity={Number(quantity)}
        onQuantityChange={setQuantity}
        quoteAmount={Number(quoteAmount)}
        onQuoteAmountChange={setQuoteAmount}
        autoQuantity={autoQuantity}
        leverage={leverage}
        onLeverageChange={setLeverage}
        entryPrice={candles.length ? Number(candles[candles.length - 1].close) : null}
        stopLoss={latestSignalForTimeframe?.meta?.trade_plan?.stop_loss ?? latestSignalForTimeframe?.stop_loss}
        takeProfit={latestSignalForTimeframe?.meta?.trade_plan?.take_profit ?? latestSignalForTimeframe?.take_profit}
        takeLevels={latestSignalForTimeframe?.meta?.trade_plan?.take_levels ?? null}
        minQty={Number(currentPair?.min_qty ?? 0)}
        minNotional={Number(currentPair?.min_notional ?? 0)}
        stepSize={Number(currentPair?.step_size ?? 0)}
      />
      {newSignalModal.open ? (
        <div className="modal-backdrop" onClick={() => setNewSignalModal({ open: false, first: null, count: 0 })}>
          <div className="modal-card" onClick={(event) => event.stopPropagation()}>
            <h3>Новый сигнал</h3>
            <p style={{ color: "var(--muted)", marginTop: 8 }}>
              Найдено новых сигналов: <strong>{newSignalModal.count}</strong>
            </p>
            <p style={{ color: "var(--muted)", marginTop: 6 }}>
              {newSignalModal.first?.binance_symbol ?? newSignalModal.first?.symbol} · {newSignalModal.first?.timeframe}
            </p>
            <div style={{ display: "flex", gap: 10, marginTop: 14 }}>
              <button
                className="primary"
                onClick={() => {
                  if (newSignalModal.first) {
                    handleSelectScanResult(newSignalModal.first);
                  }
                  setNewSignalModal({ open: false, first: null, count: 0 });
                }}
              >
                Открыть сигнал
              </button>
              <button
                className="ghost"
                onClick={() => {
                  const url = newSignalModal.first?.chart_url;
                  if (url) window.open(url, "_blank", "noopener,noreferrer");
                }}
              >
                Открыть Binance
              </button>
            </div>
          </div>
        </div>
      ) : null}
      {stopDragConfirmModal.open ? (
        <div
          className="modal-backdrop"
          onClick={() => setStopDragConfirmModal({ open: false, order: null, nextStop: null })}
        >
          <div className="modal-card" onClick={(event) => event.stopPropagation()}>
            <h3>Подтвердить перенос SL</h3>
            <p style={{ color: "var(--muted)", marginTop: 8 }}>
              {stopDragConfirmModal.order?.symbol} · {stopDragConfirmModal.order?.side}
            </p>
            <p style={{ color: "var(--muted)", marginTop: 6 }}>
              Новый Stop Loss: <strong>{Number(stopDragConfirmModal.nextStop || 0).toFixed(6)}</strong>
            </p>
            <div style={{ display: "flex", gap: 10, marginTop: 14 }}>
              <button
                className="primary"
                onClick={async () => {
                  const { order, nextStop } = stopDragConfirmModal;
                  setStopDragConfirmModal({ open: false, order: null, nextStop: null });
                  await handleMoveStopToPrice(order, Number(nextStop));
                }}
              >
                Подтвердить
              </button>
              <button
                className="ghost"
                onClick={() => setStopDragConfirmModal({ open: false, order: null, nextStop: null })}
              >
                Отмена
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
