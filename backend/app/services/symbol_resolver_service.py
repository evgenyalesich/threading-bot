from __future__ import annotations

from app.models.symbol_mapping import SymbolMapping
from app.repositories.symbol_mapping_repository import SymbolMappingRepository


class SymbolResolverService:
    def __init__(self, repository: SymbolMappingRepository) -> None:
        self._repository = repository

    async def resolve(self, yfinance_symbol: str, market: str) -> str | None:
        normalized = yfinance_symbol.upper()
        if "-" not in normalized:
            return normalized
        mapping = await self._repository.get_by_yfinance(normalized, market)
        if mapping:
            return mapping.binance_symbol

        derived = self._derive_symbol(normalized)
        if derived:
            new_mapping = SymbolMapping(
                yfinance_symbol=normalized,
                binance_symbol=derived,
                market=market,
            )
            await self._repository.add(new_mapping)
            return derived
        return None

    def _derive_symbol(self, yfinance_symbol: str) -> str | None:
        if yfinance_symbol.endswith("-USD"):
            base = yfinance_symbol.replace("-USD", "")
            return f"{base}USDT".replace("-", "").upper()
        if yfinance_symbol.endswith("USDT"):
            return yfinance_symbol.replace("-", "").upper()
        return None
