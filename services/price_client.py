from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import requests

from config import settings


@dataclass(frozen=True)
class PriceResult:
    asset_name: str
    symbol: str
    currency: str
    price: float
    fetched_at: str
    raw_timestamp: str | int | None
    source_name: str
    raw_response: dict[str, Any]


class SymbolNotFoundError(ValueError):
    pass


class PriceClient:
    def __init__(self, timeout: int | None = None) -> None:
        self.timeout = timeout or settings.request_timeout

    def fetch_price(self, asset_name: str, symbol: str) -> PriceResult:
        symbol = symbol.upper()

        # metals on gold api
        if symbol in {"XAU", "XAG", "XPT"}:
            return self._fetch_gold_price(asset_name, symbol)

        # WTI on Alpha Vantage commodity endpoint
        if symbol == "WTI":
            return self._fetch_wti_price(asset_name, symbol)

        # forced routing
        if asset_name == "stock":
            return self._fetch_stock_price(asset_name, symbol)

        if asset_name == "crypto":
            return self._fetch_crypto_by_symbol(asset_name, symbol)

        # auto scan
        try:
            return self._fetch_stock_price(asset_name, symbol)
        except SymbolNotFoundError:
            return self._fetch_crypto_by_symbol(asset_name, symbol)

    def _fetch_gold_price(self, asset_name: str, symbol: str) -> PriceResult:
        headers = {"Accept": "application/json"}
        if settings.gold_api_key:
            headers["x-access-token"] = settings.gold_api_key

        url = settings.gold_api_url.format(symbol=symbol)
        response = requests.get(url, headers=headers, timeout=self.timeout)
        response.raise_for_status()
        payload = response.json()

        if "price" not in payload:
            raise ValueError(f"Unexpected gold API response: {payload}")

        return PriceResult(
            asset_name=asset_name,
            symbol=str(payload.get("symbol", symbol)).upper(),
            currency=str(payload.get("currency", "USD")).upper(),
            price=float(payload["price"]),
            fetched_at=datetime.now(timezone.utc).isoformat(),
            raw_timestamp=payload.get("updatedAt") or payload.get("timestamp"),
            source_name="gold-api",
            raw_response=payload,
        )

    def _fetch_wti_price(self, asset_name: str, symbol: str) -> PriceResult:
        if not settings.alphavantage_api_key:
            raise ValueError("Missing ALPHAVANTAGE_API_KEY")

        params = {
            "function": "WTI",
            "interval": "daily",
            "apikey": settings.alphavantage_api_key,
        }

        response = requests.get(
            settings.alphavantage_api_url,
            params=params,
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()

        data = payload.get("data", [])
        if not isinstance(data, list) or not data:
            raise SymbolNotFoundError(f"WTI data not found: {payload}")

        latest = None
        for item in data:
            value = str(item.get("value", "")).strip()
            if value and value != ".":
                latest = item
                break

        if latest is None:
            raise SymbolNotFoundError(f"WTI latest value not found: {payload}")

        return PriceResult(
            asset_name=asset_name,
            symbol="WTI",
            currency="USD",
            price=float(latest["value"]),
            fetched_at=datetime.now(timezone.utc).isoformat(),
            raw_timestamp=latest.get("date"),
            source_name="alphavantage-commodity",
            raw_response=payload,
        )

    def _fetch_stock_price(self, asset_name: str, symbol: str) -> PriceResult:
        if not settings.alphavantage_api_key:
            raise ValueError("Missing ALPHAVANTAGE_API_KEY")

        params = {
            "function": "GLOBAL_QUOTE",
            "symbol": symbol,
            "apikey": settings.alphavantage_api_key,
        }

        response = requests.get(
            settings.alphavantage_api_url,
            params=params,
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()

        quote = payload.get("Global Quote", {})
        price = str(quote.get("05. price", "")).strip()

        if not quote or not price:
            raise SymbolNotFoundError(f"Stock symbol not found: {symbol}")

        return PriceResult(
            asset_name=asset_name,
            symbol=str(quote.get("01. symbol", symbol)).upper(),
            currency="USD",
            price=float(price),
            fetched_at=datetime.now(timezone.utc).isoformat(),
            raw_timestamp=quote.get("07. latest trading day"),
            source_name="alphavantage",
            raw_response=payload,
        )

    def _fetch_crypto_by_symbol(self, asset_name: str, symbol: str) -> PriceResult:
        headers = {"Accept": "application/json"}
        if settings.coingecko_api_key:
            headers["x-cg-demo-api-key"] = settings.coingecko_api_key

        markets_url = settings.coingecko_api_url.replace("/simple/price", "/coins/markets")
        params = {
            "vs_currency": settings.default_fiat,
            "symbols": symbol.lower(),
            "include_tokens": "all",
            "order": "market_cap_desc",
            "per_page": 10,
            "page": 1,
            "sparkline": "false",
        }

        response = requests.get(
            markets_url,
            params=params,
            headers=headers,
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()

        if not isinstance(payload, list) or not payload:
            raise SymbolNotFoundError(f"Crypto symbol not found: {symbol}")

        exact_matches = [
            item for item in payload
            if str(item.get("symbol", "")).upper() == symbol
        ]
        candidates = exact_matches or payload

        def rank_key(item: dict[str, Any]) -> tuple[int, float]:
            market_cap_rank = item.get("market_cap_rank")
            if market_cap_rank is None:
                market_cap_rank = 10**9
            market_cap = item.get("market_cap") or 0
            return (int(market_cap_rank), -float(market_cap))

        best = sorted(candidates, key=rank_key)[0]

        current_price = best.get("current_price")
        if current_price is None:
            raise SymbolNotFoundError(f"Crypto symbol not found: {symbol}")

        return PriceResult(
            asset_name=asset_name,
            symbol=str(best.get("symbol", symbol)).upper(),
            currency=settings.default_fiat.upper(),
            price=float(current_price),
            fetched_at=datetime.now(timezone.utc).isoformat(),
            raw_timestamp=best.get("last_updated"),
            source_name="coingecko",
            raw_response=best,
        )