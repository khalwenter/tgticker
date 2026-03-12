from __future__ import annotations

import time

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from config import settings
from logger import logger
from services.price_client import PriceClient
from services.storage import JsonStorage
from services.ticker_registry import TickerRegistry

storage = JsonStorage()
price_client = PriceClient()
registry = TickerRegistry(settings.ticker_file)


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
        "Use /createticker to add new ticker commands.\n"
        "Use /removecommands to remove a ticker command.\n"
        "Use /removetickers to manage tickers."
    )


async def commands_ls(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update):
        return

    tickers = registry.load()

    base_commands = [
        "/start",
        "/commands",
        "/createticker",
        "/removecommands",
        "/listtickers",
        "/removetickers",
    ]

    ticker_commands = [f"/{item['command']}price" for item in tickers]

    text = "Available commands:\n\n" + "\n".join(base_commands + ticker_commands)
    await update.effective_message.reply_text(text)


async def dynamic_price_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update):
        return

    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    if message is None or chat is None or not message.text:
        return

    raw_command = message.text.split()[0]
    command_name = raw_command.lstrip("/").split("@")[0].lower()

    reserved = {
        "start",
        "commands",
        "createticker",
        "removecommands",
        "listtickers",
        "removetickers",
        "cancel",
    }
    if command_name in reserved:
        return

    if not command_name.endswith("price"):
        return

    asset_name = command_name[:-5]
    ticker = registry.get_by_command(asset_name)

    if not ticker:
        await message.reply_text(f"Ticker command /{command_name} not found.")
        return

    symbol = ticker["symbol"]
    command = f"/{command_name}"
    thread_id = getattr(message, "message_thread_id", None)
    started = time.perf_counter()

    logger.info(
        "START %s chat_id=%s thread_id=%s user_id=%s symbol=%s",
        command,
        chat.id,
        thread_id,
        getattr(user, "id", None),
        symbol,
    )

    event = storage.build_event(
        command=command,
        asset_name=asset_name,
        symbol=symbol,
        chat_id=chat.id,
        thread_id=thread_id,
        user_id=getattr(user, "id", None),
        username=getattr(user, "username", None),
    )

    try:
        result = price_client.fetch_price(asset_name=asset_name, symbol=symbol)
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

        logger.info(
            "END %s success chat_id=%s thread_id=%s symbol=%s price=%s currency=%s duration_ms=%s",
            command,
            chat.id,
            thread_id,
            result.symbol,
            result.price,
            result.currency,
            duration_ms,
        )

        text = (
            f"<b>{asset_name.upper()} Price</b>\n"
            f"Symbol: <code>{result.symbol}</code>\n"
            f"Price: <b>{result.price:,.2f} {result.currency}</b>\n"
            f"Source: <code>{result.source_name}</code>\n"
            f"Fetched: <code>{result.fetched_at}</code>"
        )
        await message.reply_text(text, parse_mode=ParseMode.HTML)

    except Exception as exc:
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        event.update(
            {
                "status": "error",
                "error_message": str(exc),
                "duration_ms": duration_ms,
            }
        )
        storage.append(event)
        logger.exception("Ticker request failed")
        await message.reply_text(
            f"Failed to fetch {asset_name.upper()} price. Check logs for details."
        )