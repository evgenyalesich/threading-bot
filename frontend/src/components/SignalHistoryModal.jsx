import SignalList from "./SignalList.jsx";

export default function SignalHistoryModal({ open, order, signals, loading, onClose }) {
  if (!open) return null;

  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <div className="modal-card" onClick={(event) => event.stopPropagation()}>
        <header>
          <div>
            <h3>История сигналов</h3>
            <span>
              {order?.symbol} · {order?.timeframe ?? "н/д"} · {order?.market}
            </span>
          </div>
          <button className="ghost" type="button" onClick={onClose}>
            Закрыть
          </button>
        </header>
        <div className="modal-content">
          {loading ? <div className="empty-state">Загрузка сигналов...</div> : null}
          {!loading && signals.length === 0 ? <div className="empty-state">Сигналов нет</div> : null}
          {!loading && signals.length > 0 ? <SignalList signals={signals} /> : null}
        </div>
      </div>
    </div>
  );
}
