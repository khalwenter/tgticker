from __future__ import annotations

from dataclasses import dataclass

import requests

from config import settings


@dataclass(frozen=True)
class StockMatch:
    symbol: str
    name: str
    region: str
    currency: str
    match_score: str


@dataclass(frozen=True)
class StockBrowseItem:
    symbol: str
    price: str
    change_percentage: str
    source_bucket: str


class StockSymbolService:
    def __init__(self, timeout: int | None = None) -> None:
        self.timeout = timeout or settings.request_timeout

    def search(self, keywords: str, limit: int = 10) -> list[StockMatch]:
        if not settings.alphavantage_api_key:
            raise ValueError("Missing ALPHAVANTAGE_API_KEY")

        params = {
            "function": "SYMBOL_SEARCH",
            "keywords": keywords,
            "apikey": settings.alphavantage_api_key,
        }

        response = requests.get(
            settings.alphavantage_api_url,
            params=params,
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()

        matches = payload.get("bestMatches", [])
        result: list[StockMatch] = []

        for item in matches[:limit]:
            result.append(
                StockMatch(
                    symbol=str(item.get("1. symbol", "")).upper(),
                    name=str(item.get("2. name", "")),
                    region=str(item.get("4. region", "")),
                    currency=str(item.get("8. currency", "")),
                    match_score=str(item.get("9. matchScore", "")),
                )
            )

        return result

    def fetch_top_symbols(self, limit: int = 50) -> list[StockBrowseItem]:
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
                result.append(
                    StockBrowseItem(
                        symbol=symbol,
                        price=str(item.get("price", "")),
                        change_percentage=str(item.get("change_percentage", "")),
                        source_bucket=bucket_name,
                    )
                )

                if len(result) >= limit:
                    return result

        return result