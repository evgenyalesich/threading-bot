from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from html import unescape
from xml.etree import ElementTree

import httpx

from app.core.settings import Settings


@dataclass(frozen=True)
class NewsEvent:
    title: str
    source: str
    published_at: datetime | None
    url: str | None
    impact: str
    score: int
    matched_keywords: list[str]

    def as_dict(self) -> dict:
        return {
            "title": self.title,
            "source": self.source,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "url": self.url,
            "impact": self.impact,
            "score": self.score,
            "matched_keywords": self.matched_keywords,
        }


class NewsService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._cache: list[NewsEvent] | None = None
        self._cache_at: datetime | None = None
        self._lock = asyncio.Lock()

    async def latest(self, limit: int = 80, force: bool = False) -> list[NewsEvent]:
        if not self._settings.news_enabled:
            return []
        now = datetime.now(UTC)
        if (
            not force
            and self._cache is not None
            and self._cache_at is not None
            and (now - self._cache_at).total_seconds() < self._settings.news_cache_ttl_sec
        ):
            return self._cache[:limit]

        async with self._lock:
            now = datetime.now(UTC)
            if (
                not force
                and self._cache is not None
                and self._cache_at is not None
                and (now - self._cache_at).total_seconds() < self._settings.news_cache_ttl_sec
            ):
                return self._cache[:limit]
            events = await self._fetch_all()
            events.sort(key=lambda item: item.published_at or datetime.min.replace(tzinfo=UTC), reverse=True)
            self._cache = events
            self._cache_at = now
            return events[:limit]

    async def context(self, symbol: str | None = None, market: str | None = None) -> dict:
        events = await self.latest(limit=120)
        global_events = events
        market_events = self._market_events(events, market=market)
        symbol_events = self._symbol_events(events, symbol=symbol)
        relevant = self._dedupe_events([*symbol_events, *market_events, *global_events])
        now = datetime.now(UTC)
        before = timedelta(minutes=max(self._settings.news_block_minutes_before, 0))
        after = timedelta(minutes=max(self._settings.news_block_minutes_after, 0))
        blocking = []
        for event in relevant:
            if event.impact != "high":
                continue
            published = event.published_at or now
            if published - before <= now <= published + after:
                blocking.append(event)
        return {
            "news_enabled": self._settings.news_enabled,
            "news_block": bool(blocking),
            "high_impact_news": bool(blocking),
            "news_block_window_min": {
                "before": self._settings.news_block_minutes_before,
                "after": self._settings.news_block_minutes_after,
            },
            "news_events": [event.as_dict() for event in relevant[:30]],
            "global_events": [event.as_dict() for event in global_events[:30]],
            "market_events": [event.as_dict() for event in market_events[:30]],
            "symbol_events": [event.as_dict() for event in symbol_events[:20]],
            "blocking_news": [event.as_dict() for event in blocking[:10]],
        }

    async def _fetch_all(self) -> list[NewsEvent]:
        feeds = self._settings.news_feed_list()
        if not feeds:
            return []
        timeout = httpx.Timeout(8.0, connect=3.0)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            tasks = [self._fetch_feed(client, url) for url in feeds]
            results = await asyncio.gather(*tasks, return_exceptions=True)
        events: list[NewsEvent] = []
        seen: set[str] = set()
        for result in results:
            if isinstance(result, Exception):
                continue
            for event in result:
                key = f"{event.title.lower()}::{event.url or ''}"
                if key in seen:
                    continue
                seen.add(key)
                events.append(event)
        return events

    async def _fetch_feed(self, client: httpx.AsyncClient, url: str) -> list[NewsEvent]:
        response = await client.get(url, headers={"User-Agent": "threading-bot-news-parser/1.0"})
        response.raise_for_status()
        return self._parse_rss(response.text, source=url)

    def _parse_rss(self, text: str, source: str) -> list[NewsEvent]:
        try:
            root = ElementTree.fromstring(text.encode("utf-8"))
        except ElementTree.ParseError:
            return []
        events: list[NewsEvent] = []
        for item in root.findall(".//item")[:80]:
            title = self._node_text(item, "title")
            if not title:
                continue
            link = self._node_text(item, "link") or None
            published = self._parse_dt(self._node_text(item, "pubDate") or self._node_text(item, "published"))
            description = self._node_text(item, "description")
            score, impact, keywords = self._impact(title, description)
            events.append(
                NewsEvent(
                    title=title,
                    source=source,
                    published_at=published,
                    url=link,
                    impact=impact,
                    score=score,
                    matched_keywords=keywords,
                )
            )
        return events

    def _node_text(self, item: ElementTree.Element, name: str) -> str:
        node = item.find(name)
        if node is None or node.text is None:
            return ""
        return " ".join(unescape(node.text).replace("\n", " ").split())

    def _parse_dt(self, value: str) -> datetime | None:
        if not value:
            return None
        try:
            parsed = parsedate_to_datetime(value)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            return parsed.astimezone(UTC)
        except (TypeError, ValueError):
            return None

    def _impact(self, title: str, description: str) -> tuple[int, str, list[str]]:
        text = f"{title} {description}".lower()
        keywords = [keyword for keyword in self._settings.news_high_impact_keyword_list() if keyword in text]
        score = len(keywords) * 2
        if any(keyword in text for keyword in ["breaking", "urgent", "unexpected", "surprise"]):
            score += 2
        impact = "high" if score >= 2 else "medium" if score == 1 else "low"
        return score, impact, keywords

    def _dedupe_events(self, events: list[NewsEvent]) -> list[NewsEvent]:
        result: list[NewsEvent] = []
        seen: set[str] = set()
        for event in events:
            key = f"{event.title.lower()}::{event.url or ''}"
            if key in seen:
                continue
            seen.add(key)
            result.append(event)
        return result

    def _symbol_events(self, events: list[NewsEvent], symbol: str | None) -> list[NewsEvent]:
        normalized_symbol = str(symbol or "").upper().replace("-", "")
        base = normalized_symbol.replace("USDT", "").replace("BUSD", "").replace("USDC", "")
        if not base:
            return []
        aliases = {
            "BTC": {"btc", "bitcoin"},
            "ETH": {"eth", "ethereum", "ether"},
            "BNB": {"bnb", "binance"},
            "SOL": {"sol", "solana"},
            "XRP": {"xrp", "ripple"},
            "DOGE": {"doge", "dogecoin"},
            "ADA": {"ada", "cardano"},
        }
        terms = aliases.get(base, {base.lower()})
        return [event for event in events if any(term in self._event_text(event) for term in terms)]

    def _market_events(self, events: list[NewsEvent], market: str | None) -> list[NewsEvent]:
        market_text = str(market or "").lower()
        macro_terms = {
            "fed", "fomc", "cpi", "nfp", "nonfarm", "inflation", "rate", "gdp", "pmi", "ppi",
            "treasury", "yields", "dollar", "tariff", "ecb", "boj", "boe", "powell",
        }
        crypto_terms = {
            "bitcoin", "btc", "ethereum", "eth", "crypto", "stablecoin", "binance", "coinbase",
            "sec", "etf", "hack", "exploit", "liquidation", "whale", "defi", "solana", "xrp",
        }
        terms = set(macro_terms)
        if market_text in {"spot", "futures", "crypto"}:
            terms |= crypto_terms
        return [event for event in events if any(term in self._event_text(event) for term in terms)]

    def _event_text(self, event: NewsEvent) -> str:
        return f"{event.title} {' '.join(event.matched_keywords)} {event.source}".lower()
