from __future__ import annotations

import time

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from config import settings
from services.price_client import PriceClient
from services.storage import JsonStorage

storage = JsonStorage()
price_client = PriceClient()


def _is_allowed(update: Update) -> bool:
    message = update.effective_message
    chat = update.effective_chat

    if message is None or chat is None:
        return False

    if settings.target_chat_id is not None and chat.id != settings.target_chat_id:
        return False

    if settings.source_thread_id is not None:
        if getattr(message, "message_thread_id", None) != settings.source_thread_id:
            return False

    return True


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update):
        return

    await update.effective_message.reply_text(
        "Ticker bot is running.\n"
        "Use /commands to view available commands.\n"
        "Use /topstock to view top stocks.\n"
        "Use /topcrypto to view top crypto symbols.\n"
        "Use /watchlist to view saved symbols.\n"
        "Use /removewatchlist to remove saved symbols.\n"
        "Use /pricealert to create a price alert.\n"
        "Use /pricealertlist to show saved price alerts.\n"
        "Use /removealert to remove saved price alerts.\n\n"
        "Examples:\n"
        "/s.aapl\n"
        "/c.btc\n"
        "/aapl\n"
        "/doge\n"
        "/xau"
    )


async def commands_ls(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update):
        return

    text = (
        "Available commands:\n\n"
        "/start\n"
        "/commands\n"
        "/topstock\n"
        "/topcrypto\n"
        "/watchlist\n"
        "/removewatchlist\n"
        "/pricealert\n"
        "/pricealertlist\n"
        "/removealert\n\n"
        "Forced API commands:\n"
        "/s.aapl\n"
        "/c.btc\n\n"
        "Auto-scan commands:\n"
        "/aapl\n"
        "/doge\n"
        "/btc\n"
        "/xau\n"
        "/xag\n"
        "/xpt\n"
        "/wti"
    )
    await update.effective_message.reply_text(text)


def _parse_command(command_text: str) -> tuple[str, str] | None:
    value = command_text.lstrip("/").split("@")[0].strip().lower()
    if not value:
        return None

    if "." in value:
        prefix, symbol = value.split(".", 1)
        symbol = symbol.strip().upper()

        if prefix not in {"s", "c"}:
            return None
        if not symbol or not symbol.replace("-", "").isalnum():
            return None
        if len(symbol) > 20:
            return None

        asset_type = "stock" if prefix == "s" else "crypto"
        return asset_type, symbol

    symbol = value.upper()
    if not symbol.isalnum():
        return None
    if len(symbol) > 20:
        return None

    if symbol in {"XAU", "XAG", "XPT", "WTI"}:
        return "metal", symbol

    return "scan", symbol


def _asset_type_from_result(source_name: str) -> str:
    if source_name == "coingecko":
        return "crypto"
    if source_name == "gold-api":
        return "metal"
    return "stock"


async def dynamic_symbol_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update):
        return

    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    if message is None or chat is None or not message.text:
        return

    raw_command = message.text.split()[0]
    lowered = raw_command.lstrip("/").split("@")[0].lower()

    reserved = {
        "start", "commands", "topstock", "topcrypto",
        "watchlist", "removewatchlist", "pricealert",
        "pricealertlist", "removealert", "cancel",
    }
    if lowered in reserved:
        return

    parsed = _parse_command(raw_command)
    if parsed is None:
        return

    asset_type, symbol = parsed
    thread_id = getattr(message, "message_thread_id", None)
    started = time.perf_counter()
    command = raw_command.split()[0]

    event = storage.build_event(
        command=command,
        asset_name=asset_type,
        symbol=symbol,
        chat_id=chat.id,
        thread_id=thread_id,
        user_id=getattr(user, "id", None),
        username=getattr(user, "username", None),
    )

    try:
        result = price_client.fetch_price(asset_name=asset_type, symbol=symbol)
        duration_ms = round((time.perf_counter() - started) * 1000, 2)

        event.update(
            {
                "status": "success",
                "api_source": result.source_name,
                "currency": result.currency,
                "price": result.price,
                "api_timestamp": result.raw_timestamp,
                "response_timestamp": result.fetched_at,
                "duration_ms": duration_ms,
            }
        )
        storage.append(event)

        title = {
            "gold-api": "Metal / Energy Price",
            "coingecko": "Crypto Price",
            "alphavantage": "Stock Price",
            "alphavantage-commodity": "Commodity Price",
        }.get(result.source_name, "Price")

        resolved_asset_type = _asset_type_from_result(result.source_name)

        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        text="Add to watchlist",
                        callback_data=f"wl:add:{resolved_asset_type}:{result.symbol}:{result.price}",
                    ),
                    InlineKeyboardButton(
                        text="Set alert",
                        callback_data=f"alrt:start:{resolved_asset_type}:{result.symbol}:{result.price}",
                    ),
                ]
            ]
        )

        text = (
            f"<b>{title}</b>\n"
            f"Symbol: <code>{result.symbol}</code>\n"
            f"Price: <b>{result.price:,.4f} {result.currency}</b>\n"
            f"Source: <code>{result.source_name}</code>\n"
            f"Fetched: <code>{result.fetched_at}</code>"
        )
        await message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)

    except Exception as exc:
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        event.update(
            {
                "status": "ignored_error",
                "error_message": str(exc),
                "duration_ms": duration_ms,
            }
        )
        storage.append(event)
        return