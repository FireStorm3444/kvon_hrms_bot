import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand

from config import get_config
from core.logging_config import setup_logging
from interfaces.telegram.handlers import attendance, timesheet, skip

setup_logging()
logger = logging.getLogger(__name__)

async def setup_bot_commands(bot: Bot):
    commands = [
        BotCommand(command="status", description="Live telemetry from servers"),
        BotCommand(command="check_in", description="Force an immediate check-in"),
        BotCommand(command="check_out", description="Trigger the check-out sequence"),
        BotCommand(command="timesheet", description="Pre-fill your timesheet for today"),
        BotCommand(command="skip_check_in", description="Skip automated check-in")
    ]
    await bot.set_my_commands(commands)
    logger.info("Telegram bot command menu configured.")

async def main():
    config = get_config()
    bot = Bot(token=config.telegram_bot_token)
    dp = Dispatcher()

    # Register all isolated feature domains
    dp.include_router(attendance.router)
    dp.include_router(timesheet.router)
    dp.include_router(skip.router)

    await setup_bot_commands(bot)
    logger.info("🤖 Telegram Listener Daemon Started...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())