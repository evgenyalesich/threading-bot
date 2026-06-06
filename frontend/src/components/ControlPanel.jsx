function formatNumber(value, digits = 2) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "--";
  return numeric.toLocaleString("ru-RU", {
    minimumFractionDigits: 0,
    maximumFractionDigits: digits,
  });
}

function formatSignedPercent(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "--";
  const prefix = numeric > 0 ? "+" : "";
  return `${prefix}${numeric.toFixed(2)}%`;
}

function modeDescription(mode) {
  return mode === "auto"
    ? "Бот сам входит, ставит защиту и ведет сделку."
    : "Бот ищет входы, а ты подтверждаешь сделку вручную.";
}

function strategyLabel(strategy) {
  return {
    adaptive_pattern_confluence: "Adaptive Pattern + EMA/Fib",
    three_screens: "Три экрана Элдера",
    ema200_fib_divergence: "EMA200 + Фибо + Дивергенция",
  }[strategy] || strategy;
}

export default function ControlPanel({
  lookbackDays,
  market,
  dataEnv,
  tradeEnv,
  quantity,
  quoteAmount,
  autoQuantity,
  attachOrders,
  autoBreakeven,
  leverage,
  sidebarWidth,
  chartHeight,
  showSidePanel,
  showEma,
  showFib,
  showDivergence,
  showCandlePatterns,
  showChartPatterns,
  showElliott,
  showSupportRes,
  showTradePlan,
  showBBands,
  showVolume,
  showAtr,
  showRsi,
  showPatternLabels,
  patternLimit,
  showPatternFill,
  patternFillBands,
  patternFillLimit,
  showUnconfirmedPatterns,
  showTradeExits,
  tradeHistoryLimit,
  showTradePaths,
  chartBars,
  backfillStride,
  backfillMaxBars,
  autoFit,
  minConfidence,
  strategy,
  minConfirmations,
  requirePattern,
  requireDivergence,
  requireCandle,
  requireVolumeConfirm,
  requireTrendFilter,
  confluenceTolerance,
  onLookbackChange,
  onMarketChange,
  onDataEnvChange,
  onTradeEnvChange,
  onQuantityChange,
  onQuoteAmountChange,
  onAutoQuantityChange,
  onAttachOrdersChange,
  onAutoBreakevenChange,
  onLeverageChange,
  onSidebarWidthChange,
  onChartHeightChange,
  onShowSidePanelChange,
  onShowEmaChange,
  onShowFibChange,
  onShowDivergenceChange,
  onShowCandlePatternsChange,
  onShowChartPatternsChange,
  onShowElliottChange,
  onShowSupportResChange,
  onShowTradePlanChange,
  onShowBBandsChange,
  onShowVolumeChange,
  onShowAtrChange,
  onShowRsiChange,
  onShowPatternLabelsChange,
  onPatternLimitChange,
  onShowPatternFillChange,
  onPatternFillBandsChange,
  onPatternFillLimitChange,
  onShowUnconfirmedPatternsChange,
  onShowTradeExitsChange,
  onTradeHistoryLimitChange,
  onShowTradePathsChange,
  onChartBarsChange,
  onBackfillStrideChange,
  onBackfillMaxBarsChange,
  onAutoFitChange,
  onMinConfidenceChange,
  onStrategyChange,
  onMinConfirmationsChange,
  onRequirePatternChange,
  onRequireDivergenceChange,
  onRequireCandleChange,
  onRequireVolumeConfirmChange,
  onRequireTrendFilterChange,
  onConfluenceToleranceChange,
  h1Timeframe,
  onH1TimeframeChange,
  trendTimeframe,
  onTrendTimeframeChange,
  onBacktest,
  backtestRunning,
  onSync,
  onAnalyze,
  mode,
  onModeChange,
  onOpenConfirmOrder,
  canConfirmOrder,
  status,
  wsConnected,
  tradeWsConnected,
  feedSource,
  autoSyncRunning,
  lastSyncLabel,
  currentPair,
  currentPrice,
  latestSignal,
  latestActiveOrder,
  positionRoi,
  chartStopInput,
  chartTakeInput,
  onChartStopInputChange,
  onChartTakeInputChange,
  onMoveStopToBreakeven,
  onMoveStopToPrice,
  onMoveTakeToPrice,
  onCloseOrder,
  onNudgeChartStop,
  onNudgeChartTake,
}) {
  const signalPlan = latestSignal?.meta?.trade_plan ?? {};
  const signalConfidence = Number(latestSignal?.confidence);
  const currentMode = mode === "auto" ? "Автомат" : "Полуавтомат";
  const positionSide = latestActiveOrder?.side || latestSignal?.signal_type?.toUpperCase() || "--";

  return (
    <div className="control-panel cockpit-panel">
      <section className="cockpit-hero">
        <div className="cockpit-hero-head">
          <div>
            <p className="cockpit-eyebrow">Trading cockpit</p>
            <h3>{currentPair?.base_asset ? `${currentPair.base_asset}/${currentPair.quote_asset}` : currentPair?.symbol || "Инструмент"}</h3>
          </div>
          <span className={`cockpit-status ${mode === "auto" ? "auto" : "semi"}`}>{currentMode}</span>
        </div>
        <p className="cockpit-hero-copy">{modeDescription(mode)}</p>
        <div className="cockpit-chip-row">
          <span>{market === "futures" ? "Futures" : "Spot"}</span>
          <span>{tradeEnv === "real" ? "Real trade" : "Testnet trade"}</span>
          <span>{dataEnv === "real" ? "Real feed" : "Testnet feed"}</span>
          <span>{strategyLabel(strategy)}</span>
        </div>
        <div className="mode-switcher">
          <button
            type="button"
            className={mode === "semi" ? "active" : ""}
            onClick={() => onModeChange("semi")}
          >
            SEMI
          </button>
          <button
            type="button"
            className={mode === "auto" ? "active" : ""}
            onClick={() => onModeChange("auto")}
          >
            AUTO
          </button>
        </div>
      </section>

      <section className="cockpit-section">
        <div className="section-heading">
          <strong>Состояние системы</strong>
          <span>{status || "Ожидание"}</span>
        </div>
        <div className="cockpit-stats-grid">
          <div className="mini-stat">
            <span>Поток графика</span>
            <strong className={wsConnected ? "positive" : "negative"}>{wsConnected ? "online" : "offline"}</strong>
          </div>
          <div className="mini-stat">
            <span>Поток ордеров</span>
            <strong className={tradeWsConnected ? "positive" : "negative"}>{tradeWsConnected ? "online" : "offline"}</strong>
          </div>
          <div className="mini-stat">
            <span>История</span>
            <strong>{autoSyncRunning ? "syncing" : "ready"}</strong>
          </div>
          <div className="mini-stat">
            <span>Feed</span>
            <strong>{feedSource || "--"}</strong>
          </div>
        </div>
        <div className="system-footnote">Последняя синхронизация: {lastSyncLabel || "--"}</div>
      </section>

      <section className="cockpit-section">
        <div className="section-heading">
          <strong>Контекст сделки</strong>
          <span>{h1Timeframe} / {trendTimeframe}</span>
        </div>
        <div className="cockpit-signal-card">
          <div className="signal-strip">
            <div>
              <span className="signal-strip-label">Цена</span>
              <strong>{formatNumber(currentPrice, 6)}</strong>
            </div>
            <div>
              <span className="signal-strip-label">Сторона</span>
              <strong>{positionSide}</strong>
            </div>
            <div>
              <span className="signal-strip-label">Confidence</span>
              <strong>{Number.isFinite(signalConfidence) ? `${Math.round(signalConfidence * 100)}%` : "--"}</strong>
            </div>
          </div>
          <div className="signal-strip secondary">
            <div>
              <span className="signal-strip-label">Entry</span>
              <strong>{formatNumber(signalPlan.entry ?? latestSignal?.entry_price, 6)}</strong>
            </div>
            <div>
              <span className="signal-strip-label">SL</span>
              <strong>{formatNumber(signalPlan.stop_loss ?? latestSignal?.stop_loss, 6)}</strong>
            </div>
            <div>
              <span className="signal-strip-label">TP</span>
              <strong>{formatNumber(signalPlan.take_profit ?? latestSignal?.take_profit, 6)}</strong>
            </div>
          </div>
          {latestSignal?.rationale ? <p className="signal-context-copy">{latestSignal.rationale}</p> : null}
          {canConfirmOrder ? (
            <button className="primary cockpit-confirm-btn" onClick={onOpenConfirmOrder}>
              Подтвердить вход {latestSignal?.signal_type?.toUpperCase()}
            </button>
          ) : null}
        </div>
      </section>

      <section className="cockpit-section">
        <div className="section-heading">
          <strong>Позиция</strong>
          <span>{latestActiveOrder ? "живая" : "нет открытой"}</span>
        </div>
        {latestActiveOrder ? (
          <div className="position-workbench">
            <div className="position-overview">
              <div>
                <span className="signal-strip-label">Ордер</span>
                <strong>{latestActiveOrder.symbol} · {latestActiveOrder.side}</strong>
              </div>
              <div>
                <span className="signal-strip-label">PnL / ROI</span>
                <strong className={Number(positionRoi) >= 0 ? "positive" : "negative"}>{formatSignedPercent(positionRoi)}</strong>
              </div>
            </div>
            <div className="signal-strip secondary">
              <div>
                <span className="signal-strip-label">Entry</span>
                <strong>{formatNumber(latestActiveOrder.price, 6)}</strong>
              </div>
              <div>
                <span className="signal-strip-label">SL</span>
                <strong>{formatNumber(latestActiveOrder.stop_loss, 6)}</strong>
              </div>
              <div>
                <span className="signal-strip-label">TP</span>
                <strong>{formatNumber(latestActiveOrder.take_profit, 6)}</strong>
              </div>
            </div>
            <div className="position-grid">
              <div className="position-field">
                <label>Stop Loss</label>
                <div className="inline-adjuster">
                  <button type="button" className="ghost mini" onClick={() => onNudgeChartStop(-1)}>-</button>
                  <input
                    value={chartStopInput}
                    onChange={(event) => onChartStopInputChange(event.target.value)}
                    placeholder="Новый SL"
                  />
                  <button type="button" className="ghost mini" onClick={() => onNudgeChartStop(1)}>+</button>
                </div>
                <button
                  type="button"
                  className="primary"
                  onClick={() => onMoveStopToPrice(latestActiveOrder, Number(chartStopInput))}
                >
                  Применить SL
                </button>
              </div>
              <div className="position-field">
                <label>Take Profit</label>
                <div className="inline-adjuster">
                  <button type="button" className="ghost mini" onClick={() => onNudgeChartTake(-1)}>-</button>
                  <input
                    value={chartTakeInput}
                    onChange={(event) => onChartTakeInputChange(event.target.value)}
                    placeholder="Новый TP"
                  />
                  <button type="button" className="ghost mini" onClick={() => onNudgeChartTake(1)}>+</button>
                </div>
                <button
                  type="button"
                  className="primary"
                  onClick={() => onMoveTakeToPrice(latestActiveOrder, Number(chartTakeInput))}
                >
                  Применить TP
                </button>
              </div>
            </div>
            <div className="control-actions stacked">
              <button className="ghost" onClick={() => onMoveStopToBreakeven(latestActiveOrder)}>
                Перенести SL в BE
              </button>
              <button className="danger-button" onClick={() => onCloseOrder(latestActiveOrder)}>
                Закрыть позицию
              </button>
            </div>
          </div>
        ) : (
          <div className="empty-state compact-empty">Открытой позиции по выбранному инструменту сейчас нет.</div>
        )}
      </section>

      <section className="cockpit-section">
        <div className="section-heading">
          <strong>Исполнение</strong>
          <span>Базовые настройки</span>
        </div>
        <div className="control-grid two">
          <div className="control-group">
            <label>Рынок</label>
            <select value={market} onChange={(event) => onMarketChange(event.target.value)}>
              <option value="spot">Спот</option>
              <option value="futures">Фьючерсы</option>
            </select>
          </div>
          <div className="control-group">
            <label>Глубина (дней)</label>
            <input
              type="number"
              value={lookbackDays}
              onChange={(event) => onLookbackChange(Number(event.target.value))}
            />
          </div>
          <div className="control-group">
            <label>Источник данных</label>
            <div className="segmented-toggle">
              <button type="button" className={dataEnv === "real" ? "active" : ""} onClick={() => onDataEnvChange("real")}>Реал</button>
              <button type="button" className={dataEnv === "testnet" ? "active" : ""} onClick={() => onDataEnvChange("testnet")}>Тестнет</button>
            </div>
          </div>
          <div className="control-group">
            <label>Источник торговли</label>
            <div className="segmented-toggle">
              <button type="button" className={tradeEnv === "real" ? "active" : ""} onClick={() => onTradeEnvChange("real")}>Реал</button>
              <button type="button" className={tradeEnv === "testnet" ? "active" : ""} onClick={() => onTradeEnvChange("testnet")}>Тестнет</button>
            </div>
          </div>
          <div className="control-group">
            <label>Количество</label>
            <input
              type="number"
              step="0.0001"
              value={quantity}
              disabled={autoQuantity}
              onChange={(event) => {
                const value = Number(event.target.value);
                onQuantityChange(Number.isFinite(value) ? value : 0);
              }}
            />
          </div>
          <div className="control-group">
            <label>{market === "futures" ? "Маржа на сделку ($)" : "Сумма сделки ($)"}</label>
            <input
              type="number"
              step="0.01"
              value={quoteAmount}
              disabled={!autoQuantity}
              onChange={(event) => onQuoteAmountChange(Number(event.target.value) || 0)}
            />
          </div>
          {market === "futures" ? (
            <div className="control-group">
              <label>Плечо</label>
              <input
                type="number"
                min="1"
                max="125"
                value={leverage}
                onChange={(event) => onLeverageChange(Number(event.target.value) || 1)}
              />
            </div>
          ) : null}
        </div>
        <div className="toggle-grid">
          <label className="toggle-row"><input type="checkbox" checked={autoQuantity} onChange={(event) => onAutoQuantityChange(event.target.checked)} /><span>Авто-расчет по сумме</span></label>
          <label className="toggle-row"><input type="checkbox" checked={attachOrders} onChange={(event) => onAttachOrdersChange(event.target.checked)} /><span>Ставить SL/TP сразу</span></label>
          <label className="toggle-row"><input type="checkbox" checked={autoBreakeven} onChange={(event) => onAutoBreakevenChange(event.target.checked)} /><span>Авто BE после TP1</span></label>
        </div>
        <div className="control-actions">
          <button className="ghost" onClick={onSync}>Синхронизировать</button>
          <button className="primary" onClick={onAnalyze}>Запуск анализа</button>
        </div>
        <button className="ghost full-width" onClick={onBacktest} disabled={backtestRunning}>
          {backtestRunning ? "Бэктест..." : "Запуск бэктеста"}
        </button>
      </section>

      <details className="control-section" open>
        <summary>Фильтры стратегии</summary>
        <div className="control-grid two">
          <div className="control-group">
            <label>Стратегия</label>
            <select value={strategy} onChange={(event) => onStrategyChange(event.target.value)}>
              <option value="adaptive_pattern_confluence">Adaptive Pattern + EMA/Fib</option>
              <option value="three_screens">Три экрана Элдера</option>
              <option value="ema200_fib_divergence">EMA200 + Фибо + Дивергенция</option>
            </select>
          </div>
          <div className="control-group">
            <label>Трендовый ТФ</label>
            <select value={trendTimeframe} onChange={(e) => onTrendTimeframeChange(e.target.value)}>
              <option value="4h">4h</option>
              <option value="1d">1d</option>
              <option value="1h">1h</option>
            </select>
          </div>
          <div className="control-group">
            <label>ТФ входа</label>
            <select value={h1Timeframe} onChange={(e) => onH1TimeframeChange(e.target.value)}>
              <option value="1h">1h</option>
              <option value="4h">4h</option>
              <option value="15m">15m</option>
            </select>
          </div>
          <div className="control-group">
            <label>Мин. уверенность</label>
            <input
              type="number"
              step="0.01"
              min="0"
              max="1"
              value={minConfidence}
              onChange={(event) => onMinConfidenceChange(Number(event.target.value) || 0)}
            />
          </div>
          <div className="control-group">
            <label>Мин. подтверждений</label>
            <input
              type="number"
              step="1"
              min="0"
              max="6"
              value={minConfirmations}
              onChange={(event) => onMinConfirmationsChange(Number(event.target.value) || 0)}
            />
          </div>
          <div className="control-group">
            <label>EMA/Fib tolerance</label>
            <input
              type="number"
              step="0.001"
              min="0"
              max="0.05"
              value={confluenceTolerance}
              onChange={(event) => onConfluenceToleranceChange(Number(event.target.value) || 0)}
            />
            <small>0 = динамически по ATR</small>
          </div>
        </div>
        <div className="toggle-grid">
          <label className="toggle-row"><input type="checkbox" checked={requireTrendFilter} onChange={(event) => onRequireTrendFilterChange(event.target.checked)} /><span>Требовать тренд EMA200/26</span></label>
          <label className="toggle-row"><input type="checkbox" checked={requirePattern} onChange={(event) => onRequirePatternChange(event.target.checked)} /><span>Требовать фигуру</span></label>
          <label className="toggle-row"><input type="checkbox" checked={requireDivergence} onChange={(event) => onRequireDivergenceChange(event.target.checked)} /><span>Требовать дивергенцию</span></label>
          <label className="toggle-row"><input type="checkbox" checked={requireCandle} onChange={(event) => onRequireCandleChange(event.target.checked)} /><span>Требовать свечной паттерн</span></label>
          <label className="toggle-row"><input type="checkbox" checked={requireVolumeConfirm} onChange={(event) => onRequireVolumeConfirmChange(event.target.checked)} /><span>Требовать объем</span></label>
        </div>
      </details>

      <details className="control-section">
        <summary>Вид графика</summary>
        <div className="toggle-grid">
          <label className="toggle-row"><input type="checkbox" checked={autoFit} onChange={(e) => onAutoFitChange(e.target.checked)} /><span>Авто-вписывание</span></label>
          <label className="toggle-row"><input type="checkbox" checked={showEma} onChange={(e) => onShowEmaChange(e.target.checked)} /><span>EMA200</span></label>
          <label className="toggle-row"><input type="checkbox" checked={showFib} onChange={(e) => onShowFibChange(e.target.checked)} /><span>Фибо</span></label>
          <label className="toggle-row"><input type="checkbox" checked={showDivergence} onChange={(e) => onShowDivergenceChange(e.target.checked)} /><span>Дивергенция</span></label>
          <label className="toggle-row"><input type="checkbox" checked={showCandlePatterns} onChange={(e) => onShowCandlePatternsChange(e.target.checked)} /><span>Свечные паттерны</span></label>
          <label className="toggle-row"><input type="checkbox" checked={showChartPatterns} onChange={(e) => onShowChartPatternsChange(e.target.checked)} /><span>Фигуры линиями</span></label>
          <label className="toggle-row"><input type="checkbox" checked={showPatternFill} onChange={(e) => onShowPatternFillChange(e.target.checked)} /><span>Заливка фигур</span></label>
          <label className="toggle-row"><input type="checkbox" checked={showPatternLabels} onChange={(e) => onShowPatternLabelsChange(e.target.checked)} /><span>Подписи паттернов</span></label>
          <label className="toggle-row"><input type="checkbox" checked={showUnconfirmedPatterns} onChange={(e) => onShowUnconfirmedPatternsChange(e.target.checked)} /><span>Неподтвержденные фигуры</span></label>
          <label className="toggle-row"><input type="checkbox" checked={showElliott} onChange={(e) => onShowElliottChange(e.target.checked)} /><span>Pivot Elliott</span></label>
          <label className="toggle-row"><input type="checkbox" checked={showSupportRes} onChange={(e) => onShowSupportResChange(e.target.checked)} /><span>Поддержка/сопротивление</span></label>
          <label className="toggle-row"><input type="checkbox" checked={showTradePlan} onChange={(e) => onShowTradePlanChange(e.target.checked)} /><span>Линии сделки</span></label>
          <label className="toggle-row"><input type="checkbox" checked={showBBands} onChange={(e) => onShowBBandsChange(e.target.checked)} /><span>BBands</span></label>
          <label className="toggle-row"><input type="checkbox" checked={showVolume} onChange={(e) => onShowVolumeChange(e.target.checked)} /><span>Объем</span></label>
          <label className="toggle-row"><input type="checkbox" checked={showAtr} onChange={(e) => onShowAtrChange(e.target.checked)} /><span>ATR</span></label>
          <label className="toggle-row"><input type="checkbox" checked={showRsi} onChange={(e) => onShowRsiChange(e.target.checked)} /><span>RSI</span></label>
          <label className="toggle-row"><input type="checkbox" checked={showTradeExits} onChange={(e) => onShowTradeExitsChange(e.target.checked)} /><span>Выходы сделок</span></label>
          <label className="toggle-row"><input type="checkbox" checked={showTradePaths} onChange={(e) => onShowTradePathsChange(e.target.checked)} /><span>Траектория сделки</span></label>
        </div>
        <div className="control-grid two">
          <div className="control-group">
            <label>Метки паттернов</label>
            <input type="range" min="0" max="60" step="5" value={patternLimit} onChange={(event) => onPatternLimitChange(Number(event.target.value))} />
          </div>
          <div className="control-group">
            <label>Pattern fill bands</label>
            <input type="range" min="2" max="8" step="1" value={patternFillBands} onChange={(event) => onPatternFillBandsChange(Number(event.target.value))} />
          </div>
          <div className="control-group">
            <label>Pattern fill count</label>
            <input type="range" min="1" max="8" step="1" value={patternFillLimit} onChange={(event) => onPatternFillLimitChange(Number(event.target.value))} />
          </div>
          <div className="control-group">
            <label>Метки истории</label>
            <input type="range" min="5" max="60" step="5" value={tradeHistoryLimit} onChange={(event) => onTradeHistoryLimitChange(Number(event.target.value))} />
          </div>
          <div className="control-group">
            <label>Свечей на графике</label>
            <input type="range" min="200" max="5000" step="200" value={chartBars} onChange={(event) => onChartBarsChange(Number(event.target.value))} />
          </div>
          <div className="control-group">
            <label>Шаг бэкофила</label>
            <input type="number" min="1" max="10" value={backfillStride} onChange={(event) => onBackfillStrideChange(Number(event.target.value) || 1)} />
          </div>
          <div className="control-group">
            <label>Макс. свечей бэкофила</label>
            <input type="number" min="200" max="10000" value={backfillMaxBars} onChange={(event) => onBackfillMaxBarsChange(Number(event.target.value) || 1000)} />
          </div>
          <div className="control-group">
            <label>Ширина панели</label>
            <input type="range" min="280" max="520" step="10" value={sidebarWidth} onChange={(event) => onSidebarWidthChange(Number(event.target.value))} />
          </div>
          <div className="control-group">
            <label>Высота графика</label>
            <input type="range" min="420" max="820" step="20" value={chartHeight} onChange={(event) => onChartHeightChange(Number(event.target.value))} />
          </div>
        </div>
        <label className="toggle-row">
          <input type="checkbox" checked={showSidePanel} onChange={(event) => onShowSidePanelChange(event.target.checked)} />
          <span>Показывать боковые панели</span>
        </label>
      </details>
    </div>
  );
}
