function formatTime(value) {
  if (!value) return "--";
  try {
    return new Date(value).toLocaleString("ru-RU", {
      day: "2-digit",
      month: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return "--";
  }
}

export default function NewsGuardPanel({ context, loading, error }) {
  const blocked = Boolean(context?.news_block);
  const events = context?.blocking_news?.length
    ? context.blocking_news
    : context?.market_events?.length
      ? context.market_events
      : context?.global_events || context?.news_events || [];
  const globalCount = context?.global_events?.length || 0;
  const marketCount = context?.market_events?.length || 0;
  const symbolCount = context?.symbol_events?.length || 0;
  return (
    <section className={`news-guard-panel ${blocked ? "blocked" : "clear"}`}>
      <div className="panel-title-row">
        <div>
          <div className="panel-title">News Guard</div>
          <div className="journal-subtitle">Global macro + crypto news risk</div>
        </div>
        <span className={`news-guard-badge ${blocked ? "blocked" : "clear"}`}>
          {loading ? "CHECK" : blocked ? "BLOCK" : "CLEAR"}
        </span>
      </div>
      {error ? <div className="dom-error">{error}</div> : null}
      {blocked ? (
        <div className="news-warning">Глобальная важная фин/крипто новость рядом. Стратегия молчит до выхода из risk-window.</div>
      ) : (
        <div className="news-ok">Критических macro/crypto новостей в текущем окне нет.</div>
      )}
      <div className="news-scope-grid">
        <span>Global <b>{globalCount}</b></span>
        <span>Market <b>{marketCount}</b></span>
        <span>Symbol <b>{symbolCount}</b></span>
      </div>
      <div className="news-list">
        {events.slice(0, 4).map((item, index) => (
          <a className="news-row" href={item.url || "#"} target="_blank" rel="noreferrer" key={`${item.title}-${index}`}>
            <span>{formatTime(item.published_at)} · {item.impact || "low"}</span>
            <strong>{item.title}</strong>
            {item.matched_keywords?.length ? <small>{item.matched_keywords.slice(0, 5).join(", ")}</small> : null}
          </a>
        ))}
        {!events.length ? <div className="empty-state">Новости загружаются или источники пока молчат.</div> : null}
      </div>
    </section>
  );
}
