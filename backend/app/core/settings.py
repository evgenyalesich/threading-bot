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
    telegram_notifications_enabled: bool = Field(default=False, validation_alias="TELEGRAM_NOTIFICATIONS_ENABLED")
    telegram_bot_token: str | None = Field(default=None, validation_alias="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: str | None = Field(default=None, validation_alias="TELEGRAM_CHAT_ID")
    telegram_allowed_chat_ids: str = Field(default="", validation_alias="TELEGRAM_ALLOWED_CHAT_IDS")
    automation_enabled_on_start: bool = Field(default=False, validation_alias="AUTOMATION_ENABLED_ON_START")
    ui_auth_enabled: bool = Field(default=False, validation_alias="UI_AUTH_ENABLED")
    ui_auth_secret: str | None = Field(default=None, validation_alias="UI_AUTH_SECRET")
    ui_auth_cookie_secure: bool = Field(default=True, validation_alias="UI_AUTH_COOKIE_SECURE")
    news_enabled: bool = Field(default=True, validation_alias="NEWS_ENABLED")
    news_rss_feeds: str = Field(
        default=(
            "https://www.investing.com/rss/news_25.rss,"
            "https://www.investing.com/rss/news_1.rss,"
            "https://www.fxstreet.com/rss/news,"
            "https://cointelegraph.com/rss,"
            "https://www.coindesk.com/arc/outboundfeeds/rss/"
        ),
        validation_alias="NEWS_RSS_FEEDS",
    )
    news_block_minutes_before: int = Field(default=30, validation_alias="NEWS_BLOCK_MINUTES_BEFORE")
    news_block_minutes_after: int = Field(default=30, validation_alias="NEWS_BLOCK_MINUTES_AFTER")
    news_cache_ttl_sec: int = Field(default=180, validation_alias="NEWS_CACHE_TTL_SEC")
    news_high_impact_keywords: str = Field(
        default=(
            "nfp,nonfarm,cpi,inflation,fomc,fed,powell,rate decision,interest rate,"
            "ecb,lagarde,boe,boj,gdp,pmi,ppi,unemployment,jobless,retail sales,"
            "war,sanction,sec,etf,hack,exploit,binance,coinbase"
        ),
        validation_alias="NEWS_HIGH_IMPACT_KEYWORDS",
    )

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

    def telegram_allowed_chat_id_list(self) -> list[str]:
        values = [str(self.telegram_chat_id or "").strip()]
        values.extend(item.strip() for item in self.telegram_allowed_chat_ids.split(","))
        return sorted({item for item in values if item})

    def news_feed_list(self) -> list[str]:
        return [item.strip() for item in self.news_rss_feeds.split(",") if item.strip()]

    def news_high_impact_keyword_list(self) -> list[str]:
        return [item.strip().lower() for item in self.news_high_impact_keywords.split(",") if item.strip()]
