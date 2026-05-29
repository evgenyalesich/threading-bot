function formatNum(value, digits = 4) {
  if (!Number.isFinite(value)) return "-";
  return value.toFixed(digits);
}

function humanizeAccountError(code) {
  const map = {
    invalid_api_key:
      "Неверный API-ключ/секрет, не тот рынок (spot/futures) или ключи не для testnet. Проверь права ключа и перезапусти backend после правки .env.",
  };
  return map[code] || code;
}

export default function AccountPanel({ summary, trades = [] }) {
  return (
    <div className="account-panel">
      <div className="panel-title">Баланс</div>
      {!summary ? <div className="empty-state">Загрузка...</div> : null}
      {summary?.status === "no_keys" ? (
        <div className="empty-state">
          Нет ключей Binance.
          <br />
          Testnet: `BINANCE_SPOT_TESTNET_API_KEY/SECRET` и/или `BINANCE_FUTURES_TESTNET_API_KEY/SECRET`
          <br />
          (или общий fallback `BINANCE_TESTNET_API_KEY/SECRET`)
        </div>
      ) : null}
      {summary?.status === "error" ? (
        <div className="empty-state">Ошибка: {humanizeAccountError(summary.error || "неизвестно")}</div>
      ) : null}

      {summary?.status === "ok" && summary.market === "spot" ? (
        <div className="account-list">
          {(summary.spot_balances || []).slice(0, 12).map((b) => (
            <div className="account-row" key={b.asset}>
              <strong>{b.asset}</strong>
              <span>доступно {formatNum(Number(b.free), 6)}</span>
              <span>заморожено {formatNum(Number(b.locked), 6)}</span>
            </div>
          ))}
          {!summary.spot_balances?.length ? (
            <div className="empty-state">
              Баланс пустой. Проверь:
              <br />
              1) что выбран правильный режим (SPOT/FUTURES) и среда (Testnet/Real)
              <br />
              2) что ключи лежат в `BINANCE_TESTNET_API_KEY/SECRET` для testnet
            </div>
          ) : null}
        </div>
      ) : null}

      {summary?.status === "ok" && summary.market === "futures" ? (
        <div className="account-list">
          <div className="account-subtitle">Активы</div>
          {(summary.futures_assets || []).slice(0, 8).map((a) => (
            <div className="account-row" key={a.asset}>
              <strong>{a.asset}</strong>
              <span>кошелек {formatNum(Number(a.wallet_balance), 4)}</span>
              <span>доступно {formatNum(Number(a.available_balance), 4)}</span>
            </div>
          ))}
          {!summary.futures_assets?.length ? (
            <div className="empty-state">
              Активов нет. Если ты на Futures Testnet, это отдельный баланс: его нужно пополнить на тестнете.
            </div>
          ) : null}
          <div className="account-subtitle">Позиции</div>
          {(summary.futures_positions || []).slice(0, 8).map((p) => (
            <div className="account-row" key={p.symbol}>
              <strong>{p.symbol}</strong>
              <span>
                {p.side || "-"} {formatNum(Number(p.position_amt), 4)} x{p.leverage ?? "-"}
              </span>
              <span>вход {formatNum(Number(p.entry_price), 2)}</span>
            </div>
          ))}
          {!summary.futures_positions?.length ? <div className="empty-state">Позиции отсутствуют</div> : null}
        </div>
      ) : null}
      {summary?.status === "ok" ? (
        <div className="account-list">
          <div className="account-subtitle">Последние сделки</div>
          {trades.slice(0, 8).map((t) => (
            <div className="account-row" key={`${t.id ?? t.orderId ?? "t"}-${t.time ?? t.symbol}`}>
              <strong>{t.symbol || "-"}</strong>
              <span>{t.side || t.positionSide || "-"}</span>
              <span>{t.qty || t.executedQty || t.size || "-"}</span>
            </div>
          ))}
          {!trades.length ? <div className="empty-state">История сделок пуста</div> : null}
        </div>
      ) : null}
    </div>
  );
}
