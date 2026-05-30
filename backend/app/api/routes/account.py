from __future__ import annotations

import asyncio

from fastapi import APIRouter, Query

from app.core.settings import Settings
from app.services.binance_credentials import resolve_api_credentials
from app.schemas.account_summary import (
    AccountSummary,
    FuturesAssetItem,
    FuturesPositionItem,
    SpotBalanceItem,
)


router = APIRouter()
settings = Settings()


def _build_client(trade_env: str, market: str):
    trade_env = trade_env.lower()
    market = market.lower()
    api_key, api_secret, trade_settings = resolve_api_credentials(settings, trade_env, market)
    if not api_key or not api_secret:
        return None, trade_env

    from binance.client import Client

    client = Client(
        api_key=api_key,
        api_secret=api_secret,
        testnet=trade_settings.binance_testnet,
    )
    # python-binance's `testnet=True` is not consistently applied across spot/futures endpoints
    # in all versions. Force URLs so we don't accidentally hit real endpoints with testnet keys.
    if trade_settings.binance_testnet:
        client.API_URL = trade_settings.binance_rest_spot_testnet_url.rstrip("/") + "/api"
        client.FUTURES_URL = trade_settings.binance_rest_futures_testnet_url.rstrip("/") + "/fapi"
    return client, trade_env


def _normalize_binance_error(exc: Exception) -> str:
    # Prefer stable error codes for the frontend.
    code = getattr(exc, "code", None)
    if code is None:
        # python-binance sometimes stores it on `status_code`/`error_code` or only in the string.
        text = str(exc)
        if "code=-2015" in text or "APIError(code=-2015)" in text:
            return "invalid_api_key"
        return text
    try:
        code_int = int(code)
    except Exception:
        return str(exc)
    if code_int == -2015:
        return "invalid_api_key"
    return str(exc)


@router.get("/summary")
async def account_summary(
    market: str = Query(default="spot"),
    trade_env: str = Query(default="testnet"),
    nonzero_only: bool = Query(default=True),
) -> AccountSummary:
    market = market.lower()
    client, normalized_env = _build_client(trade_env, market)
    if client is None:
        return AccountSummary(status="no_keys", market=market, trade_env=normalized_env)

    try:
        if market == "spot":
            data = await asyncio.to_thread(client.get_account)
            balances = []
            for item in data.get("balances", []) or []:
                asset = item.get("asset")
                if not asset:
                    continue
                free = float(item.get("free") or 0)
                locked = float(item.get("locked") or 0)
                if nonzero_only and free == 0 and locked == 0:
                    continue
                balances.append(SpotBalanceItem(asset=asset, free=free, locked=locked))
            balances.sort(key=lambda x: (x.free + x.locked), reverse=True)
            return AccountSummary(
                status="ok",
                market=market,
                trade_env=normalized_env,
                spot_balances=balances,
            )

        if market == "futures":
            # futures_account_balance: list of assets; position_information: per symbol
            assets_raw = await asyncio.to_thread(client.futures_account_balance)
            positions_raw = await asyncio.to_thread(client.futures_position_information)

            assets = []
            for item in assets_raw or []:
                asset = item.get("asset")
                if not asset:
                    continue
                wallet = float(item.get("balance") or 0)
                available = float(item.get("availableBalance") or 0)
                upnl = item.get("crossUnPnl")
                upnl_val = float(upnl) if upnl is not None else None
                if nonzero_only and wallet == 0 and available == 0:
                    continue
                assets.append(
                    FuturesAssetItem(
                        asset=asset,
                        wallet_balance=wallet,
                        available_balance=available,
                        unrealized_profit=upnl_val,
                    )
                )
            assets.sort(key=lambda x: x.wallet_balance, reverse=True)

            positions = []
            for item in positions_raw or []:
                symbol = item.get("symbol")
                if not symbol:
                    continue
                amt = float(item.get("positionAmt") or 0)
                if nonzero_only and amt == 0:
                    continue
                entry = float(item.get("entryPrice") or 0)
                mark = item.get("markPrice")
                mark_val = float(mark) if mark is not None else None
                upnl = item.get("unRealizedProfit")
                upnl_val = float(upnl) if upnl is not None else None
                lev = item.get("leverage")
                lev_val = int(lev) if lev is not None else None
                margin = item.get("positionInitialMargin") or item.get("initialMargin") or item.get("isolatedMargin")
                margin_val = float(margin) if margin is not None else None
                notional = item.get("notional")
                notional_val = abs(float(notional)) if notional is not None else None
                if not lev_val and margin_val and margin_val > 0 and notional_val is not None:
                    lev_val = round(notional_val / margin_val)
                if (margin_val is None or margin_val <= 0) and entry > 0 and lev_val:
                    margin_val = abs(amt) * entry / lev_val
                side = "LONG" if amt > 0 else "SHORT" if amt < 0 else None
                positions.append(
                    FuturesPositionItem(
                        symbol=symbol,
                        position_amt=amt,
                        entry_price=entry,
                        mark_price=mark_val,
                        unrealized_profit=upnl_val,
                        margin=margin_val,
                        leverage=lev_val,
                        side=side,
                    )
                )
            return AccountSummary(
                status="ok",
                market=market,
                trade_env=normalized_env,
                futures_assets=assets,
                futures_positions=positions,
            )

        return AccountSummary(status="error", market=market, trade_env=normalized_env, error="unsupported_market")
    except Exception as exc:
        return AccountSummary(
            status="error",
            market=market,
            trade_env=normalized_env,
            error=_normalize_binance_error(exc),
        )


@router.get("/trades")
async def account_trades(
    market: str = Query(default="spot"),
    trade_env: str = Query(default="testnet"),
    symbol: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
) -> dict:
    market = market.lower()
    client, normalized_env = _build_client(trade_env, market)
    if client is None:
        return {"status": "no_keys", "market": market, "trade_env": normalized_env, "trades": []}
    try:
        if market == "futures":
            params = {"limit": int(limit)}
            if symbol:
                params["symbol"] = symbol.upper()
            rows = await asyncio.to_thread(client.futures_account_trades, **params)
        else:
            if not symbol:
                return {
                    "status": "error",
                    "market": market,
                    "trade_env": normalized_env,
                    "error": "symbol_required_for_spot_trades",
                    "trades": [],
                }
            rows = await asyncio.to_thread(client.get_my_trades, symbol=symbol.upper(), limit=int(limit))
        return {"status": "ok", "market": market, "trade_env": normalized_env, "trades": rows or []}
    except Exception as exc:
        return {
            "status": "error",
            "market": market,
            "trade_env": normalized_env,
            "error": _normalize_binance_error(exc),
            "trades": [],
        }
