export default function PairsPanel({
  pairs,
  selectedSymbol,
  search,
  minVolatility,
  maxPrice,
  maxNotional,
  quoteAsset,
  onSearchChange,
  onMinVolatilityChange,
  onMaxPriceChange,
  onMaxNotionalChange,
  onQuoteAssetChange,
  onSelectPair,
  loading,
}) {
  return (
    <div className="pairs-panel">
      <div className="panel-title">Пары ({pairs.length})</div>
      <div className="pairs-filters">
        <div className="control-group">
          <label>Поиск</label>
          <input value={search} onChange={(event) => onSearchChange(event.target.value)} />
        </div>
        <div className="control-group">
          <label>Котировка</label>
          <select value={quoteAsset} onChange={(event) => onQuoteAssetChange(event.target.value)}>
            <option value="ALL">ВСЕ</option>
            <option value="USDT">USDT</option>
            <option value="USDC">USDC</option>
            <option value="BUSD">BUSD</option>
            <option value="USD">USD</option>
          </select>
        </div>
        <div className="control-group">
          <label>Мин. волатильность %</label>
          <input
            type="number"
            step="0.1"
            value={minVolatility}
            onChange={(event) => onMinVolatilityChange(Number(event.target.value) || 0)}
          />
        </div>
        <div className="control-group">
          <label>Макс. цена $</label>
          <input
            type="number"
            step="0.0001"
            value={maxPrice}
            onChange={(event) => onMaxPriceChange(Number(event.target.value) || 0)}
          />
        </div>
        <div className="control-group">
          <label>Макс. minNotional $</label>
          <input
            type="number"
            step="0.1"
            value={maxNotional}
            onChange={(event) => onMaxNotionalChange(Number(event.target.value) || 0)}
          />
        </div>
      </div>
      <div className="pairs-list">
        {loading ? (
          <div className="empty-state">Загрузка пар...</div>
        ) : null}
        {!loading && !pairs.length ? (
          <div className="empty-state">Нет подходящих пар</div>
        ) : null}
        {pairs.map((pair) => {
          const volatility = Number.isFinite(pair.volatility_score) ? pair.volatility_score : 0;
          const price = Number.isFinite(pair.last_price) ? pair.last_price : 0;
          const minNotional = Number.isFinite(pair.min_notional) ? pair.min_notional.toFixed(2) : null;
          const display = pair.base_asset && pair.quote_asset ? `${pair.base_asset}/${pair.quote_asset}` : pair.symbol;
          return (
            <button
              key={pair.symbol}
              className={`pair-row ${selectedSymbol === pair.symbol ? "active" : ""}`}
              onClick={() => onSelectPair(pair)}
            >
              <div>
                <strong>{display}</strong>
                <span>
                  {pair.symbol}
                  {minNotional ? ` · мин $${minNotional}` : ""}
                </span>
              </div>
              <div>
                <span className="pair-vol">{volatility.toFixed(2)}%</span>
                <span className="pair-price">${price.toFixed(6)}</span>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
