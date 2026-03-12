from __future__ import annotations

import asyncio

from config import settings, validate_settings


async def error_handler(update: object, context) -> None:
    from logger import logger
    logger.exception("Telegram error occurred", exc_info=context.error)


async def _refresh_menu_commands(application) -> None:
    from telegram import BotCommand, BotCommandScopeChat, BotCommandScopeDefault

    fixed_commands = [
        BotCommand("start", "Start bot"),
        BotCommand("commands", "Show available commands"),
        BotCommand("topstock", "Show top stocks"),
        BotCommand("topcrypto", "Show top crypto"),
        BotCommand("watchlist", "Show watchlist"),
        BotCommand("removewatchlist", "Remove watchlist item"),
        BotCommand("pricealert", "Create price alert"),
        BotCommand("pricealertlist", "Show saved alerts"),
        BotCommand("removealert", "Remove saved alerts"),
    ]

    await application.bot.delete_my_commands(scope=BotCommandScopeDefault())
    await application.bot.set_my_commands(fixed_commands, scope=BotCommandScopeDefault())

    if settings.target_chat_id is not None:
        chat_scope = BotCommandScopeChat(chat_id=settings.target_chat_id)
        await application.bot.delete_my_commands(scope=chat_scope)
        await application.bot.set_my_commands(fixed_commands, scope=chat_scope)


async def run_bot() -> None:
    validate_settings()

    from telegram.ext import Application, CommandHandler, MessageHandler, filters
    from handlers.admin import top_crypto, top_stock
    from handlers.commands import start, commands_ls, dynamic_symbol_command
    from handlers.watchlist import (
        build_alert_button_handler,
        build_alert_text_handler,
        build_remove_alert_handler,
        build_watchlist_callback_handler,
        build_watchlist_remove_handler,
        pricealert_command,
        pricealertlist_command,
        removealert_command,
        removewatchlist_command,
        run_alert_checks,
        watchlist_command,
    )
    from logger import logger

    application = Application.builder().token(settings.bot_token).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("commands", commands_ls))
    application.add_handler(CommandHandler("topstock", top_stock))
    application.add_handler(CommandHandler("topcrypto", top_crypto))
    application.add_handler(CommandHandler("watchlist", watchlist_command))
    application.add_handler(CommandHandler("removewatchlist", removewatchlist_command))
    application.add_handler(CommandHandler("pricealert", pricealert_command))
    application.add_handler(CommandHandler("pricealertlist", pricealertlist_command))
    application.add_handler(CommandHandler("removealert", removealert_command))

    application.add_handler(build_watchlist_callback_handler())
    application.add_handler(build_alert_button_handler())
    application.add_handler(build_watchlist_remove_handler())
    application.add_handler(build_remove_alert_handler())

    application.add_handler(build_alert_text_handler(), group=0)

    application.add_handler(
        MessageHandler(filters.COMMAND, dynamic_symbol_command),
        group=1,
    )

    application.add_error_handler(error_handler)

    await application.initialize()
    await application.bot.delete_webhook(drop_pending_updates=True)
    await _refresh_menu_commands(application)

    if application.job_queue is not None:
        application.job_queue.run_repeating(
            run_alert_checks,
            interval=60,
            first=15,
            name="price-alert-checker",
        )
        logger.info("Price alert checker scheduled.")
    else:
        logger.warning("JobQueue is unavailable. Price alerts will be saved but not auto-checked.")

    logger.info(
        "Starting bot for target_chat_id=%s source_thread_id=%s",
        settings.target_chat_id,
        settings.source_thread_id,
    )

    await application.start()
    await application.updater.start_polling(drop_pending_updates=True)

    try:
        while True:
            await asyncio.sleep(3600)
    finally:
        await application.updater.stop()
        await application.stop()
        await application.shutdown()


def main() -> None:
    asyncio.run(run_bot())


if __name__ == "__main__":
    main()