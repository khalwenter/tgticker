from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from config import settings
from logger import logger
from services.market_discovery import MarketDiscoveryService

market_service = MarketDiscoveryService()


def _is_allowed(update: Update) -> bool:
    message = update.effective_message
    chat = update.effective_chat

    if chat is None:
        return False

    if settings.target_chat_id is not None and chat.id != settings.target_chat_id:
        return False

    if settings.source_thread_id is not None and message is not None:
        if getattr(message, "message_thread_id", None) != settings.source_thread_id:
            return False

    return True


def _format_stock_price(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return "N/A"
    return f"${value}"


async def top_stock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update):
        return

    try:
        items = market_service.fetch_top_stocks(limit=50)
        if not items:
            await update.effective_message.reply_text("No stock symbols found.")
            return

        lines = ["Top stocks:\n"]
        for idx, item in enumerate(items, start=1):
            lines.append(
                f"{idx:02d}. /{item.symbol.lower()} | {item.symbol} | {_format_stock_price(item.price)} | {item.change_percentage} | {item.source_bucket}"
            )

        await update.effective_message.reply_text("\n".join(lines))
    except Exception as exc:
        logger.exception("Failed to fetch top stocks")
        await update.effective_message.reply_text(f"Failed to fetch top stocks: {exc}")


async def top_crypto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update):
        return

    try:
        items = market_service.fetch_top_crypto(limit=50)
        if not items:
            await update.effective_message.reply_text("No crypto symbols found.")
            return

        lines = ["Top crypto symbols:\n"]
        for idx, item in enumerate(items, start=1):
            lines.append(
                f"{idx:02d}. /{item.symbol.lower()} | {item.symbol} | ${item.current_price} USD | rank {item.market_cap_rank}"
            )

        await update.effective_message.reply_text("\n".join(lines))
    except Exception as exc:
        logger.exception("Failed to fetch top crypto")
        await update.effective_message.reply_text(f"Failed to fetch top crypto: {exc}")