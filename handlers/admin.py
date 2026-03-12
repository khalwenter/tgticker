from __future__ import annotations

from telegram import (
    Update,
    BotCommand,
    BotCommandScopeChat,
    ForceReply,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

from config import settings
from logger import logger
from services.ticker_registry import TickerRegistry

ASK_TICKER = 1
ASK_REMOVE = 2

registry = TickerRegistry(settings.ticker_file)


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


async def create_ticker_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not _is_allowed(update):
        return ConversationHandler.END

    await update.effective_message.reply_text(
        "Which command would you like to add?\n\n"
        "Reply in this format:\n"
        "<symbol>/<command>\n\n"
        "Example:\n"
        "xag/silver",
        reply_markup=ForceReply(selective=True),
    )
    return ASK_TICKER


async def create_ticker_save(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not _is_allowed(update):
        return ConversationHandler.END

    text = (update.effective_message.text or "").strip()
    logger.info("CREATE_TICKER received text=%s", text)

    if "/" not in text:
        await update.effective_message.reply_text(
            "Invalid format.\nUse: <symbol>/<command>\nExample: xag/silver"
        )
        return ASK_TICKER

    symbol_raw, command_raw = text.split("/", 1)
    symbol = symbol_raw.strip().upper()
    command = command_raw.strip().lower()

    if not symbol or not command:
        await update.effective_message.reply_text("Symbol or command cannot be empty.")
        return ASK_TICKER

    asset_type = "crypto" if symbol in {"BTC", "ETH", "SOL", "XRP"} else "metal"

    try:
        registry.add_ticker(command=command, symbol=symbol, asset_type=asset_type)
        await _refresh_bot_commands(context)
        await update.effective_message.reply_text(
            f"Added /{command}price for symbol {symbol}."
        )
    except Exception as exc:
        logger.exception("Failed to create ticker")
        await update.effective_message.reply_text(f"Failed to add ticker: {exc}")

    return ConversationHandler.END


async def remove_command_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not _is_allowed(update):
        return ConversationHandler.END

    tickers = registry.load()
    if not tickers:
        await update.effective_message.reply_text("No ticker commands to remove.")
        return ConversationHandler.END

    await update.effective_message.reply_text(
        "Which command do you want to remove?\n\n"
        "Reply with one of these formats:\n"
        "gold\n"
        "/goldprice\n"
        "/goldprice@tickerkhalbot",
        reply_markup=ForceReply(selective=True),
    )
    return ASK_REMOVE


def _normalize_remove_input(text: str) -> str:
    value = text.strip().lower()

    if value.startswith("/"):
        value = value[1:]

    value = value.split("@")[0]

    if value.endswith("price"):
        value = value[:-5]

    return value.strip()


async def remove_command_save(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not _is_allowed(update):
        return ConversationHandler.END

    text = (update.effective_message.text or "").strip()
    logger.info("REMOVE_COMMAND received text=%s", text)

    command = _normalize_remove_input(text)

    if not command:
        await update.effective_message.reply_text("Command name cannot be empty.")
        return ASK_REMOVE

    ticker = registry.get_by_command(command)
    if not ticker:
        await update.effective_message.reply_text(f"Command '{command}' not found.")
        return ASK_REMOVE

    registry.delete_ticker(command)
    await _refresh_bot_commands(context)
    await update.effective_message.reply_text(f"Removed /{command}price.")
    return ConversationHandler.END


async def cancel_create_ticker(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.effective_message:
        await update.effective_message.reply_text("Action cancelled.")
    return ConversationHandler.END


async def list_tickers(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update):
        return

    tickers = registry.load()
    if not tickers:
        await update.effective_message.reply_text("No tickers found.")
        return

    text = "\n".join(
        f"/{item['command']}price → {item['symbol']} ({item['asset_type']})"
        for item in tickers
    )
    await update.effective_message.reply_text(text)


async def remove_tickers_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update):
        return

    tickers = registry.load()
    if not tickers:
        await update.effective_message.reply_text("No tickers found.")
        return

    keyboard = []
    for item in tickers:
        keyboard.append([
            InlineKeyboardButton(
                text=f"{item['command']} → {item['symbol']}",
                callback_data=f"ticker:view:{item['command']}",
            )
        ])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.effective_message.reply_text(
        "Your tickers. Click one to remove:",
        reply_markup=reply_markup,
    )


async def ticker_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None:
        return

    await query.answer()

    if not _is_allowed(update):
        return

    data = query.data or ""
    parts = data.split(":")

    if len(parts) < 3:
        await query.edit_message_text("Invalid action.")
        return

    action = parts[1]
    command = parts[2]

    ticker = registry.get_by_command(command)

    if action == "view":
        if not ticker:
            await query.edit_message_text("Ticker not found.")
            return

        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        text="Remove",
                        callback_data=f"ticker:delete:{command}",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="Back",
                        callback_data="ticker:back:list",
                    )
                ],
            ]
        )

        await query.edit_message_text(
            f"Ticker: /{ticker['command']}price\n"
            f"Symbol: {ticker['symbol']}\n"
            f"Type: {ticker['asset_type']}\n\n"
            f"Do you want to remove it?",
            reply_markup=keyboard,
        )
        return

    if action == "delete":
        if not ticker:
            await query.edit_message_text("Ticker already removed.")
            return

        registry.delete_ticker(command)
        await _refresh_bot_commands(context)
        await query.edit_message_text(f"Removed /{command}price.")
        return

    if action == "back":
        tickers = registry.load()
        if not tickers:
            await query.edit_message_text("No tickers found.")
            return

        keyboard = []
        for item in tickers:
            keyboard.append([
                InlineKeyboardButton(
                    text=f"{item['command']} → {item['symbol']}",
                    callback_data=f"ticker:view:{item['command']}",
                )
            ])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "Your tickers. Click one to remove:",
            reply_markup=reply_markup,
        )
        return

    await query.edit_message_text("Unknown action.")


async def _refresh_bot_commands(context: ContextTypes.DEFAULT_TYPE) -> None:
    tickers = registry.load()
    commands = [
        BotCommand("start", "Start bot"),
        BotCommand("commands", "Show all commands"),
        BotCommand("createticker", "Create a new ticker command"),
        BotCommand("removecommands", "Remove a ticker command"),
        BotCommand("listtickers", "List all ticker commands"),
        BotCommand("removetickers", "Show clickable ticker removal list"),
    ]
    commands.extend(
        BotCommand(f"{item['command']}price", f"Get {item['symbol']} price")
        for item in tickers
    )

    await context.bot.set_my_commands(commands)

    if settings.target_chat_id is not None:
        await context.bot.set_my_commands(
            commands,
            scope=BotCommandScopeChat(chat_id=settings.target_chat_id),
        )


def build_admin_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("createticker", create_ticker_start)],
        states={
            ASK_TICKER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, create_ticker_save)
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel_create_ticker)],
        per_chat=True,
        per_user=True,
    )


def build_remove_command_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("removecommands", remove_command_start)],
        states={
            ASK_REMOVE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, remove_command_save)
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel_create_ticker)],
        per_chat=True,
        per_user=True,
    )


def build_ticker_callback_handler() -> CallbackQueryHandler:
    return CallbackQueryHandler(ticker_callback, pattern=r"^ticker:")