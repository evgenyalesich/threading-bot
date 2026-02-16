import { useState } from "react";

export default function MappingTable({ mappings, onCreate, onUpdate, onDelete }) {
  const [form, setForm] = useState({ yfinance_symbol: "", binance_symbol: "", market: "spot" });
  const [editingId, setEditingId] = useState(null);
  const [editingValue, setEditingValue] = useState({ binance_symbol: "", market: "spot" });

  const handleSubmit = (event) => {
    event.preventDefault();
    if (!form.yfinance_symbol || !form.binance_symbol) return;
    onCreate(form);
    setForm({ yfinance_symbol: "", binance_symbol: "", market: "spot" });
  };

  const startEdit = (mapping) => {
    setEditingId(mapping.id);
    setEditingValue({ binance_symbol: mapping.binance_symbol, market: mapping.market });
  };

  const submitEdit = (id) => {
    onUpdate(id, editingValue);
    setEditingId(null);
  };

  return (
    <div className="mapping-panel">
      <div className="panel-title">Маппинг символов</div>
      <form className="mapping-form" onSubmit={handleSubmit}>
        <input
          placeholder="YFinance (BTC-USD)"
          value={form.yfinance_symbol}
          onChange={(event) => setForm((prev) => ({ ...prev, yfinance_symbol: event.target.value }))}
        />
        <input
          placeholder="Binance (BTCUSDT)"
          value={form.binance_symbol}
          onChange={(event) => setForm((prev) => ({ ...prev, binance_symbol: event.target.value }))}
        />
        <select
          value={form.market}
          onChange={(event) => setForm((prev) => ({ ...prev, market: event.target.value }))}
        >
          <option value="spot">Спот</option>
          <option value="futures">Фьючерсы</option>
        </select>
        <button type="submit" className="primary">Добавить</button>
      </form>
      <div className="mapping-table">
        {mappings.length === 0 ? <div className="empty-state">Маппингов пока нет</div> : null}
        {mappings.map((mapping) => (
          <div key={mapping.id} className="mapping-row">
            <div>
              <strong>{mapping.yfinance_symbol}</strong>
              <span>{mapping.binance_symbol}</span>
            </div>
            <div>
              {editingId === mapping.id ? (
                <>
                  <input
                    value={editingValue.binance_symbol}
                    onChange={(event) =>
                      setEditingValue((prev) => ({ ...prev, binance_symbol: event.target.value }))
                    }
                  />
                  <select
                    value={editingValue.market}
                    onChange={(event) =>
                      setEditingValue((prev) => ({ ...prev, market: event.target.value }))
                    }
                  >
                    <option value="spot">Спот</option>
                    <option value="futures">Фьючерсы</option>
                  </select>
                  <button className="ghost" type="button" onClick={() => submitEdit(mapping.id)}>
                    Сохранить
                  </button>
                </>
              ) : (
                <>
                  <span className="mapping-market">{mapping.market}</span>
                  <button className="ghost" type="button" onClick={() => startEdit(mapping)}>
                    Изменить
                  </button>
                </>
              )}
              <button className="ghost danger" type="button" onClick={() => onDelete(mapping.id)}>
                Удалить
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
