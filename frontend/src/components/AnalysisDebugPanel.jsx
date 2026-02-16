function formatPct(value) {
  if (!Number.isFinite(value)) return "-";
  return `${Math.round(value * 100)}%`;
}

function reasonLabel(reason) {
  const map = {
    insufficient_bars: "Недостаточно свечей для индикаторов (нужно 210+)",
    no_signal_components: "Нет подтверждений: фигуры/дивергенция/свечные паттерны",
    trend_mismatch_ema200: "Не прошел тренд-фильтр (цена относительно EMA200)",
    confirmations_below_min: "Недостаточно подтверждений",
    confidence_below_min: "Уверенность ниже минимума",
    volume_confirm_required: "Нужен подтверждающий объем, но его нет",
    pattern_required: "Требуется фигура, но ее нет",
    divergence_required: "Требуется дивергенция, но ее нет",
    candle_required: "Требуется свечной паттерн, но его нет",
    no_candles_in_db: "В БД нет свечей (сначала синхронизируй историю)",
    explain_failed: "Не удалось получить диагностику (ошибка запроса)",
  };
  return map[reason] || reason;
}

export default function AnalysisDebugPanel({ debug }) {
  if (!debug) {
    return (
      <div className="debug-panel">
        <div className="panel-title">Почему нет сигнала</div>
        <div className="empty-state">
          Нажми "Запуск анализа". Если сигнала нет, здесь появится объяснение.
        </div>
      </div>
    );
  }
  const reasons = Array.isArray(debug.reasons) ? debug.reasons : [];
  const hasReasons = reasons.length > 0;
  return (
    <div className="debug-panel">
      <div className="panel-title">Почему нет сигнала</div>
      {!hasReasons ? (
        <div className="empty-state">Блокеров не видно (сигнал должен быть возможен)</div>
      ) : (
        <div className="debug-reasons">
          {reasons.map((reason) => (
            <div key={reason} className="debug-reason">
              {reasonLabel(reason)}
            </div>
          ))}
        </div>
      )}
      <div className="debug-metrics">
        <div>
          <strong>Сторона:</strong> {debug.side ? String(debug.side).toUpperCase() : "-"}
        </div>
        <div>
          <strong>Подтверждения:</strong>{" "}
          {Number.isFinite(debug.confirmations) ? debug.confirmations : "-"} /{" "}
          {Number.isFinite(debug?.filters?.min_confirmations)
            ? debug.filters.min_confirmations
            : Number.isFinite(debug.min_confirmations)
            ? debug.min_confirmations
            : "-"}
        </div>
        <div>
          <strong>Уверенность:</strong> {formatPct(debug.confidence)} (мин {formatPct(debug?.filters?.min_confidence ?? debug.min_confidence)})
        </div>
        <div>
          <strong>Тренд (bias):</strong> {Number.isFinite(debug.trend_bias) ? debug.trend_bias : "-"}
        </div>
        <div>
          <strong>Фигура (bias):</strong> {Number.isFinite(debug.pattern_bias) ? debug.pattern_bias : "-"}
        </div>
        <div>
          <strong>Дивергенция (bias):</strong> {Number.isFinite(debug.divergence_bias) ? debug.divergence_bias : "-"}
        </div>
        <div>
          <strong>Свечи (bias):</strong> {Number.isFinite(debug.candle_bias) ? debug.candle_bias : "-"}
        </div>
        <div>
          <strong>Объем подтвержден:</strong>{" "}
          {debug.volume_confirm === true ? "да" : debug.volume_confirm === false ? "нет" : "-"}
        </div>
      </div>
    </div>
  );
}
