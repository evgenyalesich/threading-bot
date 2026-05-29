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
  minConfirmations,
  requirePattern,
  requireDivergence,
  requireCandle,
  requireVolumeConfirm,
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
  onMinConfirmationsChange,
  onRequirePatternChange,
  onRequireDivergenceChange,
  onRequireCandleChange,
  onRequireVolumeConfirmChange,
  h1Timeframe,
  onH1TimeframeChange,
  trendTimeframe,
  onTrendTimeframeChange,
  onBacktest,
  backtestRunning,
  onSync,
  onAnalyze,
  mode,
  onModeToggle,
}) {
  return (
    <div className="control-panel">
      <div className="control-group">
        <label>Рынок</label>
        <select value={market} onChange={(event) => onMarketChange(event.target.value)}>
          <option value="spot">Спот</option>
          <option value="futures">Фьючерсы</option>
        </select>
      </div>
      <div className="control-group">
        <label>Источник данных</label>
        <div className="segmented-toggle">
          <button
            type="button"
            className={dataEnv === "real" ? "active" : ""}
            onClick={() => onDataEnvChange("real")}
          >
            Реал
          </button>
          <button
            type="button"
            className={dataEnv === "testnet" ? "active" : ""}
            onClick={() => onDataEnvChange("testnet")}
          >
            Тестнет
          </button>
        </div>
      </div>
      <div className="control-group">
        <label>Источник торговли</label>
        <div className="segmented-toggle">
          <button
            type="button"
            className={tradeEnv === "real" ? "active" : ""}
            onClick={() => onTradeEnvChange("real")}
          >
            Реал
          </button>
          <button
            type="button"
            className={tradeEnv === "testnet" ? "active" : ""}
            onClick={() => onTradeEnvChange("testnet")}
          >
            Тестнет
          </button>
        </div>
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
      <label className="toggle-row">
        <input
          type="checkbox"
          checked={autoQuantity}
          onChange={(event) => onAutoQuantityChange(event.target.checked)}
        />
        <span>Авто-расчет по сумме</span>
      </label>
      <div className="control-group">
        <label>Сумма ($)</label>
        <input
          type="number"
          step="0.01"
          value={quoteAmount}
          disabled={!autoQuantity}
          onChange={(event) => onQuoteAmountChange(Number(event.target.value) || 0)}
        />
      </div>
      <label className="toggle-row">
        <input
          type="checkbox"
          checked={attachOrders}
          onChange={(event) => onAttachOrdersChange(event.target.checked)}
        />
        <span>Прикрепить SL/TP</span>
      </label>
      <label className="toggle-row">
        <input
          type="checkbox"
          checked={autoBreakeven}
          onChange={(event) => onAutoBreakevenChange(event.target.checked)}
        />
        <span>Авто перенос SL в БУ (по TP1)</span>
      </label>
      <details className="control-section" open>
        <summary>Три экрана (стратегия)</summary>
        <div className="control-group">
          <label>Тренд (Экран 1 — 4H)</label>
          <select value={trendTimeframe} onChange={(e) => onTrendTimeframeChange(e.target.value)}>
            <option value="4h">4h</option>
            <option value="1d">1d</option>
            <option value="1h">1h</option>
          </select>
        </div>
        <div className="control-group">
          <label>Вход (Экраны 2+3 — 1H)</label>
          <select value={h1Timeframe} onChange={(e) => onH1TimeframeChange(e.target.value)}>
            <option value="1h">1h</option>
            <option value="4h">4h</option>
            <option value="15m">15m</option>
          </select>
        </div>
      </details>
      <div className="control-actions">
        <button className="ghost" onClick={onSync}>
          Синхронизировать историю
        </button>
        <button className="primary" onClick={onAnalyze}>
          Запуск анализа
        </button>
        <button className="ghost" onClick={onBacktest} disabled={backtestRunning}>
          {backtestRunning ? "Бэктест..." : "Запуск бэктеста"}
        </button>
      </div>
      <details className="control-section">
        <summary>Фильтры сигналов</summary>
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
        <label className="toggle-row">
          <input
            type="checkbox"
            checked={requirePattern}
            onChange={(event) => onRequirePatternChange(event.target.checked)}
          />
          <span>Требовать фигуру</span>
        </label>
        <label className="toggle-row">
          <input
            type="checkbox"
            checked={requireDivergence}
            onChange={(event) => onRequireDivergenceChange(event.target.checked)}
          />
          <span>Требовать дивергенцию</span>
        </label>
        <label className="toggle-row">
          <input
            type="checkbox"
            checked={requireCandle}
            onChange={(event) => onRequireCandleChange(event.target.checked)}
          />
          <span>Требовать свечной паттерн</span>
        </label>
        <label className="toggle-row">
          <input
            type="checkbox"
            checked={requireVolumeConfirm}
            onChange={(event) => onRequireVolumeConfirmChange(event.target.checked)}
          />
          <span>Требовать подтверждение объемом</span>
        </label>
      </details>
      <details className="control-section">
        <summary>Слои графика</summary>
        <label className="toggle-row">
          <input type="checkbox" checked={autoFit} onChange={(e) => onAutoFitChange(e.target.checked)} />
          <span>Авто-вписывание</span>
        </label>
        <label className="toggle-row">
          <input type="checkbox" checked={showEma} onChange={(e) => onShowEmaChange(e.target.checked)} />
          <span>EMA200</span>
        </label>
        <label className="toggle-row">
          <input type="checkbox" checked={showFib} onChange={(e) => onShowFibChange(e.target.checked)} />
          <span>Фибоначчи</span>
        </label>
        <label className="toggle-row">
          <input
            type="checkbox"
            checked={showDivergence}
            onChange={(e) => onShowDivergenceChange(e.target.checked)}
          />
          <span>Дивергенция</span>
        </label>
        <label className="toggle-row">
          <input
            type="checkbox"
            checked={showCandlePatterns}
            onChange={(e) => onShowCandlePatternsChange(e.target.checked)}
          />
          <span>Свечные паттерны</span>
        </label>
        <label className="toggle-row">
          <input
            type="checkbox"
            checked={showPatternLabels}
            onChange={(e) => onShowPatternLabelsChange(e.target.checked)}
          />
          <span>Подписи паттернов</span>
        </label>
        <div className="control-group">
          <label>Метки паттернов</label>
          <input
            type="range"
            min="0"
            max="60"
            step="5"
            value={patternLimit}
            onChange={(event) => onPatternLimitChange(Number(event.target.value))}
          />
        </div>
        <label className="toggle-row">
          <input
            type="checkbox"
            checked={showChartPatterns}
            onChange={(e) => onShowChartPatternsChange(e.target.checked)}
          />
          <span>Фигуры (линии)</span>
        </label>
        <label className="toggle-row">
          <input
            type="checkbox"
            checked={showPatternFill}
            onChange={(e) => onShowPatternFillChange(e.target.checked)}
          />
          <span>Заливка фигур</span>
        </label>
        <div className="control-group">
          <label>Pattern fill bands</label>
          <input
            type="range"
            min="2"
            max="8"
            step="1"
            value={patternFillBands}
            onChange={(event) => onPatternFillBandsChange(Number(event.target.value))}
          />
        </div>
        <div className="control-group">
          <label>Pattern fill count</label>
          <input
            type="range"
            min="1"
            max="8"
            step="1"
            value={patternFillLimit}
            onChange={(event) => onPatternFillLimitChange(Number(event.target.value))}
          />
        </div>
        <label className="toggle-row">
          <input
            type="checkbox"
            checked={showUnconfirmedPatterns}
            onChange={(e) => onShowUnconfirmedPatternsChange(e.target.checked)}
          />
          <span>Показывать непотвержденные</span>
        </label>
        <label className="toggle-row">
          <input
            type="checkbox"
            checked={showElliott}
            onChange={(e) => onShowElliottChange(e.target.checked)}
          />
          <span>Пивоты Elliott</span>
        </label>
        <label className="toggle-row">
          <input
            type="checkbox"
            checked={showSupportRes}
            onChange={(e) => onShowSupportResChange(e.target.checked)}
          />
          <span>Поддержка/сопротивление</span>
        </label>
        <label className="toggle-row">
          <input
            type="checkbox"
            checked={showTradePlan}
            onChange={(e) => onShowTradePlanChange(e.target.checked)}
          />
          <span>Линии плана сделки</span>
        </label>
        <label className="toggle-row">
          <input
            type="checkbox"
            checked={showBBands}
            onChange={(e) => onShowBBandsChange(e.target.checked)}
          />
          <span>BBands</span>
        </label>
        <label className="toggle-row">
          <input type="checkbox" checked={showVolume} onChange={(e) => onShowVolumeChange(e.target.checked)} />
          <span>Объем</span>
        </label>
        <label className="toggle-row">
          <input type="checkbox" checked={showAtr} onChange={(e) => onShowAtrChange(e.target.checked)} />
          <span>ATR</span>
        </label>
        <label className="toggle-row">
          <input type="checkbox" checked={showRsi} onChange={(e) => onShowRsiChange(e.target.checked)} />
          <span>RSI</span>
        </label>
        <label className="toggle-row">
          <input
            type="checkbox"
            checked={showTradeExits}
            onChange={(e) => onShowTradeExitsChange(e.target.checked)}
          />
          <span>Выходы сделок</span>
        </label>
        <label className="toggle-row">
          <input
            type="checkbox"
            checked={showTradePaths}
            onChange={(e) => onShowTradePathsChange(e.target.checked)}
          />
          <span>Траектория вход/выход</span>
        </label>
        <div className="control-group">
          <label>Метки истории</label>
          <input
            type="range"
            min="5"
            max="60"
            step="5"
            value={tradeHistoryLimit}
            onChange={(event) => onTradeHistoryLimitChange(Number(event.target.value))}
          />
        </div>
        <div className="control-group">
          <label>Свечей на графике</label>
          <input
            type="range"
            min="200"
            max="5000"
            step="200"
            value={chartBars}
            onChange={(event) => onChartBarsChange(Number(event.target.value))}
          />
        </div>
        <div className="control-group">
          <label>Шаг бэкофила</label>
          <input
            type="number"
            min="1"
            max="10"
            value={backfillStride}
            onChange={(event) => onBackfillStrideChange(Number(event.target.value) || 1)}
          />
        </div>
        <div className="control-group">
          <label>Макс. свечей бэкофила</label>
          <input
            type="number"
            min="200"
            max="10000"
            value={backfillMaxBars}
            onChange={(event) => onBackfillMaxBarsChange(Number(event.target.value) || 1000)}
          />
        </div>
      </details>
      <div className="control-group">
        <label>Ширина панели</label>
        <input
          type="range"
          min="280"
          max="520"
          step="10"
          value={sidebarWidth}
          onChange={(event) => onSidebarWidthChange(Number(event.target.value))}
        />
      </div>
      <div className="control-group">
        <label>Высота графика</label>
        <input
          type="range"
          min="420"
          max="820"
          step="20"
          value={chartHeight}
          onChange={(event) => onChartHeightChange(Number(event.target.value))}
        />
      </div>
      <label className="toggle-row">
        <input
          type="checkbox"
          checked={showSidePanel}
          onChange={(event) => onShowSidePanelChange(event.target.checked)}
        />
        <span>Показывать боковые панели</span>
      </label>
      <div className="mode-toggle" onClick={onModeToggle}>
        <span>Режим</span>
        <strong>{mode === "auto" ? "AUTO" : "SEMI"}</strong>
      </div>
    </div>
  );
}
