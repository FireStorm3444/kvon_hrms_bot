import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand

from config import get_config
from core.logging_config import setup_logging
from interfaces.telegram.handlers import attendance, timesheet, skip

import pytz
from core.database import DatabaseManager
from datetime import datetime
from interfaces.telegram.helpers import execute_main_script

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

async def checkout_scheduler_worker():
    """Background task that checks the database against the IST clock every 30 seconds."""
    db = DatabaseManager()
    ist_tz = pytz.timezone('Asia/Kolkata')
    
    logger.info("⚙️ Background Checkout Scheduler Started.")
    
    while True:
        try:
            target_time = db.get_scheduled_checkout()
            
            if target_time:
                # Get current IST time in HH:MM format
                current_time = datetime.now(ist_tz).strftime("%H:%M")
                
                # If the current time is greater than or equal to the scheduled time
                if current_time >= target_time:
                    logger.info("⏰ Scheduled checkout time reached (%s). Executing payload...", target_time)
                    
                    # 1. Wipe the schedule FIRST to prevent duplicate executions
                    db.clear_scheduled_checkout()
                    
                    # 2. Fire the check-out pipeline
                    asyncio.create_task(execute_main_script("check-out"))
        
        except Exception as e:
            logger.error(f"Scheduler worker encountered an error: {e}")
            
        # Sleep for 30 seconds before checking again
        await asyncio.sleep(30)

# --- BOT ENTRY POINT ---
async def main():
    config = get_config()
    bot = Bot(token=config.telegram_bot_token)
    dp = Dispatcher()

    dp.include_router(attendance.router)
    dp.include_router(timesheet.router)
    dp.include_router(skip.router)

    await setup_bot_commands(bot)
    
    # START THE BACKGROUND WORKER
    asyncio.create_task(checkout_scheduler_worker())

    logger.info("🤖 Telegram Listener Daemon Started...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())