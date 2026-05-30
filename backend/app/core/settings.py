from __future__ import annotations

from pydantic import Field, field_validator
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]
ENV_PATH = BASE_DIR / ".env"


class Settings(BaseSettings):
    app_name: str = "Threading Bot API"
    environment: str = "development"
    debug: bool = True
    api_prefix: str = "/api"

    database_url: str = Field(
        default="postgresql+asyncpg://postgres:6628@localhost:5432/threading_bot",
        validation_alias="DATABASE_URL",
    )
    cors_origins: str = Field(
        default="http://localhost:5173",
        validation_alias="CORS_ORIGINS",
    )

    binance_api_key: str | None = Field(default=None, validation_alias="BINANCE_API_KEY")
    binance_api_secret: str | None = Field(default=None, validation_alias="BINANCE_API_SECRET")
    binance_testnet_api_key: str | None = Field(default=None, validation_alias="BINANCE_TESTNET_API_KEY")
    binance_testnet_api_secret: str | None = Field(default=None, validation_alias="BINANCE_TESTNET_API_SECRET")
    # Binance testnet often uses separate keys for spot vs futures. These override the generic
    # BINANCE_TESTNET_* pair when provided.
    binance_spot_testnet_api_key: str | None = Field(default=None, validation_alias="BINANCE_SPOT_TESTNET_API_KEY")
    binance_spot_testnet_api_secret: str | None = Field(
        default=None, validation_alias="BINANCE_SPOT_TESTNET_API_SECRET"
    )
    binance_futures_testnet_api_key: str | None = Field(
        default=None, validation_alias="BINANCE_FUTURES_TESTNET_API_KEY"
    )
    binance_futures_testnet_api_secret: str | None = Field(
        default=None, validation_alias="BINANCE_FUTURES_TESTNET_API_SECRET"
    )
    binance_testnet: bool = Field(default=True, validation_alias="BINANCE_TESTNET")
    binance_ws_spot_url: str = Field(
        default="wss://stream.binance.com:9443/ws",
        validation_alias="BINANCE_WS_SPOT_URL",
    )
    binance_ws_futures_url: str = Field(
        default="wss://fstream.binance.com/ws",
        validation_alias="BINANCE_WS_FUTURES_URL",
    )
    binance_ws_spot_testnet_url: str = Field(
        default="wss://testnet.binance.vision/ws",
        validation_alias="BINANCE_WS_SPOT_TESTNET_URL",
    )
    binance_ws_futures_testnet_url: str = Field(
        default="wss://stream.binancefuture.com/ws",
        validation_alias="BINANCE_WS_FUTURES_TESTNET_URL",
    )
    binance_rest_spot_url: str = Field(
        default="https://api.binance.com",
        validation_alias="BINANCE_REST_SPOT_URL",
    )
    binance_rest_futures_url: str = Field(
        default="https://fapi.binance.com",
        validation_alias="BINANCE_REST_FUTURES_URL",
    )
    binance_rest_spot_testnet_url: str = Field(
        default="https://testnet.binance.vision",
        validation_alias="BINANCE_REST_SPOT_TESTNET_URL",
    )
    binance_rest_futures_testnet_url: str = Field(
        default="https://testnet.binancefuture.com",
        validation_alias="BINANCE_REST_FUTURES_TESTNET_URL",
    )

    default_symbol: str = "BTC-USD"
    default_timeframe: str = "15m"
    risk_per_trade: float = 0.01
    default_order_quantity: float = 0.001
    market_cache_ttl: int = 30
    db_auto_create: bool = Field(default=False, validation_alias="DB_AUTO_CREATE")

    model_config = SettingsConfigDict(env_file=str(ENV_PATH), case_sensitive=False)

    @field_validator("debug", mode="before")
    @classmethod
    def _parse_debug(cls, value):
        if isinstance(value, bool):
            return value
        if value is None:
            return True
        text = str(value).strip().lower()
        if text in {"1", "true", "yes", "on", "debug", "dev", "development"}:
            return True
        if text in {"0", "false", "no", "off", "release", "prod", "production"}:
            return False
        return True

    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
