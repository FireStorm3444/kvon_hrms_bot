import sys
import asyncio
import logging
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, BotCommand
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import get_config
from core.database import DatabaseManager
from core.logging_config import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

router = Router()
db = DatabaseManager()
config = get_config()
bot = Bot(token=config.telegram_bot_token)

# --- FINITE STATE MACHINE (FSM) DEFINITION ---
class TimesheetState(StatesGroup):
    waiting_for_task_name = State()
    waiting_for_task_details = State()
    waiting_for_mentor = State()

class SkipState(StatesGroup):
    waiting_for_date = State()

@router.message(Command("check_in"))
async def handle_checkin(message: Message):
    logger.info("Received /check_in command from chat_id=%s.", message.chat.id)
    await message.answer("🔄 Initiating manual check-in sequence...")
    # Fire off main.py asynchronously using the existing helper function
    asyncio.create_task(execute_main_script("check-in"))

# --- THE SKIP COMMAND ---
@router.message(Command("skip_check_in"))
async def handle_skip_init(message: Message, state: FSMContext):
    logger.info("Received /skip_check_in command from chat_id=%s.", message.chat.id)
    args = message.text.split(maxsplit=1)
    
    # If tapped from the menu (no date provided), ask for it interactively
    if len(args) < 2:
        await message.answer(
            "📅 **Skip Check-In**\n\nWhich date would you like to skip? \n"
            "*(Reply with `tomorrow` or a specific date like `2026-06-25`)*", 
            parse_mode="Markdown"
        )
        await state.set_state(SkipState.waiting_for_date)
        return
        
    # If typed manually with a date (the fast path), process it immediately
    await process_skip_date(message.answer, args[1], state)

@router.message(SkipState.waiting_for_date)
async def handle_skip_interactive(message: Message, state: FSMContext):
    logger.info("Received interactive skip date from chat_id=%s.", message.chat.id)
    # Pass the user's interactive reply into the processor
    await process_skip_date(message.answer, message.text, state)

async def process_skip_date(send_function, target_input: str, state: FSMContext):
    """Core logic to calculate and save the skip date, used by both entry points."""
    target = target_input.lower().strip()
    
    if target == "tomorrow":
        target_date = (datetime.today() + timedelta(days=1)).strftime("%Y-%m-%d")
    elif target == "reset":
        target_date = None
    else:
        # Assuming the user typed a raw date string
        target_date = target
        
    if not target_date:
        if db.clear_skip_dates():
            logger.info("Skip date reset successfully.")
            await send_function("✅ Skip date reset. Automated check-ins will resume as normal.")
        else:
            logger.error("Skip date reset failed.")
            await send_function("❌ Database error occurred while trying to reset skip dates.")
    elif db.add_skip_date(target_date):
        logger.info("Skip date processed successfully: %s.", target_date)
        await send_function(f"✅ Noted. I have updated the database to skip the automated check-in on `{target_date}`.", parse_mode="Markdown")
    else:
        logger.error("Skip date processing failed for target_date=%s.", target_date)
        await send_function("❌ Database error occurred while trying to save the skip date.")
        
    # Always clear the FSM state so the bot isn't stuck waiting forever
    await state.clear()

# --- TIMESHEET QUESTIONNAIRE (FSM) ---
@router.message(Command("timesheet"))
async def start_timesheet(message: Message, state: FSMContext):
    logger.info("Received /timesheet command from chat_id=%s.", message.chat.id)
    await message.answer("📝 Let's prep your timesheet. What is the **Task Name**?", parse_mode="Markdown")
    await state.set_state(TimesheetState.waiting_for_task_name)

@router.message(TimesheetState.waiting_for_task_name)
async def process_task_name(message: Message, state: FSMContext):
    logger.debug("Received timesheet task name from chat_id=%s.", message.chat.id)
    await state.update_data(task_name=message.text)
    await message.answer("Got it. What are the **Task Details**?")
    await state.set_state(TimesheetState.waiting_for_task_details)

@router.message(TimesheetState.waiting_for_task_details)
async def process_task_details(message: Message, state: FSMContext):
    logger.debug("Received timesheet task details from chat_id=%s.", message.chat.id)
    await state.update_data(task_details=message.text)
    await message.answer("Great. Finally, who is your **Mentor**?")
    await state.set_state(TimesheetState.waiting_for_mentor)

@router.message(TimesheetState.waiting_for_mentor)
async def process_mentor_name(message: Message, state: FSMContext):
    logger.debug("Received timesheet mentor name from chat_id=%s.", message.chat.id)
    data = await state.get_data()
    task_name = data['task_name']
    task_details = data['task_details']
    mentor = message.text
    
    # Save to SQLite with default 09:00 to 18:00 times
    success = db.save_pending_timesheet(task_name, task_details, mentor, "09:00", "18:00")
    
    if success:
        logger.info("Pending timesheet staged from chat_id=%s.", message.chat.id)
        await message.answer(
            f"✅ **Timesheet Staged & Saved**\n\n"
            f"**Task:** {task_name}\n**Details:** {task_details}\n**Mentor:** {mentor}\n\n"
            f"This data is safely stored in the database. Send `/check_out` when you are ready to end your day.",
            parse_mode="Markdown"
        )
    else:
        logger.error("Failed to stage pending timesheet from chat_id=%s.", message.chat.id)
        await message.answer("❌ Failed to save timesheet to the database.")
    
    await state.clear()

# --- DYNAMIC CHECK-OUT & INTERACTIVE FALLBACK ---
@router.message(Command("check_out"))
async def handle_checkout(message: Message):
    logger.info("Received /check_out command from chat_id=%s.", message.chat.id)
    pending_ts = db.get_pending_timesheet()
    
    if pending_ts:
        await message.answer("🔄 Timesheet found in memory. Initiating check-out sequence...")
        # Fire off main.py asynchronously so it doesn't block the bot
        asyncio.create_task(execute_main_script("check-out"))
    else:
        # Fallback: No timesheet found in DB
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📝 Fill Timesheet Now", callback_data="fill_ts")],
            [InlineKeyboardButton(text="⚠️ Force Raw Check-Out", callback_data="force_checkout")]
        ])
        await message.answer(
            "⚠️ **Timesheet Required**\n\nYou haven't staged a timesheet yet. The KvonTech API will likely reject your check-out.", 
            reply_markup=keyboard,
            parse_mode="Markdown"
        )

# --- BUTTON CALLBACK HANDLERS ---
@router.callback_query(F.data == "fill_ts")
async def callback_fill_ts(callback: CallbackQuery, state: FSMContext):
    logger.info("Received fill_ts callback from chat_id=%s.", callback.message.chat.id)
    await callback.message.edit_text("📝 Let's prep your timesheet. What is the **Task Name**?", parse_mode="Markdown")
    await state.set_state(TimesheetState.waiting_for_task_name)
    await callback.answer()

@router.callback_query(F.data == "force_checkout")
async def callback_force_checkout(callback: CallbackQuery):
    logger.info("Received force_checkout callback from chat_id=%s.", callback.message.chat.id)
    await callback.message.edit_text("⚠️ Forcing raw check-out pipeline...")
    asyncio.create_task(execute_main_script("check-out"))
    await callback.answer()

# --- HELPER: ASYNC SUBPROCESS EXECUTION ---
async def execute_main_script(action: str):
    """Runs main.py as a separate OS process and captures all logs."""
    logger.info("🚀 Launching subprocess for: %s", action)
    
    # sys.executable perfectly resolves to your active virtual environment
    process = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "interfaces.cli.main", "--action", action,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    # Await the finish and capture the outputs
    stdout, stderr = await process.communicate()
    
    # Decode and print the logs directly to the daemon's terminal
    out_str = stdout.decode().strip()
    err_str = stderr.decode().strip()
    
    if out_str:
        logger.info("[MAIN.PY OUTPUT]\n%s", out_str)
    
    if process.returncode != 0:
        logger.error("[MAIN.PY ERROR/CRASH returncode=%s]\n%s", process.returncode, err_str)
    elif err_str:
        logger.info("[MAIN.PY STDERR]\n%s", err_str)
    else:
        logger.info("Subprocess for %s completed with returncode=%s.", action, process.returncode)

async def setup_bot_commands(bot: Bot):
    """Pushes the command menu to Telegram"""
    commands = [
        BotCommand(command="check_in", description="Force an immediate check-in"),
        BotCommand(command="check_out", description="Trigger the check-out sequence"),
        BotCommand(command="timesheet", description="Pre-fill your timesheet for today"),
        BotCommand(command="skip_check_in", description="Skip automated check-in (e.g. tomorrow)")
    ]
    await bot.set_my_commands(commands)
    logger.info("Telegram bot command menu configured.")

# --- BOT ENTRY POINT ---
async def main():
    dp = Dispatcher()
    dp.include_router(router)

    await setup_bot_commands(bot)

    logger.info("🤖 Telegram Listener Daemon Started...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
