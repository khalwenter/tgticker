from __future__ import annotations

import csv
import io
from dataclasses import dataclass

import requests

from config import settings


@dataclass(frozen=True)
class StockBrowseItem:
    symbol: str
    name: str
    price: str
    change_percentage: str
    source_bucket: str


@dataclass(frozen=True)
class CryptoBrowseItem:
    symbol: str
    name: str
    current_price: str
    market_cap_rank: int | None


class MarketDiscoveryService:
    def __init__(self, timeout: int | None = None) -> None:
        self.timeout = timeout or settings.request_timeout
        self._listing_name_map_cache: dict[str, str] | None = None

    def _fetch_listing_name_map(self) -> dict[str, str]:
        if self._listing_name_map_cache is not None:
            return self._listing_name_map_cache

        if not settings.alphavantage_api_key:
            raise ValueError("Missing ALPHAVANTAGE_API_KEY")

        params = {
            "function": "LISTING_STATUS",
            "state": "active",
            "apikey": settings.alphavantage_api_key,
        }

        response = requests.get(
            settings.alphavantage_api_url,
            params=params,
            timeout=self.timeout,
        )
        response.raise_for_status()

        text = response.text.strip()
        if not text:
            self._listing_name_map_cache = {}
            return self._listing_name_map_cache

        reader = csv.DictReader(io.StringIO(text))
        mapping: dict[str, str] = {}

        for row in reader:
            symbol = str(row.get("symbol", "")).upper().strip()
            name = str(row.get("name", "")).strip()
            if symbol and name and symbol not in mapping:
                mapping[symbol] = name

        self._listing_name_map_cache = mapping
        return mapping

    def fetch_top_stocks(self, limit: int = 50) -> list[StockBrowseItem]:
        if not settings.alphavantage_api_key:
            raise ValueError("Missing ALPHAVANTAGE_API_KEY")

        params = {
            "function": "TOP_GAINERS_LOSERS",
            "apikey": settings.alphavantage_api_key,
        }

        response = requests.get(
            settings.alphavantage_api_url,
            params=params,
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()

        name_map = self._fetch_listing_name_map()

        buckets = [
            ("top_gainers", "gainer"),
            ("top_losers", "loser"),
            ("most_actively_traded", "active"),
        ]

        seen: set[str] = set()
        result: list[StockBrowseItem] = []

        for payload_key, bucket_name in buckets:
            items = payload.get(payload_key, [])
            for item in items:
                symbol = str(item.get("ticker", "")).upper().strip()
                if not symbol or symbol in seen:
                    continue

                seen.add(symbol)

                raw_name = name_map.get(symbol, "").strip()
                display_name = raw_name if raw_name else f"Unknown name ({symbol})"

                result.append(
                    StockBrowseItem(
                        symbol=symbol,
                        name=display_name,
                        price=str(item.get("price", "")).strip(),
                        change_percentage=str(item.get("change_percentage", "")).strip(),
                        source_bucket=bucket_name,
                    )
                )

                if len(result) >= limit:
                    return result

        if not result:
            raise ValueError(f"Unexpected Alpha Vantage TOP_GAINERS_LOSERS response: {payload}")

        return result

    def fetch_top_crypto(self, limit: int = 50) -> list[CryptoBrowseItem]:
        params = {
            "vs_currency": settings.default_fiat,
            "order": "market_cap_desc",
            "per_page": limit,
            "page": 1,
            "sparkline": "false",
        }

        headers = {"Accept": "application/json"}
        if settings.coingecko_api_key:
            headers["x-cg-demo-api-key"] = settings.coingecko_api_key

        markets_url = settings.coingecko_api_url.replace("/simple/price", "/coins/markets")

        response = requests.get(
            markets_url,
            params=params,
            headers=headers,
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()

        result: list[CryptoBrowseItem] = []
        for item in payload[:limit]:
            result.append(
                CryptoBrowseItem(
                    symbol=str(item.get("symbol", "")).upper(),
                    name=str(item.get("name", "")),
                    current_price=str(item.get("current_price", "")),
                    market_cap_rank=item.get("market_cap_rank"),
                )
            )

        return result