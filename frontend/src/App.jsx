import { useEffect, useMemo, useRef, useState } from "react";
import ChartPanel from "./components/ChartPanel.jsx";
import ControlPanel from "./components/ControlPanel.jsx";
import MappingTable from "./components/MappingTable.jsx";
import PairsPanel from "./components/PairsPanel.jsx";
import ScanResultsPanel from "./components/ScanResultsPanel.jsx";
import SignalHistoryModal from "./components/SignalHistoryModal.jsx";
import SignalList from "./components/SignalList.jsx";
import StatsPanel from "./components/StatsPanel.jsx";
import TradeHistoryPanel from "./components/TradeHistoryPanel.jsx";
import TradeJournal from "./components/TradeJournal.jsx";
import AnalysisDebugPanel from "./components/AnalysisDebugPanel.jsx";
import AccountPanel from "./components/AccountPanel.jsx";
import {
  createMapping,
  backfillSignals,
  deleteMapping,
  fetchCandles,
  fetchIndicators,
  fetchMappings,
  fetchOrders,
  fetchPairs,
  fetchSignalById,
  fetchSignals,
  explainAnalysis,
  fetchAccountSummary,
  fetchAccountTrades,
  moveStopToBreakeven,
  moveStopToPrice,
  placeOrder,
  resolveSymbol,
  runAnalysis,
  runBacktest,
  scanMarket,
  syncMarket,
  updateMapping,
} from "./api/client.js";

function toEpochSeconds(value) {
  return Math.floor(new Date(value).getTime() / 1000);
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
  const [timeframe, setTimeframe] = useState("15m");
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
  const [mappings, setMappings] = useState([]);
  const [pairs, setPairs] = useState([]);
  const [pairsLoading, setPairsLoading] = useState(false);
  const [pairSearch, setPairSearch] = useState("");
  const [minVolatility, setMinVolatility] = useState(0);
  const [maxPrice, setMaxPrice] = useState(0);
  const [maxNotional, setMaxNotional] = useState(0);
  const [quoteAsset, setQuoteAsset] = useState("ALL");
  const [selectedPair, setSelectedPair] = useState(null);
  const [scanResults, setScanResults] = useState([]);
  const [scanRunning, setScanRunning] = useState(false);
  const [scanLimit, setScanLimit] = useState(20);
  const [scanMaxPairs, setScanMaxPairs] = useState(50);
  const [scanAutoSync, setScanAutoSync] = useState(false);
  const [activeOrder, setActiveOrder] = useState(null);
  const [historySignals, setHistorySignals] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [indicatorData, setIndicatorData] = useState(null);
  const [mode, setMode] = useState("semi");
  const [h1Timeframe, setH1Timeframe] = useState("1h");
  const [trendTimeframe, setTrendTimeframe] = useState("4h");

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
  const [minConfidence, setMinConfidence] = useState(0.45);
  const [minConfirmations, setMinConfirmations] = useState(1);
  const [requirePattern, setRequirePattern] = useState(false);
  const [requireDivergence, setRequireDivergence] = useState(false);
  const [requireCandle, setRequireCandle] = useState(false);
  const [requireVolumeConfirm, setRequireVolumeConfirm] = useState(false);
  const [backtestStats, setBacktestStats] = useState(null);
  const [backtestTrades, setBacktestTrades] = useState([]);
  const [backtestRunning, setBacktestRunning] = useState(false);
  const [analysisDebug, setAnalysisDebug] = useState(null);
  const [accountSummary, setAccountSummary] = useState(null);
  const [accountTrades, setAccountTrades] = useState([]);
  const [leverage, setLeverage] = useState(10);
  const [fitRequest, setFitRequest] = useState(0);
  const syncAttemptsRef = useRef(new Set());
  const breakevenTriggeredRef = useRef(new Set());

  const latestSignal = useMemo(() => signals[0], [signals]);
  const priceMap = useMemo(() => new Map(pairs.map((pair) => [pair.symbol, pair.last_price])), [pairs]);
  const currentPair = useMemo(() => {
    if (selectedPair?.symbol === binanceSymbol) {
      return selectedPair;
    }
    return pairs.find((pair) => pair.symbol === binanceSymbol) ?? selectedPair;
  }, [selectedPair, pairs, binanceSymbol]);

  const filteredPairs = useMemo(() => {
    return pairs
      .filter((pair) => {
        if (pairSearch) {
          const search = pairSearch.toUpperCase();
          const target = `${pair.symbol} ${pair.base_asset ?? ""} ${pair.quote_asset ?? ""} ${
            pair.yfinance_symbol ?? ""
          }`.toUpperCase();
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
    const total = signals.length;
    const pnlValues = orders
      .map((order) => {
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
  }, [signals, orders, priceMap]);

  const activeStats = backtestStats ?? stats;

  const tradeHistory = useMemo(
    () => buildTradeHistory(candles, signals, tradeHistoryLimit),
    [candles, signals, tradeHistoryLimit]
  );
  const displayedTrades = backtestTrades.length ? backtestTrades : tradeHistory;
  const chartTrades = useMemo(() => {
    if (!displayedTrades.length) return [];
    const ordered = [...displayedTrades].sort((a, b) => a.entry_time - b.entry_time);
    const limit = Math.max(5, Number(tradeHistoryLimit) || 20);
    return ordered.slice(-limit);
  }, [displayedTrades, tradeHistoryLimit]);

  const chartLimit = useMemo(() => Math.max(chartBars, 200), [chartBars]);
  const indicatorLimit = useMemo(() => Math.min(Math.max(chartLimit, 240), 5000), [chartLimit]);
  const maxCandles = useMemo(() => chartLimit + 200, [chartLimit]);
  const pageSize = 1000;
  const maxCandlesTotal = useMemo(() => Math.max(maxCandles, 15000), [maxCandles]);

  useEffect(() => {
    setBacktestStats(null);
    setBacktestTrades([]);
    setAnalysisDebug(null);
  }, [symbol, timeframe, market]);

  useEffect(() => {
    let active = true;
    async function loadAccount() {
      try {
        const summary = await fetchAccountSummary(market, tradeEnv);
        if (active) setAccountSummary(summary);
        const trades = await fetchAccountTrades(market, tradeEnv, binanceSymbol, 50);
        if (active) setAccountTrades(trades?.trades ?? []);
      } catch (e) {
        if (active) {
          setAccountSummary({ status: "error", market, trade_env: tradeEnv, error: e?.message ?? "ошибка" });
          setAccountTrades([]);
        }
      }
    }
    loadAccount();
    const interval = setInterval(loadAccount, 10000);
    return () => {
      active = false;
      clearInterval(interval);
    };
  }, [market, tradeEnv, binanceSymbol]);

  useEffect(() => {
    async function load() {
      setCandles([]);
      setSignals([]);
      setIndicatorData(null);
      try {
        let data = await fetchCandles(symbol, timeframe, chartLimit);
        const syncKey = `${symbol}:${timeframe}:${market}:${dataEnv}`;
        const shouldSync = binanceSymbol && data.length < 20 && !syncAttemptsRef.current.has(syncKey);
        if (shouldSync) {
          setStatus("Нет истории, синхронизирую...");
          try {
            syncAttemptsRef.current.add(syncKey);
            await syncMarket(symbol, timeframe, lookbackDays, market, binanceSymbol, dataEnv);
            data = await fetchCandles(symbol, timeframe, chartLimit);
          } catch (syncError) {
            // ignore sync failures, fall back to empty state
          }
        }
        setCandles(data);
        const signalData = await fetchSignals(symbol, 100, timeframe);
        setSignals(signalData);
        if (data.length) {
          try {
            const indicators = await fetchIndicators(symbol, timeframe, indicatorLimit);
            setIndicatorData(indicators);
          } catch (indicatorError) {
            setIndicatorData(null);
          }
        } else {
          setIndicatorData(null);
        }
        if (data.length === 0) {
          setStatus("История отсутствует");
        } else {
          setStatus("Готово");
        }
      } catch (error) {
        setCandles([]);
        setStatus("Ошибка загрузки");
      }
    }

    load();
  }, [symbol, timeframe, market, binanceSymbol, lookbackDays, dataEnv, chartLimit, indicatorLimit]);

  useEffect(() => {
    setSelectedPair(null);
    setBinanceSymbol(null);
  }, [market]);

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
    async function loadMappings() {
      try {
        const data = await fetchMappings();
        setMappings(data);
      } catch (error) {
        setMappings([]);
      }
    }

    loadMappings();
  }, []);

  useEffect(() => {
    if (!activeOrder) return;
    let active = true;
    async function loadHistory() {
      setHistoryLoading(true);
      try {
        let baseSignal = null;
        if (activeOrder.signal_id) {
          baseSignal = await fetchSignalById(activeOrder.signal_id);
        }
        const symbolForSignals = baseSignal?.symbol;
        const timeframeForSignals = baseSignal?.timeframe || activeOrder.timeframe;
        const data = await fetchSignals(symbolForSignals, 200, timeframeForSignals);
        if (active) {
          setHistorySignals(data);
        }
      } catch (error) {
        if (active) {
          setHistorySignals([]);
        }
      } finally {
        if (active) {
          setHistoryLoading(false);
        }
      }
    }

    loadHistory();
    return () => {
      active = false;
    };
  }, [activeOrder]);

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
    const socket = new WebSocket(wsUrl);

    socket.onmessage = (event) => {
      const payload = JSON.parse(event.data);
      if (payload.type === "error") {
        setStatus(`Стрим: ${payload.message}`);
        return;
      }
      if (payload.type !== "kline") return;

      const candle = payload.data;
      setCandles((prev) => {
        if (!prev.length) return [candle];
        const last = prev[prev.length - 1];
        if (last.open_time === candle.open_time) {
        const updated = [...prev];
        updated[updated.length - 1] = candle;
        return updated;
      }
        const next = [...prev, candle];
        if (next.length > maxCandlesTotal) {
          return next.slice(next.length - maxCandlesTotal);
        }
        return next;
      });
      if (candle.is_final) {
        void (async () => {
          try {
            const indicators = await fetchIndicators(symbol, timeframe, indicatorLimit);
            setIndicatorData(indicators);
          } catch (indicatorError) {
            // keep last indicators on failure
          }
        })();
      }
    };

    socket.onerror = () => {
      setStatus("Ошибка стрима");
    };

    return () => {
      socket.close();
    };
  }, [binanceSymbol, symbol, timeframe, market, dataEnv, maxCandlesTotal, indicatorLimit]);

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
    if (!binanceSymbol) {
      setStatus("Сначала выбери торговую пару Binance");
      return;
    }
    setStatus("Синхронизация истории...");
    try {
      await syncMarket(symbol, timeframe, lookbackDays, market, binanceSymbol, dataEnv);
      await syncMarket(symbol, h1Timeframe, lookbackDays, market, binanceSymbol, dataEnv);
      await syncMarket(symbol, trendTimeframe, lookbackDays, market, binanceSymbol, dataEnv);
      const data = await fetchCandles(symbol, timeframe, chartLimit);
      setCandles(data);
      setStatus(data.length ? "История синхронизирована" : "История отсутствует");
      if (data.length) {
        try {
          setStatus("Заполняю сигналы по истории...");
          await backfillSignals({
            symbol,
            timeframe,
            lookback_days: lookbackDays,
            stride: backfillStride,
            max_bars: backfillMaxBars,
          });
          const signalData = await fetchSignals(symbol, 100, timeframe);
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
          min_confidence: minConfidence,
          min_confirmations: minConfirmations,
          require_pattern: requirePattern,
          require_divergence: requireDivergence,
          require_candle: requireCandle,
          require_volume_confirm: requireVolumeConfirm,
          leverage: market === "futures" ? leverage : null,
        }
      );
      if (response.signal) {
        setSignals((prev) => {
          if (prev.length && prev[0].id === response.signal.id) return prev;
          return [response.signal, ...prev];
        });
      }
      const signalData = await fetchSignals(symbol, 100, timeframe);
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
            lookback_days: lookbackDays,
            market,
            data_env: dataEnv,
            min_confidence: minConfidence,
            min_confirmations: minConfirmations,
            require_pattern: requirePattern,
            require_divergence: requireDivergence,
            require_candle: requireCandle,
            require_volume_confirm: requireVolumeConfirm,
          });
          setAnalysisDebug(explained.debug ?? null);
        } catch (e) {
          setAnalysisDebug({ reasons: ["explain_failed"] });
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
    setStatus("Запуск бэктеста...");
    try {
      const response = await runBacktest({
        symbol,
        timeframe,
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
      });
      setBacktestStats(response.stats ?? null);
      setBacktestTrades(response.trades ?? []);
      const totalTrades = response.stats?.total_trades ?? 0;
      setStatus(`Бэктест готов (${totalTrades})`);
    } catch (error) {
      setStatus("Ошибка бэктеста");
    } finally {
      setBacktestRunning(false);
    }
  };

  const handlePlaceOrder = async () => {
    if (!latestSignal || !binanceSymbol) return;
    if (market === "spot" && latestSignal.signal_type === "short") {
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
      await placeOrder({
        exchange: "binance",
        market,
        symbol: binanceSymbol,
        side: latestSignal.signal_type === "long" ? "BUY" : "SELL",
        order_type: "MARKET",
        quantity,
        leverage: market === "futures" ? leverage : null,
        trade_env: tradeEnv,
        quote_amount: autoQuantity ? quoteAmount : null,
        auto_quantity: autoQuantity,
        timeframe,
        signal_id: latestSignal.id,
        price: lastPrice,
        stop_loss: latestSignal.meta?.trade_plan?.stop_loss ?? latestSignal.stop_loss,
        take_profit: latestSignal.meta?.trade_plan?.take_profit ?? latestSignal.take_profit,
        take_levels: latestSignal.meta?.trade_plan?.take_levels ?? null,
        breakeven_at: latestSignal.meta?.trade_plan?.breakeven_at ?? null,
        auto_breakeven: autoBreakeven,
        attach_orders: attachOrders,
      });
      const updatedOrders = await fetchOrders(100);
      setOrders(updatedOrders);
      setStatus("Ордер отправлен");
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
            hint = ` Минимум для ${currentPair.symbol}: примерно ${required.toFixed(2)} ${quote} (minQty=${minQty}, шаг=${step}).`;
          }
        }
      }
      setStatus(`Ошибка ордера: ${humanizeApiError(code)}${hint}`);
    }
  };

  const handleSelectPair = async (pair) => {
    setSelectedPair({ ...pair, market });
    setSymbol(pair.symbol);
    setBinanceSymbol(pair.symbol);
    if (pair.yfinance_symbol) {
      try {
        await createMapping({
          yfinance_symbol: pair.yfinance_symbol,
          binance_symbol: pair.symbol,
          market,
        });
      } catch (error) {
        const existing = mappings.find(
          (item) => item.yfinance_symbol === pair.yfinance_symbol && item.market === market
        );
        if (existing && existing.binance_symbol !== pair.symbol) {
          try {
            await updateMapping(existing.id, { binance_symbol: pair.symbol, market });
          } catch (updateError) {
            // ignore update errors
          }
        }
      }
      const updatedMappings = await fetchMappings();
      setMappings(updatedMappings);
    }
  };

  const handleCreateMapping = async (payload) => {
    try {
      await createMapping(payload);
      const updatedMappings = await fetchMappings();
      setMappings(updatedMappings);
    } catch (error) {
      setStatus("Ошибка создания маппинга");
    }
  };

  const handleUpdateMapping = async (id, payload) => {
    try {
      await updateMapping(id, payload);
      const updatedMappings = await fetchMappings();
      setMappings(updatedMappings);
    } catch (error) {
      setStatus("Ошибка обновления маппинга");
    }
  };

  const handleDeleteMapping = async (id) => {
    try {
      await deleteMapping(id);
      const updatedMappings = await fetchMappings();
      setMappings(updatedMappings);
    } catch (error) {
      setStatus("Ошибка удаления маппинга");
    }
  };

  const handleScan = async () => {
    setScanRunning(true);
    setStatus("Сканирую рынок...");
    try {
      const response = await scanMarket({
        market,
        timeframe,
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
        min_confidence: minConfidence,
        min_confirmations: minConfirmations,
        require_pattern: requirePattern,
        require_divergence: requireDivergence,
        require_candle: requireCandle,
        require_volume_confirm: requireVolumeConfirm,
      });
      setScanResults(response.signals ?? []);
      setStatus(`Скан готов (${response.scanned})`);
    } catch (error) {
      setStatus("Ошибка сканирования");
      setScanResults([]);
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

  return (
    <div className="app-shell">
      <header className="top-bar">
        <div>
          <h1>Торговый бот</h1>
          <p>EMA200 + фигуры + дивергенции + Фибо + Elliott</p>
        </div>
        <div className="top-actions">
          <button className="ghost layout-toggle" onClick={() => setShowSidePanel((prev) => !prev)}>
            {showSidePanel ? "Скрыть панели" : "Показать панели"}
          </button>
          <button className="ghost layout-toggle" onClick={() => setFitRequest((value) => value + 1)}>
            Вписать график
          </button>
          <div className="status-pill">{status}</div>
        </div>
      </header>

      <main
        className="dashboard"
        style={{
          gridTemplateColumns: showSidePanel ? `minmax(0, 1fr) ${sidebarWidth}px` : "minmax(0, 1fr)",
        }}
      >
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
            <ChartPanel
              candles={candles}
              signals={signals}
              pricePrecision={currentPair?.price_precision}
              indicatorData={indicatorData}
              height={chartHeight}
              dataKey={`${symbol}-${timeframe}-${market}`}
              tradeHistory={chartTrades}
              tradeMarkerMode={backtestTrades.length ? "trades" : "signals"}
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
              onLoadMoreCandles={handleLoadMoreCandles}
            />
            {candles.length === 0 ? (
              <div className="chart-empty">Нет данных. Нажми "Синхронизировать историю".</div>
            ) : null}
          </div>
          <TradeHistoryPanel trades={displayedTrades} />
        </section>
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
              onModeToggle={() => setMode((prev) => (prev === "auto" ? "semi" : "auto"))}
            />
            <PairsPanel
              pairs={filteredPairs}
              selectedSymbol={symbol}
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
            <ScanResultsPanel
              results={scanResults}
              running={scanRunning}
              limit={scanLimit}
              maxPairs={scanMaxPairs}
              minVolatility={minVolatility}
              minConfidence={minConfidence}
              minConfirmations={minConfirmations}
              requirePattern={requirePattern}
              requireDivergence={requireDivergence}
              requireCandle={requireCandle}
              requireVolumeConfirm={requireVolumeConfirm}
              autoSync={scanAutoSync}
              onLimitChange={setScanLimit}
              onMaxPairsChange={setScanMaxPairs}
              onMinVolatilityChange={setMinVolatility}
              onMinConfidenceChange={setMinConfidence}
              onMinConfirmationsChange={setMinConfirmations}
              onRequirePatternChange={setRequirePattern}
              onRequireDivergenceChange={setRequireDivergence}
              onRequireCandleChange={setRequireCandle}
              onRequireVolumeConfirmChange={setRequireVolumeConfirm}
              onAutoSyncChange={setScanAutoSync}
              onRunScan={handleScan}
              onSelectResult={handleSelectScanResult}
            />
            {mode === "semi" && latestSignal && binanceSymbol ? (
              <button className="primary confirm-order" onClick={handlePlaceOrder}>
                Подтвердить ордер ({latestSignal.signal_type.toUpperCase()})
              </button>
            ) : null}
            <StatsPanel stats={activeStats} />
            <AccountPanel summary={accountSummary} trades={accountTrades} />
            <AnalysisDebugPanel debug={analysisDebug} />
            <div className="signals-panel">
              <div className="signals-title">Сигналы</div>
              <SignalList signals={signals} />
            </div>
            <TradeJournal orders={orders} priceMap={priceMap} onSelectOrder={setActiveOrder} />
            <MappingTable
              mappings={mappings}
              onCreate={handleCreateMapping}
              onUpdate={handleUpdateMapping}
              onDelete={handleDeleteMapping}
            />
          </aside>
        ) : null}
      </main>
      <SignalHistoryModal
        open={Boolean(activeOrder)}
        order={activeOrder}
        signals={historySignals}
        loading={historyLoading}
        onClose={() => setActiveOrder(null)}
      />
    </div>
  );
}
