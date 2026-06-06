function formatDateTime(value) {
  if (!value) return "--";
  return new Date(value).toLocaleString();
}

function formatPrice(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "--";
  return numeric.toLocaleString("ru-RU", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 6,
  });
}

export default function AutomationCenter({
  state,
  loading,
  onSyncWorkspace,
  onEnable,
  onDisable,
  onRunNow,
  onSetMode,
  onSetTradeEnv,
  onApprove,
  onReject,
}) {
  return (
    <section className="automation-center">
      <div className="panel-title-row">
        <div>
          <div className="panel-title">Automation Center</div>
          <div className="journal-subtitle">Очередь сигналов, approve flow и журнал автодействий.</div>
        </div>
        <span className={`automation-state-badge ${state?.enabled ? "live" : "idle"}`}>
          {state?.enabled ? "LIVE" : "IDLE"}
        </span>
      </div>

      <div className="automation-toolbar">
        <button className="ghost" onClick={onSyncWorkspace}>
          Взять текущий workspace
        </button>
        <button className="ghost" onClick={onRunNow} disabled={loading}>
          Проверить сейчас
        </button>
      </div>

      <div className="automation-mode-strip">
        <button
          type="button"
          className={state?.mode === "semi" ? "active" : ""}
          onClick={() => onSetMode("semi")}
        >
          SEMI
        </button>
        <button
          type="button"
          className={state?.mode === "auto" ? "active" : ""}
          onClick={() => onSetMode("auto")}
        >
          AUTO
        </button>
        <button
          type="button"
          className={state?.trade_env === "testnet" ? "active" : ""}
          onClick={() => onSetTradeEnv("testnet")}
        >
          DEMO
        </button>
        <button
          type="button"
          className={state?.trade_env === "real" ? "active" : ""}
          onClick={() => onSetTradeEnv("real")}
        >
          REAL
        </button>
      </div>

      <div className="automation-actions">
        <button className="primary" onClick={state?.enabled ? onDisable : onEnable} disabled={loading}>
          {state?.enabled ? "Остановить automation" : "Запустить automation"}
        </button>
      </div>

      <div className="automation-grid">
        <div className="automation-card">
          <span>Universe</span>
          <strong>{state?.scan_market_wide ? "MARKET-WIDE" : (state?.symbol || "--")}</strong>
          <small>{state?.timeframe || "--"} · {state?.market || "--"} · {state?.quote || "ALL"}</small>
        </div>
        <div className="automation-card">
          <span>Live state</span>
          <strong>{(state?.live_state || "--").toUpperCase()}</strong>
          <small>{state?.live_message || state?.last_no_signal_reason || "--"}</small>
        </div>
        <div className="automation-card">
          <span>Polling</span>
          <strong>{state?.poll_interval_sec ?? "--"}s</strong>
          <small>last check {formatDateTime(state?.last_check_at)}</small>
        </div>
        <div className="automation-card">
          <span>Очередь approve</span>
          <strong>{state?.pending_approvals?.length ?? 0}</strong>
          <small>{state?.mode === "auto" ? "auto execution enabled" : "manual confirmation"}</small>
        </div>
        <div className="automation-card">
          <span>Последний сигнал</span>
          <strong>{state?.latest_signal ? `${state.latest_signal.signal_type.toUpperCase()} ${Math.round(Number(state.latest_signal.confidence || 0) * 100)}%` : "--"}</strong>
          <small>{formatDateTime(state?.last_signal_at)}</small>
        </div>
        <div className="automation-card">
          <span>Automation worker</span>
          <strong>{state?.worker_running ? "ONLINE" : "OFFLINE"}</strong>
          <small>{state?.enabled ? "automation enabled" : "automation disabled"}</small>
        </div>
        <div className="automation-card">
          <span>Telegram polling</span>
          <strong>{state?.telegram_worker_running ? "ONLINE" : "OFFLINE"}</strong>
          <small>{state?.telegram_enabled ? `last update ${formatDateTime(state?.last_update_received_at)}` : "telegram disabled"}</small>
        </div>
        <div className="automation-card">
          <span>Last callback</span>
          <strong>{formatDateTime(state?.last_callback_handled_at)}</strong>
          <small>{state?.last_telegram_error || "no telegram errors"}</small>
        </div>
        <div className="automation-card">
          <span>Runtime error</span>
          <strong>{state?.last_error ? "ATTENTION" : "OK"}</strong>
          <small>{state?.last_error || state?.last_no_signal_reason || "worker healthy"}</small>
        </div>
      </div>

      <div className="automation-subsection">
        <div className="signals-title">Pending approvals</div>
        <div className="automation-list">
          {state?.pending_approvals?.length ? state.pending_approvals.map((item) => (
            <div key={item.signal_id} className={`signal-card ${item.signal_type === "long" ? "long" : "short"}`}>
              <div className="signal-header">
                <strong>{item.symbol}</strong>
                <span className="signal-type">{item.signal_type.toUpperCase()}</span>
              </div>
              <div className="signal-meta">
                <span>{item.timeframe}</span>
                <span>{Math.round(Number(item.confidence || 0) * 100)}%</span>
              </div>
              <div className="signal-levels">
                <span>Entry {formatPrice(item.entry_price)}</span>
                <span>SL {formatPrice(item.stop_loss)}</span>
              </div>
              <div className="signal-levels secondary">
                <span>TP {formatPrice(item.take_profit)}</span>
                <span>ID #{item.signal_id}</span>
              </div>
              {item.rationale ? <div className="signal-rationale">{item.rationale}</div> : null}
              <div className="automation-inline-actions">
                <button className="primary" onClick={() => onApprove(item.signal_id)}>Approve</button>
                <button className="ghost" onClick={() => onReject(item.signal_id)}>Reject</button>
              </div>
            </div>
          )) : (
            <div className="empty-state">Очередь пуста. Automation будет ждать новый сигнал.</div>
          )}
        </div>
      </div>

      <div className="automation-subsection">
        <div className="signals-title">Automation log</div>
        <div className="automation-log-list">
          {state?.logs?.length ? state.logs.map((log) => (
            <div key={log.id} className={`automation-log-row ${log.level}`}>
              <div className="automation-log-head">
                <strong>{log.event}</strong>
                <span>{formatDateTime(log.created_at)}</span>
              </div>
              <div className="automation-log-message">{log.message}</div>
            </div>
          )) : (
            <div className="empty-state">Журнал пока пуст.</div>
          )}
        </div>
      </div>

      <div className="automation-subsection">
        <div className="signals-title">Recent signals</div>
        <div className="automation-list">
          {state?.recent_signals?.length ? state.recent_signals.map((item) => (
            <div key={item.id} className={`signal-card ${item.signal_type === "long" ? "long" : "short"}`}>
              <div className="signal-header">
                <strong>{item.symbol}</strong>
                <span className="signal-type">{item.signal_type.toUpperCase()}</span>
              </div>
              <div className="signal-meta">
                <span>{item.timeframe}</span>
                <span>{Math.round(Number(item.confidence || 0) * 100)}%</span>
              </div>
              <div className="signal-levels">
                <span>Entry {formatPrice(item.entry_price)}</span>
                <span>ID #{item.id}</span>
              </div>
              <div className="signal-levels secondary">
                <span>SL {formatPrice(item.stop_loss)}</span>
                <span>TP {formatPrice(item.take_profit)}</span>
              </div>
              <div className="signal-rationale">{item.rationale || formatDateTime(item.created_at)}</div>
            </div>
          )) : (
            <div className="empty-state">Сигналов пока нет.</div>
          )}
        </div>
      </div>

      <div className="automation-subsection">
        <div className="signals-title">Recent orders</div>
        <div className="automation-list">
          {state?.recent_orders?.length ? state.recent_orders.map((item) => (
            <div key={item.id} className={`signal-card ${item.side === "BUY" ? "long" : "short"}`}>
              <div className="signal-header">
                <strong>{item.symbol}</strong>
                <span className="signal-type">{item.side}</span>
              </div>
              <div className="signal-meta">
                <span>{item.market}/{item.trade_env || "--"}</span>
                <span>{item.status}</span>
              </div>
              <div className="signal-levels">
                <span>Entry {formatPrice(item.price)}</span>
                <span>ID #{item.id}</span>
              </div>
              <div className="signal-levels secondary">
                <span>SL {formatPrice(item.stop_loss)}</span>
                <span>TP {formatPrice(item.take_profit)}</span>
              </div>
              <div className="signal-rationale">
                PnL {item.realized_pnl ?? "--"} · {formatDateTime(item.created_at)}
              </div>
            </div>
          )) : (
            <div className="empty-state">Сделок пока нет.</div>
          )}
        </div>
      </div>
    </section>
  );
}
