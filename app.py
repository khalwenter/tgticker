from __future__ import annotations

import asyncio

from config import settings, validate_settings


async def error_handler(update: object, context) -> None:
    from logger import logger
    logger.exception("Telegram error occurred", exc_info=context.error)


async def run_bot() -> None:
    validate_settings()

    from telegram.ext import Application, CommandHandler, MessageHandler, filters
    from handlers.admin import (
        build_admin_conversation,
        build_remove_command_conversation,
        build_ticker_callback_handler,
        list_tickers,
        remove_tickers_menu,
    )
    from handlers.commands import start, commands_ls, dynamic_price_command
    from logger import logger

    application = Application.builder().token(settings.bot_token).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("commands", commands_ls))
    application.add_handler(build_admin_conversation())
    application.add_handler(build_remove_command_conversation())
    application.add_handler(CommandHandler("listtickers", list_tickers))
    application.add_handler(CommandHandler("removetickers", remove_tickers_menu))
    application.add_handler(build_ticker_callback_handler())

    application.add_handler(
        MessageHandler(filters.COMMAND, dynamic_price_command),
        group=1,
    )

    application.add_error_handler(error_handler)

    await application.initialize()
    await application.bot.delete_webhook(drop_pending_updates=True)

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