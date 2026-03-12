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


class PriceClient:
    def __init__(self, timeout: int | None = None) -> None:
        self.timeout = timeout or settings.request_timeout

    def fetch_price(self, asset_name: str, symbol: str) -> PriceResult:
        symbol = symbol.upper()

        if symbol in {"XAU", "XAG", "XPT", "XPD"}:
            return self._fetch_gold_price(asset_name, symbol)

        if symbol in {"BTC", "ETH", "SOL", "XRP"}:
            return self._fetch_coingecko_price(asset_name, symbol)

        raise ValueError(f"No provider configured for symbol: {symbol}")

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

    def _fetch_coingecko_price(self, asset_name: str, symbol: str) -> PriceResult:
        coin_map = {
            "BTC": "bitcoin",
            "ETH": "ethereum",
            "SOL": "solana",
            "XRP": "ripple",
        }

        coin_id = coin_map[symbol]
        params = {
            "ids": coin_id,
            "vs_currencies": settings.default_fiat,
            "include_last_updated_at": "true",
        }

        headers = {"Accept": "application/json"}
        if settings.coingecko_api_key:
            headers["x-cg-demo-api-key"] = settings.coingecko_api_key

        response = requests.get(
            settings.coingecko_api_url,
            params=params,
            headers=headers,
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()

        if coin_id not in payload or settings.default_fiat not in payload[coin_id]:
            raise ValueError(f"Unexpected CoinGecko response: {payload}")

        return PriceResult(
            asset_name=asset_name,
            symbol=symbol,
            currency=settings.default_fiat.upper(),
            price=float(payload[coin_id][settings.default_fiat]),
            fetched_at=datetime.now(timezone.utc).isoformat(),
            raw_timestamp=payload[coin_id].get("last_updated_at"),
            source_name="coingecko",
            raw_response=payload,
        )