from __future__ import annotations

from datetime import datetime, timedelta, timezone

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from config import settings
from logger import logger
from services.alert_service import AlertService
from services.price_client import PriceClient
from services.watchlist_service import WatchlistService

watchlist_service = WatchlistService()
alert_service = AlertService()
price_client = PriceClient()

ALERT_COOLDOWN_MINUTES = 30


def _is_allowed(update: Update) -> bool:
    message = update.effective_message
    chat = update.effective_chat
    callback = update.callback_query

    if chat is None:
        return False

    if settings.target_chat_id is not None and chat.id != settings.target_chat_id:
        return False

    if settings.source_thread_id is not None:
        msg = message or (callback.message if callback else None)
        if msg is not None and getattr(msg, "message_thread_id", None) != settings.source_thread_id:
            return False

    return True


def _symbol_asset_type(symbol: str) -> str:
    symbol = symbol.upper()
    if symbol in {"XAU", "XAG", "XPT", "WTI"}:
        return "metal"
    return "scan"


def _clear_alert_state(context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop("awaiting_alert_symbol", None)
    context.user_data.pop("awaiting_alert_price", None)
    context.user_data.pop("alert_symbol", None)
    context.user_data.pop("alert_asset_type", None)
    context.user_data.pop("alert_last_price", None)


async def watchlist_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update):
        return

    chat = update.effective_chat
    user = update.effective_user
    items = watchlist_service.list_items(chat.id, getattr(user, "id", None))

    if not items:
        await update.effective_message.reply_text("Your watchlist is empty.")
        return

    lines = ["Watchlist:\n"]

    for idx, item in enumerate(items, start=1):
        try:
            result = price_client.fetch_price(item["asset_type"], item["symbol"])
            lines.append(
                f"{idx:02d}. {item['symbol']} | {result.price:,.4f} {result.currency}"
            )
        except Exception:
            lines.append(f"{idx:02d}. {item['symbol']} | price unavailable")

    await update.effective_message.reply_text("\n".join(lines))


async def removewatchlist_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update):
        return

    chat = update.effective_chat
    user = update.effective_user
    items = watchlist_service.list_items(chat.id, getattr(user, "id", None))

    if not items:
        await update.effective_message.reply_text("Your watchlist is empty.")
        return

    keyboard = [
        [InlineKeyboardButton(text=f"{item['symbol']}", callback_data=f"wlrm:{item['id']}")]
        for item in items
    ]
    await update.effective_message.reply_text(
        "Choose a watchlist item to remove:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def pricealertlist_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update):
        return

    chat = update.effective_chat
    user = update.effective_user
    alerts = alert_service.list_active_alerts(chat.id, getattr(user, "id", None))

    if not alerts:
        await update.effective_message.reply_text("You have no active price alerts.")
        return

    lines = ["Active price alerts:\n"]
    for idx, alert in enumerate(alerts, start=1):
        lines.append(
            f"{idx:02d}. {alert['symbol']} | reaches {float(alert['target_price']):,.4f}"
        )

    await update.effective_message.reply_text("\n".join(lines))


async def removealert_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update):
        return

    chat = update.effective_chat
    user = update.effective_user
    alerts = alert_service.list_active_alerts(chat.id, getattr(user, "id", None))

    if not alerts:
        await update.effective_message.reply_text("You have no active price alerts.")
        return

    keyboard = [
        [
            InlineKeyboardButton(
                text=f"{alert['symbol']} | reaches {float(alert['target_price']):,.4f}",
                callback_data=f"alrm:{alert['id']}",
            )
        ]
        for alert in alerts
    ]
    await update.effective_message.reply_text(
        "Choose an alert to remove:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def watchlist_remove_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None:
        return

    await query.answer()
    if not _is_allowed(update):
        return

    data = query.data or ""
    if not data.startswith("wlrm:"):
        return

    item_id = data.split(":", 1)[1]
    chat = update.effective_chat
    user = update.effective_user

    removed = watchlist_service.remove_item(item_id, chat.id, getattr(user, "id", None))
    if removed:
        await query.edit_message_text("Removed from watchlist.")
    else:
        await query.edit_message_text("Watchlist item not found.")


async def remove_alert_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None:
        return

    await query.answer()
    if not _is_allowed(update):
        return

    data = query.data or ""
    if not data.startswith("alrm:"):
        return

    alert_id = data.split(":", 1)[1]
    chat = update.effective_chat
    user = update.effective_user

    removed = alert_service.remove_alert(alert_id, chat.id, getattr(user, "id", None))
    if removed:
        await query.edit_message_text("Removed alert.")
    else:
        await query.edit_message_text("Alert not found.")


async def add_watchlist_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None:
        return

    await query.answer()
    if not _is_allowed(update):
        return

    parts = (query.data or "").split(":", 4)
    if len(parts) != 5:
        await query.message.reply_text("Invalid watchlist action.")
        return

    _, _, asset_type, symbol, price = parts

    chat = update.effective_chat
    user = update.effective_user
    existing_items = watchlist_service.list_items(chat.id, getattr(user, "id", None))

    if any(item["symbol"] == symbol.upper() for item in existing_items):
        await query.message.reply_text(f"{symbol.upper()} is already in your watchlist.")
        return

    watchlist_service.add_item(
        chat_id=chat.id,
        user_id=getattr(user, "id", None),
        symbol=symbol.upper(),
        asset_type=asset_type,
        quantity=1.0,
        added_price=float(price),
        currency=settings.default_fiat.upper(),
    )

    logger.info("WATCHLIST_ADDED %s", symbol.upper())
    await query.message.reply_text(f"Added {symbol.upper()} to watchlist.")


async def pricealert_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update):
        return

    _clear_alert_state(context)
    context.user_data["awaiting_alert_symbol"] = True

    await update.effective_message.reply_text(
        "Reply with the symbol for the alert.\nExamples:\nBTC\nAAPL\nXAU"
    )


async def alert_button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None:
        return

    await query.answer()
    if not _is_allowed(update):
        return

    parts = (query.data or "").split(":", 4)
    if len(parts) != 5:
        await query.message.reply_text("Invalid alert action.")
        return

    _, _, asset_type, symbol, current_price = parts

    _clear_alert_state(context)
    context.user_data["awaiting_alert_price"] = True
    context.user_data["alert_symbol"] = symbol.upper()
    context.user_data["alert_asset_type"] = asset_type
    context.user_data["alert_last_price"] = float(current_price)

    logger.info("ALERT_BUTTON_START symbol=%s asset_type=%s", symbol.upper(), asset_type)

    await query.message.reply_text(
        f"Set alert for {symbol.upper()}.\nCurrent price: {float(current_price):,.4f}\nReply with target price:"
    )


async def alert_text_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update):
        return

    message = update.effective_message
    if message is None or not message.text:
        return

    if context.user_data.get("awaiting_alert_symbol"):
        await _handle_alert_symbol(update, context)
        return

    if context.user_data.get("awaiting_alert_price"):
        await _handle_alert_price(update, context)
        return


async def _handle_alert_symbol(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    symbol = (update.effective_message.text or "").strip().upper()
    if not symbol or not symbol.replace("-", "").isalnum():
        await update.effective_message.reply_text("Send a valid symbol.")
        return

    asset_type = _symbol_asset_type(symbol)

    try:
        result = price_client.fetch_price(asset_type, symbol)
    except Exception:
        await update.effective_message.reply_text("Could not find that symbol.")
        return

    context.user_data["awaiting_alert_symbol"] = False
    context.user_data["awaiting_alert_price"] = True
    context.user_data["alert_symbol"] = result.symbol.upper()
    context.user_data["alert_asset_type"] = (
        "crypto" if result.source_name == "coingecko"
        else "stock" if result.source_name.startswith("alphavantage")
        else "metal"
    )
    context.user_data["alert_last_price"] = float(result.price)

    logger.info(
        "ALERT_SYMBOL_RESOLVED symbol=%s asset_type=%s price=%s",
        result.symbol,
        context.user_data["alert_asset_type"],
        result.price,
    )

    await update.effective_message.reply_text(
        f"Current price for {result.symbol}: {result.price:,.4f} {result.currency}\n"
        "Reply with target alert price:"
    )


async def _handle_alert_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (update.effective_message.text or "").strip()
    try:
        target_price = float(text)
    except ValueError:
        await update.effective_message.reply_text("Send a valid number for target price.")
        return

    chat = update.effective_chat
    user = update.effective_user
    symbol = context.user_data.get("alert_symbol")
    asset_type = context.user_data.get("alert_asset_type", "scan")
    last_price = context.user_data.get("alert_last_price")

    if not symbol:
        _clear_alert_state(context)
        await update.effective_message.reply_text("Alert setup expired. Try again.")
        return

    alert = alert_service.add_alert(
        chat_id=chat.id,
        user_id=getattr(user, "id", None),
        symbol=symbol,
        asset_type=asset_type,
        target_price=target_price,
        last_price=last_price,
    )

    logger.info(
        "ALERT_CREATED symbol=%s target=%s direction=%s",
        alert["symbol"],
        alert["target_price"],
        alert.get("direction"),
    )

    _clear_alert_state(context)

    await update.effective_message.reply_text(
        f"Price alert set for {alert['symbol']} when price reaches {alert['target_price']:,.4f}."
    )


async def run_alert_checks(context: ContextTypes.DEFAULT_TYPE) -> None:
    alerts = alert_service.active_alerts()
    now = datetime.now(timezone.utc)

    logger.info("ALERT_CHECK_START count=%s", len(alerts))

    for alert in alerts:
        try:
            result = price_client.fetch_price(alert["asset_type"], alert["symbol"])
            current = float(result.price)
            target = float(alert["target_price"])

            # backward compatible for old alerts without direction
            direction = alert.get("direction")
            if not direction:
                direction = "up" if current <= target else "down"

            triggered = (direction == "up" and current >= target) or (
                direction == "down" and current <= target
            )

            logger.info(
                "ALERT_CHECK_ITEM symbol=%s current=%s target=%s direction=%s triggered=%s",
                alert["symbol"],
                current,
                target,
                direction,
                triggered,
            )

            if not triggered:
                continue

            last_triggered_at = alert.get("last_triggered_at")
            if last_triggered_at:
                try:
                    last_dt = datetime.fromisoformat(last_triggered_at)
                    if now - last_dt < timedelta(minutes=ALERT_COOLDOWN_MINUTES):
                        logger.info(
                            "ALERT_SKIPPED_COOLDOWN symbol=%s last_triggered_at=%s",
                            alert["symbol"],
                            last_triggered_at,
                        )
                        continue
                except ValueError:
                    pass

            await context.bot.send_message(
                chat_id=alert["chat_id"],
                text=(
                    f"Price alert triggered\n"
                    f"Symbol: {alert['symbol']}\n"
                    f"Current: {current:,.4f} {result.currency}\n"
                    f"Target: {target:,.4f}"
                ),
            )

            alert_service.mark_triggered(alert["id"])
            logger.info("ALERT_TRIGGERED symbol=%s", alert["symbol"])

        except Exception as exc:
            logger.warning("ALERT_CHECK_FAILED symbol=%s error=%s", alert.get("symbol"), str(exc))


def build_watchlist_callback_handler() -> CallbackQueryHandler:
    return CallbackQueryHandler(add_watchlist_callback, pattern=r"^wl:add:")


def build_alert_button_handler() -> CallbackQueryHandler:
    return CallbackQueryHandler(alert_button_callback, pattern=r"^alrt:start:")


def build_watchlist_remove_handler() -> CallbackQueryHandler:
    return CallbackQueryHandler(watchlist_remove_callback, pattern=r"^wlrm:")


def build_remove_alert_handler() -> CallbackQueryHandler:
    return CallbackQueryHandler(remove_alert_callback, pattern=r"^alrm:")


def build_alert_text_handler() -> MessageHandler:
    return MessageHandler(filters.TEXT & ~filters.COMMAND, alert_text_router)