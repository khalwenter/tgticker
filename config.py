from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _optional_int(value: str | None) -> int | None:
    if value is None or value.strip() == "":
        return None
    return int(value)


@dataclass(frozen=True)
class Settings:
    bot_token: str
    target_chat_id: int | None
    source_thread_id: int | None
    gold_api_url: str
    gold_api_key: str | None
    coingecko_api_url: str
    coingecko_api_key: str | None
    data_file: Path
    ticker_file: Path
    log_file: Path
    request_timeout: int
    default_fiat: str


settings = Settings(
    bot_token=os.getenv("BOT_TOKEN", ""),
    target_chat_id=_optional_int(os.getenv("TARGET_CHAT_ID")),
    source_thread_id=_optional_int(os.getenv("SOURCE_THREAD_ID")),
    gold_api_url=os.getenv("GOLD_API_URL", "https://api.gold-api.com/price/{symbol}"),
    gold_api_key=os.getenv("GOLD_API_KEY") or None,
    coingecko_api_url=os.getenv(
        "COINGECKO_API_URL",
        "https://api.coingecko.com/api/v3/simple/price",
    ),
    coingecko_api_key=os.getenv("COINGECKO_API_KEY") or None,
    data_file=BASE_DIR / os.getenv("DATA_FILE", "data/requests.json"),
    ticker_file=BASE_DIR / os.getenv("TICKER_FILE", "data/tickers.json"),
    log_file=BASE_DIR / os.getenv("LOG_FILE", "logs/bot.log"),
    request_timeout=int(os.getenv("REQUEST_TIMEOUT", "15")),
    default_fiat=os.getenv("DEFAULT_FIAT", "usd").lower(),
)


def validate_settings() -> None:
    if not settings.bot_token:
        raise ValueError("Missing BOT_TOKEN")

    settings.data_file.parent.mkdir(parents=True, exist_ok=True)
    settings.ticker_file.parent.mkdir(parents=True, exist_ok=True)
    settings.log_file.parent.mkdir(parents=True, exist_ok=True)

    if not settings.data_file.exists():
        settings.data_file.write_text("[]", encoding="utf-8")

    if not settings.ticker_file.exists():
        settings.ticker_file.write_text("[]", encoding="utf-8")