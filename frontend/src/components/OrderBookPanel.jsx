function formatPrice(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "--";
  return numeric >= 1 ? numeric.toFixed(2) : numeric.toFixed(6);
}

function formatUsd(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "--";
  if (numeric >= 1_000_000) return `$${(numeric / 1_000_000).toFixed(2)}M`;
  if (numeric >= 1_000) return `$${(numeric / 1_000).toFixed(1)}K`;
  return `$${numeric.toFixed(0)}`;
}

function pressureLabel(value) {
  if (value === "bullish") return "Покупатель давит";
  if (value === "bearish") return "Продавец давит";
  return "Баланс";
}

function WallList({ title, rows, side }) {
  const max = Math.max(...(rows || []).map((row) => Number(row.notional) || 0), 1);
  return (
    <div className="dom-wall-list">
      <div className="dom-wall-title">{title}</div>
      {(rows || []).slice(0, 4).map((row) => (
        <div className={`dom-wall ${side}`} key={`${side}-${row.price}`}>
          <span>{formatPrice(row.price)}</span>
          <strong>{formatUsd(row.notional)}</strong>
          <i style={{ width: `${Math.max((Number(row.notional) / max) * 100, 8)}%` }} />
        </div>
      ))}
    </div>
  );
}

export default function OrderBookPanel({ book, loading, error }) {
  const imbalance = Number(book?.imbalance || 0);
  const bidPct = Math.max(Math.min((imbalance + 1) * 50, 100), 0);
  const askPct = 100 - bidPct;
  const pressure = book?.pressure || "neutral";

  return (
    <section className="orderbook-panel">
      <div className="panel-title-row">
        <div>
          <div className="panel-title">DOM / Стакан</div>
          <div className="journal-subtitle">Давление, стены заявок, спред.</div>
        </div>
        <span className={`dom-pressure ${pressure}`}>{loading ? "ОБНОВЛЯЮ" : pressureLabel(pressure)}</span>
      </div>

      {error ? <div className="dom-error">{error}</div> : null}
      {!book && !error ? <div className="empty-state">Стакан загружается...</div> : null}
      {book ? (
        <>
          <div className="dom-summary">
            <div>
              <span>Лучший bid</span>
              <strong className="bid">{formatPrice(book.best_bid)}</strong>
            </div>
            <div>
              <span>Лучший ask</span>
              <strong className="ask">{formatPrice(book.best_ask)}</strong>
            </div>
            <div>
              <span>Spread</span>
              <strong>{Number.isFinite(Number(book.spread_pct)) ? `${Number(book.spread_pct).toFixed(3)}%` : "--"}</strong>
            </div>
          </div>

          <div className="dom-imbalance">
            <div className="dom-imbalance-track">
              <span className="bid" style={{ width: `${bidPct}%` }} />
              <span className="ask" style={{ width: `${askPct}%` }} />
            </div>
            <div className="dom-imbalance-labels">
              <span>Bids {formatUsd(book.bid_notional)}</span>
              <strong>{(imbalance * 100).toFixed(1)}%</strong>
              <span>Asks {formatUsd(book.ask_notional)}</span>
            </div>
          </div>

          <div className="dom-walls-grid">
            <WallList title="Стены bid" rows={book.bid_walls} side="bid" />
            <WallList title="Стены ask" rows={book.ask_walls} side="ask" />
          </div>
        </>
      ) : null}
    </section>
  );
}
