import { createChart } from "lightweight-charts";
import { useEffect, useMemo, useRef } from "react";

function toChartData(candles) {
  return candles.map((candle) => ({
    time: Math.floor(new Date(candle.open_time).getTime() / 1000),
    open: candle.open,
    high: candle.high,
    low: candle.low,
    close: candle.close,
  }));
}

function uniqueAscByTime(items) {
  if (!Array.isArray(items) || !items.length) return [];
  const byTime = new Map();
  items.forEach((item) => {
    const t = Number(item?.time);
    if (!Number.isFinite(t)) return;
    byTime.set(t, { ...item, time: t });
  });
  return [...byTime.values()].sort((a, b) => a.time - b.time);
}

function resolvePrecision(candles, pricePrecision) {
  if (Number.isFinite(pricePrecision) && pricePrecision > 0) {
    return Math.min(Math.max(pricePrecision, 2), 10);
  }
  if (!candles.length) return 2;
  const last = candles[candles.length - 1];
  const price = Math.abs(last.close);
  if (price >= 1000) return 2;
  if (price >= 100) return 3;
  if (price >= 1) return 4;
  if (price >= 0.1) return 5;
  if (price >= 0.01) return 6;
  if (price >= 0.001) return 7;
  return 8;
}

function calculateEma(data, period) {
  if (!data.length) return [];
  const k = 2 / (period + 1);
  let ema = data[0].close;
  return data.map((candle, index) => {
    if (index === 0) {
      ema = candle.close;
    } else {
      ema = candle.close * k + ema * (1 - k);
    }
    return { time: candle.time, value: ema };
  });
}

function calculateRsi(values, period = 14) {
  if (!values.length) return [];
  if (values.length <= period) {
    return values.map(() => 0);
  }
  const rsi = new Array(values.length).fill(0);
  let gains = 0;
  let losses = 0;

  for (let i = 1; i <= period; i += 1) {
    const change = values[i] - values[i - 1];
    if (change >= 0) gains += change;
    else losses -= change;
  }

  let avgGain = gains / period;
  let avgLoss = losses / period;
  rsi[period] = avgLoss === 0 ? 100 : 100 - 100 / (1 + avgGain / avgLoss);

  for (let i = period + 1; i < values.length; i += 1) {
    const change = values[i] - values[i - 1];
    const gain = change > 0 ? change : 0;
    const loss = change < 0 ? -change : 0;
    avgGain = (avgGain * (period - 1) + gain) / period;
    avgLoss = (avgLoss * (period - 1) + loss) / period;
    if (avgLoss === 0) {
      rsi[i] = 100;
    } else {
      const rs = avgGain / avgLoss;
      rsi[i] = 100 - 100 / (1 + rs);
    }
  }

  return rsi;
}

function findPivots(values, window, mode) {
  const pivots = [];
  for (let i = window; i < values.length - window; i += 1) {
    const slice = values.slice(i - window, i + window + 1);
    const current = values[i];
    if (mode === "high" && current === Math.max(...slice)) {
      pivots.push({ index: i, value: current });
    }
    if (mode === "low" && current === Math.min(...slice)) {
      pivots.push({ index: i, value: current });
    }
  }
  return pivots;
}

function detectDivergence(chartData) {
  if (chartData.length < 30) return [];
  const closes = chartData.map((candle) => candle.close);
  const highs = chartData.map((candle) => candle.high);
  const lows = chartData.map((candle) => candle.low);
  const rsi = calculateRsi(closes);
  const window = 5;

  const priceHighs = findPivots(highs, window, "high");
  const priceLows = findPivots(lows, window, "low");
  const rsiHighs = findPivots(rsi, window, "high");
  const rsiLows = findPivots(rsi, window, "low");

  const markers = [];

  if (priceLows.length >= 2 && rsiLows.length >= 2) {
    const lastPriceLow = priceLows[priceLows.length - 1];
    const prevPriceLow = priceLows[priceLows.length - 2];
    const lastRsiLow = rsiLows[rsiLows.length - 1];
    const prevRsiLow = rsiLows[rsiLows.length - 2];
    if (lastPriceLow.value < prevPriceLow.value && lastRsiLow.value > prevRsiLow.value) {
      markers.push({
        time: chartData[lastPriceLow.index].time,
        position: "belowBar",
        color: "#22c55e",
        shape: "circle",
        text: "Быч. див",
      });
    }
  }

  if (priceHighs.length >= 2 && rsiHighs.length >= 2) {
    const lastPriceHigh = priceHighs[priceHighs.length - 1];
    const prevPriceHigh = priceHighs[priceHighs.length - 2];
    const lastRsiHigh = rsiHighs[rsiHighs.length - 1];
    const prevRsiHigh = rsiHighs[rsiHighs.length - 2];
    if (lastPriceHigh.value > prevPriceHigh.value && lastRsiHigh.value < prevRsiHigh.value) {
      markers.push({
        time: chartData[lastPriceHigh.index].time,
        position: "aboveBar",
        color: "#ef4444",
        shape: "circle",
        text: "Медв. див",
      });
    }
  }

  return markers;
}

function calculateFibLevels(chartData, lookback = 120) {
  if (!chartData.length) return [];
  const slice = chartData.slice(-lookback);
  const highs = slice.map((candle) => candle.high);
  const lows = slice.map((candle) => candle.low);
  const high = Math.max(...highs);
  const low = Math.min(...lows);
  const diff = high - low;
  if (diff <= 0) return [];

  return [
    { label: "0.236", value: high - diff * 0.236, color: "#facc15" },
    { label: "0.382", value: high - diff * 0.382, color: "#f59e0b" },
    { label: "0.5", value: high - diff * 0.5, color: "#e2e8f0" },
    { label: "0.618", value: high - diff * 0.618, color: "#22c55e" },
    { label: "0.786", value: high - diff * 0.786, color: "#ef4444" },
  ];
}

function formatPatternLabel(name) {
  const map = {
    CDLENGULFING: "ENG",
    CDLDOJI: "DOJI",
    CDLHAMMER: "HAM",
    CDLSHOOTINGSTAR: "SHOOT",
    CDLMORNINGSTAR: "MSTAR",
    CDLEVENINGSTAR: "ESTAR",
    CDLHARAMI: "HARAMI",
    CDLPIERCING: "PIER",
    CDLDARKCLOUDCOVER: "DARK",
  };
  if (map[name]) return map[name];
  if (!name) return "PAT";
  return name.replace("CDL", "").slice(0, 6);
}

export default function ChartPanel({
  candles,
  signals,
  tradeHistory = [],
  pricePrecision,
  indicatorData,
  height = 520,
  onLoadMoreCandles,
  showEma = true,
  showFib = true,
  showDivergence = true,
  showCandlePatterns = false,
  showChartPatterns = true,
  showElliott = false,
  showSupportRes = true,
  showTradePlan = true,
  showBBands = false,
  showVolume = true,
  showAtr = false,
  showRsi = true,
  showPatternLabels = false,
  patternLimit = 15,
  showPatternFill = false,
  patternFillBands = 4,
  patternFillLimit = 3,
  showUnconfirmedPatterns = false,
  showTradeExits = true,
  showTradePaths = true,
  // "signals" = show signal markers (entries are driven by signals array)
  // "trades"  = show entry markers from tradeHistory (used for backtest visualization)
  tradeMarkerMode = "signals",
  autoFit = false,
  fitRequest = 0,
  dataKey = "",
}) {
  const chartRef = useRef(null);
  const containerRef = useRef(null);
  const seriesRef = useRef(null);
  const emaRef = useRef(null);
  const bbUpperRef = useRef(null);
  const bbMiddleRef = useRef(null);
  const bbLowerRef = useRef(null);
  const volumeRef = useRef(null);
  const atrRef = useRef(null);
  const rsiRef = useRef(null);
  const fibLinesRef = useRef([]);
  const srLinesRef = useRef([]);
  const planLinesRef = useRef([]);
  const patternLineRefs = useRef([]);
  const lastDataKeyRef = useRef("");
  const overlayRef = useRef(null);
  const loadMoreLockRef = useRef(false);

  const chartData = useMemo(() => uniqueAscByTime(toChartData(candles)), [candles]);
  const precision = useMemo(
    () => resolvePrecision(candles, pricePrecision),
    [candles, pricePrecision]
  );
  const emaData = useMemo(() => {
    if (indicatorData?.ema200?.length) {
      return indicatorData.ema200;
    }
    return calculateEma(chartData, 200);
  }, [indicatorData, chartData]);
  const bbands = useMemo(() => indicatorData?.bbands ?? null, [indicatorData]);
  const atrData = useMemo(() => indicatorData?.atr ?? [], [indicatorData]);
  const rsiData = useMemo(() => {
    if (indicatorData?.rsi?.length) {
      return indicatorData.rsi;
    }
    if (!chartData.length) return [];
    const values = calculateRsi(chartData.map((candle) => candle.close));
    return values.map((value, index) => ({ time: chartData[index].time, value }));
  }, [indicatorData, chartData]);
  const fibLevels = useMemo(() => calculateFibLevels(chartData), [chartData]);
  const divergenceMarkers = useMemo(() => detectDivergence(chartData), [chartData]);
  const supportLevels = useMemo(
    () => indicatorData?.support_resistance ?? [],
    [indicatorData]
  );
  const volumeData = useMemo(
    () =>
      candles.map((candle) => ({
        time: Math.floor(new Date(candle.open_time).getTime() / 1000),
        value: candle.volume,
        color: candle.close >= candle.open ? "rgba(34,197,94,0.45)" : "rgba(239,68,68,0.45)",
      })),
    [candles]
  );
  const patternMarkers = useMemo(() => {
    if (!indicatorData?.patterns) return [];
    return indicatorData.patterns.map((pattern) => ({
      time: pattern.time,
      position: pattern.signal > 0 ? "belowBar" : "aboveBar",
      color: pattern.signal > 0 ? "#38bdf8" : "#f97316",
      shape: "square",
      text: formatPatternLabel(pattern.name),
    }));
  }, [indicatorData]);
  const visibleChartPatterns = useMemo(() => {
    if (!indicatorData?.chart_patterns) return [];
    return indicatorData.chart_patterns.filter((pattern) =>
      showUnconfirmedPatterns ? true : pattern.confirmed
    );
  }, [indicatorData, showUnconfirmedPatterns]);
  const limitedPatternMarkers = useMemo(() => {
    if (!showCandlePatterns) return [];
    if (patternLimit <= 0) return [];
    let markers = patternMarkers;
    if (patternLimit < markers.length) {
      markers = markers.slice(-patternLimit);
    }
    const labelLimit = showPatternLabels ? Math.min(6, markers.length) : 0;
    return markers.map((marker, index) => {
      if (labelLimit === 0) {
        return { ...marker, text: "" };
      }
      if (index < markers.length - labelLimit) {
        return { ...marker, text: "" };
      }
      return marker;
    });
  }, [patternMarkers, showCandlePatterns, patternLimit, showPatternLabels]);
  const elliottMarkers = useMemo(() => {
    if (!indicatorData?.elliott) return [];
    return indicatorData.elliott.map((pivot) => ({
      time: pivot.time,
      position: pivot.kind === "low" ? "belowBar" : "aboveBar",
      color: pivot.kind === "low" ? "#facc15" : "#a855f7",
      shape: pivot.kind === "low" ? "arrowUp" : "arrowDown",
      text: pivot.kind === "low" ? "Elliott Низ" : "Elliott Верх",
    }));
  }, [indicatorData]);
  const chartPatternMarkers = useMemo(() => {
    if (!visibleChartPatterns.length) return [];
    return visibleChartPatterns.map((pattern) => ({
      time: pattern.time,
      position: pattern.direction === "short" ? "aboveBar" : "belowBar",
      color: pattern.direction === "short" ? "#fb7185" : "#38bdf8",
      shape: "circle",
      text: pattern.name ? pattern.name.replace(/_/g, " ").slice(0, 12) : "PAT",
    }));
  }, [visibleChartPatterns]);
  const patternLines = useMemo(() => {
    if (!visibleChartPatterns.length) return [];
    const lines = [];
    visibleChartPatterns.forEach((pattern) => {
      (pattern.lines || []).forEach((line) => {
        if (!Array.isArray(line.points) || line.points.length < 2) return;
        lines.push({
          points: line.points,
          color:
            line.color ||
            (pattern.direction === "short" ? "rgba(248, 113, 113, 0.6)" : "rgba(56, 189, 248, 0.6)"),
          style: line.style ?? 2,
        });
      });
    });
    return lines;
  }, [visibleChartPatterns]);
  const patternPolygons = useMemo(() => {
    if (!showPatternFill || !visibleChartPatterns.length) return [];
    const patterns = visibleChartPatterns.slice(-patternFillLimit);
    const polygons = [];
    patterns.forEach((pattern) => {
      const lines = (pattern.lines || []).filter(
        (line) => Array.isArray(line.points) && line.points.length >= 2
      );
      if (lines.length < 2) return;
      const ranked = lines
        .map((line) => {
          const avg =
            line.points.reduce((sum, pt) => sum + Number(pt.value || pt.price || 0), 0) /
            line.points.length;
          return { line, avg };
        })
        .sort((a, b) => b.avg - a.avg);
      const upper = ranked[0]?.line;
      const lower = ranked[ranked.length - 1]?.line;
      if (!upper || !lower) return;
      polygons.push({
        upper: upper.points,
        lower: lower.points,
        color:
          pattern.direction === "short"
            ? "rgba(248, 113, 113, 0.18)"
            : "rgba(34, 197, 94, 0.18)",
        stroke:
          pattern.direction === "short"
            ? "rgba(248, 113, 113, 0.4)"
            : "rgba(34, 197, 94, 0.4)",
      });
    });
    return polygons;
  }, [showPatternFill, visibleChartPatterns, patternFillLimit]);
  const tradePlanLevels = useMemo(() => {
    const plan = signals[0]?.meta?.trade_plan;
    if (!plan) return [];
    const levels = [];
    if (Number.isFinite(plan.entry)) {
      levels.push({ price: plan.entry, label: "Entry", color: "#38bdf8" });
    }
    if (Number.isFinite(plan.stop_loss)) {
      levels.push({ price: plan.stop_loss, label: "Stop", color: "#ef4444" });
    }
    if (Number.isFinite(plan.breakeven_at) && plan.breakeven_at !== plan.entry) {
      levels.push({ price: plan.breakeven_at, label: "BE", color: "#facc15" });
    }
    if (Array.isArray(plan.take_levels)) {
      plan.take_levels.forEach((level, index) => {
        if (!Number.isFinite(level)) return;
        levels.push({ price: level, label: `TP${index + 1}`, color: "#22c55e" });
      });
    } else if (Number.isFinite(plan.take_profit)) {
      levels.push({ price: plan.take_profit, label: "TP", color: "#22c55e" });
    }
    return levels;
  }, [signals]);
  const tradeExitMarkers = useMemo(() => {
    if (!showTradeExits || !tradeHistory.length) return [];
    const markers = [];
    tradeHistory.forEach((trade) => {
      const side = trade.side === "short" ? -1 : 1;
      (trade.tp_hits || []).forEach((hit) => {
        markers.push({
          time: hit.time,
          position: side > 0 ? "aboveBar" : "belowBar",
          color: "#22c55e",
          shape: "circle",
          text: `TP${hit.level}`,
        });
      });
      if (trade.exit_reason === "SL") {
        markers.push({
          time: trade.exit_time,
          position: side > 0 ? "belowBar" : "aboveBar",
          color: "#ef4444",
          shape: "arrowDown",
          text: "SL",
        });
      } else if (trade.exit_reason === "BE") {
        markers.push({
          time: trade.exit_time,
          position: "aboveBar",
          color: "#facc15",
          shape: "circle",
          text: "BE",
        });
      } else if (
        trade.exit_reason?.startsWith("TP") &&
        !(trade.tp_hits || []).some((hit) => `TP${hit.level}` === trade.exit_reason)
      ) {
        markers.push({
          time: trade.exit_time,
          position: side > 0 ? "aboveBar" : "belowBar",
          color: "#22c55e",
          shape: "arrowUp",
          text: trade.exit_reason,
        });
      }
    });
    return markers;
  }, [showTradeExits, tradeHistory]);

  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      layout: {
        background: { color: "transparent" },
        textColor: "#c6d3e0",
      },
      grid: {
        vertLines: { color: "rgba(255,255,255,0.05)" },
        horzLines: { color: "rgba(255,255,255,0.05)" },
      },
      rightPriceScale: {
        borderColor: "rgba(255,255,255,0.2)",
        scaleMargins: { top: 0.06, bottom: 0.32 },
      },
      timeScale: {
        borderColor: "rgba(255,255,255,0.2)",
      },
      crosshair: {
        mode: 1,
      },
      handleScroll: {
        mouseWheel: true,
        pressedMouseMove: true,
      },
      handleScale: {
        mouseWheel: true,
        pinch: true,
        axisPressedMouseMove: true,
      },
      height,
    });

    const candleSeries = chart.addCandlestickSeries({
      upColor: "#22c55e",
      downColor: "#ef4444",
      borderUpColor: "#22c55e",
      borderDownColor: "#ef4444",
      wickUpColor: "#22c55e",
      wickDownColor: "#ef4444",
      priceLineVisible: true,
      lastValueVisible: true,
    });

    const emaSeries = chart.addLineSeries({
      color: "#4ade80",
      lineWidth: 2,
    });

    const bbUpper = chart.addLineSeries({
      color: "rgba(59,130,246,0.6)",
      lineWidth: 1,
      lineStyle: 2,
    });
    const bbMiddle = chart.addLineSeries({
      color: "rgba(148,163,184,0.6)",
      lineWidth: 1,
      lineStyle: 2,
    });
    const bbLower = chart.addLineSeries({
      color: "rgba(59,130,246,0.6)",
      lineWidth: 1,
      lineStyle: 2,
    });

    const volumeSeries = chart.addHistogramSeries({
      priceScaleId: "volume",
      priceFormat: { type: "volume" },
      base: 0,
    });
    chart.priceScale("volume").applyOptions({
      scaleMargins: { top: 0.82, bottom: 0.02 },
      visible: true,
      borderColor: "rgba(255,255,255,0.2)",
    });

    const atrSeries = chart.addLineSeries({
      color: "#f59e0b",
      lineWidth: 1,
      priceScaleId: "atr",
    });
    chart.priceScale("atr").applyOptions({
      scaleMargins: { top: 0.72, bottom: 0.12 },
      visible: true,
      borderColor: "rgba(255,255,255,0.2)",
    });

    const rsiSeries = chart.addLineSeries({
      color: "#38bdf8",
      lineWidth: 1,
      priceScaleId: "rsi",
      priceLineVisible: false,
      lastValueVisible: false,
    });
    chart.priceScale("rsi").applyOptions({
      scaleMargins: { top: 0.62, bottom: 0.22 },
      visible: true,
      borderColor: "rgba(255,255,255,0.2)",
    });
    rsiSeries.applyOptions({
      autoscaleInfoProvider: () => ({
        priceRange: { minValue: 0, maxValue: 100 },
      }),
    });

    seriesRef.current = candleSeries;
    emaRef.current = emaSeries;
    bbUpperRef.current = bbUpper;
    bbMiddleRef.current = bbMiddle;
    bbLowerRef.current = bbLower;
    volumeRef.current = volumeSeries;
    atrRef.current = atrSeries;
    rsiRef.current = rsiSeries;
    chartRef.current = chart;

    return () => {
      chart.remove();
    };
  }, []);

  useEffect(() => {
    if (!seriesRef.current) return;
    seriesRef.current.setData(uniqueAscByTime(chartData));
    if (emaRef.current) {
      emaRef.current.setData(uniqueAscByTime(emaData));
      emaRef.current.applyOptions({ visible: showEma });
    }
    if (bbUpperRef.current) {
      bbUpperRef.current.setData(uniqueAscByTime(bbands?.upper ?? []));
      bbUpperRef.current.applyOptions({ visible: showBBands });
    }
    if (bbMiddleRef.current) {
      bbMiddleRef.current.setData(uniqueAscByTime(bbands?.middle ?? []));
      bbMiddleRef.current.applyOptions({ visible: showBBands });
    }
    if (bbLowerRef.current) {
      bbLowerRef.current.setData(uniqueAscByTime(bbands?.lower ?? []));
      bbLowerRef.current.applyOptions({ visible: showBBands });
    }
    if (volumeRef.current) {
      volumeRef.current.setData(uniqueAscByTime(volumeData));
      volumeRef.current.applyOptions({ visible: showVolume });
    }
    if (atrRef.current) {
      atrRef.current.setData(uniqueAscByTime(atrData));
      atrRef.current.applyOptions({ visible: showAtr });
    }
    if (rsiRef.current) {
      rsiRef.current.setData(uniqueAscByTime(rsiData));
      rsiRef.current.applyOptions({ visible: showRsi });
    }
  }, [
    chartData,
    emaData,
    bbands,
    volumeData,
    atrData,
    rsiData,
    showEma,
    showBBands,
    showVolume,
    showAtr,
    showRsi,
  ]);

  useEffect(() => {
    if (!chartRef.current) return;
    chartRef.current.applyOptions({ height });
  }, [height]);

  useEffect(() => {
    if (!chartRef.current || !containerRef.current) return;
    const resizeOverlay = () => {
      if (!overlayRef.current || !containerRef.current) return;
      const canvas = overlayRef.current;
      const dpr = window.devicePixelRatio || 1;
      const width = containerRef.current.clientWidth;
      const height = containerRef.current.clientHeight;
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
      canvas.width = Math.floor(width * dpr);
      canvas.height = Math.floor(height * dpr);
      const ctx = canvas.getContext("2d");
      if (ctx) {
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      }
    };

    const resizeObserver = new ResizeObserver(() => {
      if (!chartRef.current || !containerRef.current) return;
      chartRef.current.applyOptions({
        width: containerRef.current.clientWidth,
        height: containerRef.current.clientHeight,
      });
      resizeOverlay();
    });
    resizeObserver.observe(containerRef.current);
    resizeOverlay();
    return () => resizeObserver.disconnect();
  }, []);

  useEffect(() => {
    if (!chartRef.current) return;
    chartRef.current.priceScale("volume").applyOptions({ visible: showVolume });
    chartRef.current.priceScale("atr").applyOptions({ visible: showAtr });
    chartRef.current.priceScale("rsi").applyOptions({ visible: showRsi });
  }, [showVolume, showAtr, showRsi]);

  useEffect(() => {
    if (!seriesRef.current) return;
    const minMove = 1 / 10 ** precision;
    seriesRef.current.applyOptions({
      priceFormat: {
        type: "price",
        precision,
        minMove,
      },
    });
  }, [precision]);

  useEffect(() => {
    if (!seriesRef.current) return;
    const markers = [];
    if (showDivergence) {
      markers.push(...divergenceMarkers);
    }
    if (showCandlePatterns) {
      markers.push(...limitedPatternMarkers);
    }
    if (showElliott) {
      markers.push(...elliottMarkers);
    }
    if (showChartPatterns) {
      markers.push(...chartPatternMarkers);
    }
    if (showTradeExits) {
      markers.push(...tradeExitMarkers);
    }
    if (tradeMarkerMode === "trades" && tradeHistory.length) {
      tradeHistory.forEach((trade) => {
        if (!trade.entry_time) return;
        const side = trade.side === "short" ? -1 : 1;
        markers.push({
          time: trade.entry_time,
          position: side > 0 ? "belowBar" : "aboveBar",
          color: side > 0 ? "#22c55e" : "#ef4444",
          shape: side > 0 ? "arrowUp" : "arrowDown",
          text: side > 0 ? "ВХОД L" : "ВХОД S",
        });
      });
    }
    signals.forEach((item) => {
      markers.push({
        time: Math.floor(new Date(item.created_at).getTime() / 1000),
        position: item.signal_type === "long" ? "belowBar" : "aboveBar",
        color: item.signal_type === "long" ? "#22c55e" : "#ef4444",
        shape: item.signal_type === "long" ? "arrowUp" : "arrowDown",
        text: item.signal_type.toUpperCase(),
      });
    });
    seriesRef.current.setMarkers(uniqueAscByTime(markers));
  }, [
    signals,
    divergenceMarkers,
    limitedPatternMarkers,
    elliottMarkers,
    chartPatternMarkers,
    tradeExitMarkers,
    tradeHistory,
    tradeMarkerMode,
    showDivergence,
    showCandlePatterns,
    showElliott,
    showChartPatterns,
    showTradeExits,
  ]);

  useEffect(() => {
    if (!seriesRef.current) return;
    fibLinesRef.current.forEach((line) => seriesRef.current.removePriceLine(line));
    if (!showFib) {
      fibLinesRef.current = [];
      return;
    }
    fibLinesRef.current = fibLevels.map((level) =>
      seriesRef.current.createPriceLine({
        price: level.value,
        color: level.color,
        lineWidth: 1,
        lineStyle: 2,
        axisLabelVisible: true,
        title: `Fib ${level.label}`,
      })
    );
  }, [fibLevels, showFib]);

  useEffect(() => {
    if (!seriesRef.current) return;
    srLinesRef.current.forEach((line) => seriesRef.current.removePriceLine(line));
    if (!showSupportRes) {
      srLinesRef.current = [];
      return;
    }
    srLinesRef.current = supportLevels.map((level) =>
      seriesRef.current.createPriceLine({
        price: level,
        color: "rgba(148,163,184,0.5)",
        lineWidth: 1,
        lineStyle: 3,
        axisLabelVisible: true,
        title: "SR",
      })
    );
  }, [supportLevels, showSupportRes]);

  useEffect(() => {
    if (!seriesRef.current) return;
    planLinesRef.current.forEach((line) => seriesRef.current.removePriceLine(line));
    if (!showTradePlan) {
      planLinesRef.current = [];
      return;
    }
    planLinesRef.current = tradePlanLevels.map((level) =>
      seriesRef.current.createPriceLine({
        price: level.price,
        color: level.color,
        lineWidth: 1,
        lineStyle: 0,
        axisLabelVisible: true,
        title: level.label,
      })
    );
  }, [tradePlanLevels, showTradePlan]);

  useEffect(() => {
    if (!chartRef.current) return;
    patternLineRefs.current.forEach((series) => chartRef.current.removeSeries(series));
    if (!showChartPatterns) {
      patternLineRefs.current = [];
      return;
    }
    patternLineRefs.current = patternLines.map((line) => {
      const series = chartRef.current.addLineSeries({
        color: line.color,
        lineWidth: 2,
        lineStyle: line.style,
        priceLineVisible: false,
        lastValueVisible: false,
      });
      series.setData(uniqueAscByTime(line.points));
      return series;
    });
  }, [patternLines, showChartPatterns]);

  useEffect(() => {
    if (!chartRef.current || !overlayRef.current) return;
    const canvas = overlayRef.current;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const chart = chartRef.current;
    const timeScale = chart.timeScale();
    const priceScale = chart.priceScale("right");

    const priceToCoordinate = (price) => {
      if (seriesRef.current && typeof seriesRef.current.priceToCoordinate === "function") {
        return seriesRef.current.priceToCoordinate(price);
      }
      if (priceScale && typeof priceScale.priceToCoordinate === "function") {
        return priceScale.priceToCoordinate(price);
      }
      return null;
    };

    const draw = () => {
      const width = canvas.clientWidth;
      const height = canvas.clientHeight;
      ctx.clearRect(0, 0, width, height);

      if (showPatternFill && patternPolygons.length) {
        patternPolygons.forEach((polygon) => {
          const upperStart = polygon.upper[0];
          const upperEnd = polygon.upper[polygon.upper.length - 1];
          const lowerStart = polygon.lower[0];
          const lowerEnd = polygon.lower[polygon.lower.length - 1];
          if (!upperStart || !upperEnd || !lowerStart || !lowerEnd) return;

          const upperStartTime = upperStart.time;
          const upperEndTime = upperEnd.time;
          const lowerStartTime = lowerStart.time;
          const lowerEndTime = lowerEnd.time;

          if (!upperStartTime || !upperEndTime || !lowerStartTime || !lowerEndTime) return;

          const startX = timeScale.timeToCoordinate(upperStartTime);
          const endX = timeScale.timeToCoordinate(upperEndTime);
          if (startX === null || endX === null) return;

          for (let band = 0; band < patternFillBands; band += 1) {
            const ratioStart = band / patternFillBands;
            const ratioEnd = (band + 1) / patternFillBands;

            const startPriceA =
              Number(upperStart.value || upperStart.price) +
              (Number(lowerStart.value || lowerStart.price) - Number(upperStart.value || upperStart.price)) *
                ratioStart;
            const endPriceA =
              Number(upperEnd.value || upperEnd.price) +
              (Number(lowerEnd.value || lowerEnd.price) - Number(upperEnd.value || upperEnd.price)) *
                ratioStart;
            const startPriceB =
              Number(upperStart.value || upperStart.price) +
              (Number(lowerStart.value || lowerStart.price) - Number(upperStart.value || upperStart.price)) *
                ratioEnd;
            const endPriceB =
              Number(upperEnd.value || upperEnd.price) +
              (Number(lowerEnd.value || lowerEnd.price) - Number(upperEnd.value || upperEnd.price)) * ratioEnd;

            const yStartA = priceToCoordinate(startPriceA);
            const yEndA = priceToCoordinate(endPriceA);
            const yStartB = priceToCoordinate(startPriceB);
            const yEndB = priceToCoordinate(endPriceB);
            if (yStartA === null || yEndA === null || yStartB === null || yEndB === null) return;

            ctx.beginPath();
            ctx.moveTo(startX, yStartA);
            ctx.lineTo(endX, yEndA);
            ctx.lineTo(endX, yEndB);
            ctx.lineTo(startX, yStartB);
            ctx.closePath();
            ctx.fillStyle = polygon.color;
            ctx.fill();
          }

          ctx.beginPath();
          const upperYStart = priceToCoordinate(
            Number(upperStart.value || upperStart.price)
          );
          const upperYEnd = priceToCoordinate(Number(upperEnd.value || upperEnd.price));
          const lowerYStart = priceToCoordinate(
            Number(lowerStart.value || lowerStart.price)
          );
          const lowerYEnd = priceToCoordinate(Number(lowerEnd.value || lowerEnd.price));
          if (
            upperYStart === null ||
            upperYEnd === null ||
            lowerYStart === null ||
            lowerYEnd === null
          ) {
            return;
          }
          ctx.strokeStyle = polygon.stroke;
          ctx.lineWidth = 1;
          ctx.moveTo(startX, upperYStart);
          ctx.lineTo(endX, upperYEnd);
          ctx.moveTo(startX, lowerYStart);
          ctx.lineTo(endX, lowerYEnd);
          ctx.stroke();
        });
      }

      if (showTradePaths && tradeHistory.length) {
        tradeHistory.forEach((trade) => {
          if (!trade.entry_time || !trade.exit_time) return;
          const startX = timeScale.timeToCoordinate(trade.entry_time);
          const endX = timeScale.timeToCoordinate(trade.exit_time);
          const startY = priceToCoordinate(trade.entry);
          const endY = priceToCoordinate(trade.exit_price);
          if (startX === null || endX === null || startY === null || endY === null) return;
          ctx.beginPath();
          ctx.moveTo(startX, startY);
          ctx.lineTo(endX, endY);
          ctx.strokeStyle = trade.pnl >= 0 ? "rgba(34, 197, 94, 0.45)" : "rgba(239, 68, 68, 0.45)";
          ctx.lineWidth = 1;
          ctx.setLineDash([4, 4]);
          ctx.stroke();
          ctx.setLineDash([]);
        });
      }
    };

    const scheduleDraw = () => {
      window.requestAnimationFrame(draw);
    };

    draw();
    if (typeof timeScale.subscribeVisibleTimeRangeChange === "function") {
      timeScale.subscribeVisibleTimeRangeChange(scheduleDraw);
    }
    if (typeof chart.subscribeCrosshairMove === "function") {
      chart.subscribeCrosshairMove(scheduleDraw);
    }
    if (typeof chart.subscribeClick === "function") {
      chart.subscribeClick(scheduleDraw);
    }
    const container = containerRef.current;
    if (container) {
      container.addEventListener("wheel", scheduleDraw, { passive: true });
      container.addEventListener("pointermove", scheduleDraw);
      container.addEventListener("pointerdown", scheduleDraw);
      container.addEventListener("pointerup", scheduleDraw);
    }

    return () => {
      if (typeof timeScale.unsubscribeVisibleTimeRangeChange === "function") {
        timeScale.unsubscribeVisibleTimeRangeChange(scheduleDraw);
      }
      if (typeof chart.unsubscribeCrosshairMove === "function") {
        chart.unsubscribeCrosshairMove(scheduleDraw);
      }
      if (typeof chart.unsubscribeClick === "function") {
        chart.unsubscribeClick(scheduleDraw);
      }
      if (container) {
        container.removeEventListener("wheel", scheduleDraw);
        container.removeEventListener("pointermove", scheduleDraw);
        container.removeEventListener("pointerdown", scheduleDraw);
        container.removeEventListener("pointerup", scheduleDraw);
      }
    };
  }, [patternPolygons, showPatternFill, patternFillBands, showTradePaths, tradeHistory]);

  useEffect(() => {
    if (!chartRef.current) return;
    if (dataKey && dataKey !== lastDataKeyRef.current) {
      chartRef.current.timeScale().fitContent();
      lastDataKeyRef.current = dataKey;
    }
  }, [dataKey]);

  useEffect(() => {
    if (!chartRef.current) return;
    if (autoFit && chartData.length) {
      chartRef.current.timeScale().fitContent();
    }
  }, [autoFit, chartData]);

  useEffect(() => {
    if (!chartRef.current) return;
    if (fitRequest > 0) {
      chartRef.current.timeScale().fitContent();
    }
  }, [fitRequest]);

  useEffect(() => {
    if (!chartRef.current || !onLoadMoreCandles) return;
    if (!candles.length) return;
    const earliestIso = candles[0].open_time;
    if (!earliestIso) return;

    const earliestEpoch = Math.floor(new Date(earliestIso).getTime() / 1000);
    const chart = chartRef.current;
    const timeScale = chart.timeScale();

    const maybeLoadMore = () => {
      if (loadMoreLockRef.current) return;
      const range = timeScale.getVisibleRange?.();
      if (!range) return;
      const from = typeof range.from === "number" ? range.from : null;
      if (from === null) return;

      // When user scrolls close to the left edge, pull older candles.
      if (from <= earliestEpoch + 5) {
        loadMoreLockRef.current = true;
        Promise.resolve(onLoadMoreCandles(earliestIso)).finally(() => {
          window.setTimeout(() => {
            loadMoreLockRef.current = false;
          }, 800);
        });
      }
    };

    if (typeof timeScale.subscribeVisibleTimeRangeChange === "function") {
      timeScale.subscribeVisibleTimeRangeChange(maybeLoadMore);
    }
    return () => {
      if (typeof timeScale.unsubscribeVisibleTimeRangeChange === "function") {
        timeScale.unsubscribeVisibleTimeRangeChange(maybeLoadMore);
      }
    };
  }, [candles, onLoadMoreCandles]);

  return (
    <div className="chart-panel" ref={containerRef} style={{ height }}>
      <canvas className="chart-overlay" ref={overlayRef} />
    </div>
  );
}
