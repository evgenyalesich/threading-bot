from __future__ import annotations

from app.core.settings import Settings


def clean_cred(value: str | None) -> str | None:
    if not value:
        return None
    v = value.strip()
    if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
        v = v[1:-1].strip()
    return v or None


def resolve_api_credentials(settings: Settings, trade_env: str, market: str) -> tuple[str | None, str | None, Settings]:
    normalized_env = (trade_env or "testnet").lower()
    normalized_market = (market or "spot").lower()
    effective_settings = settings.model_copy(update={"binance_testnet": normalized_env == "testnet"})

    if effective_settings.binance_testnet:
        if normalized_market == "futures":
            key = effective_settings.binance_futures_testnet_api_key or effective_settings.binance_testnet_api_key
            secret = (
                effective_settings.binance_futures_testnet_api_secret or effective_settings.binance_testnet_api_secret
            )
        else:
            key = effective_settings.binance_spot_testnet_api_key or effective_settings.binance_testnet_api_key
            secret = effective_settings.binance_spot_testnet_api_secret or effective_settings.binance_testnet_api_secret
    else:
        key = effective_settings.binance_api_key
        secret = effective_settings.binance_api_secret

    return clean_cred(key), clean_cred(secret), effective_settings
