import asyncio
import logging
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import get_config
from core.database import DatabaseManager
from services.hrms_service import AttendanceAction

# We will use subprocess to run main.py asynchronously without thread-locking the bot
import subprocess

logging.basicConfig(level=logging.INFO)

router = Router()
db = DatabaseManager()
config = get_config()
bot = Bot(token=config.telegram_bot_token)

# --- FINITE STATE MACHINE (FSM) DEFINITION ---
class TimesheetState(StatesGroup):
    waiting_for_task_name = State()
    waiting_for_task_details = State()
    waiting_for_mentor = State()

# --- 1. THE SKIP COMMAND ---
@router.message(Command("skip_check_in"))
async def handle_skip(message: Message):
    args = message.text.split(maxsplit=1)
    
    if len(args) < 2:
        await message.answer("⚠️ Please provide a date. Example: `/skip_check_in tomorrow` or `/skip_check_in 2026-06-25`", parse_mode="Markdown")
        return
        
    target = args[1].lower().strip()
    
    if target == "tomorrow":
        target_date = (datetime.today() + timedelta(days=1)).strftime("%Y-%m-%d")
    else:
        # Basic validation (assume user inputs YYYY-MM-DD if not 'tomorrow')
        target_date = target
        
    if db.add_skip_date(target_date):
        await message.answer(f"✅ Noted. I have updated the database to skip the automated check-in on `{target_date}`.", parse_mode="Markdown")
    else:
        await message.answer("❌ Database error occurred while trying to save the skip date.")

# --- 2. TIMESHEET QUESTIONNAIRE (FSM) ---
@router.message(Command("timesheet"))
async def start_timesheet(message: Message, state: FSMContext):
    await message.answer("📝 Let's prep your timesheet. What is the **Task Name**?", parse_mode="Markdown")
    await state.set_state(TimesheetState.waiting_for_task_name)

@router.message(TimesheetState.waiting_for_task_name)
async def process_task_name(message: Message, state: FSMContext):
    await state.update_data(task_name=message.text)
    await message.answer("Got it. What are the **Task Details**?")
    await state.set_state(TimesheetState.waiting_for_task_details)

@router.message(TimesheetState.waiting_for_task_details)
async def process_task_details(message: Message, state: FSMContext):
    await state.update_data(task_details=message.text)
    await message.answer("Great. Finally, who is your **Mentor**?")
    await state.set_state(TimesheetState.waiting_for_mentor)

@router.message(TimesheetState.waiting_for_mentor)
async def process_mentor_name(message: Message, state: FSMContext):
    data = await state.get_data()
    task_name = data['task_name']
    task_details = data['task_details']
    mentor = message.text
    
    # Save to SQLite with default 09:00 to 18:00 times
    success = db.save_pending_timesheet(task_name, task_details, mentor, "09:00", "18:00")
    
    if success:
        await message.answer(
            f"✅ **Timesheet Staged & Saved**\n\n"
            f"**Task:** {task_name}\n**Details:** {task_details}\n**Mentor:** {mentor}\n\n"
            f"This data is safely stored in the database. Send `/check_out` when you are ready to end your day.",
            parse_mode="Markdown"
        )
    else:
        await message.answer("❌ Failed to save timesheet to the database.")
    
    await state.clear()

# --- 3. DYNAMIC CHECK-OUT & INTERACTIVE FALLBACK ---
@router.message(Command("check_out"))
async def handle_checkout(message: Message):
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

# --- 4. BUTTON CALLBACK HANDLERS ---
@router.callback_query(F.data == "fill_ts")
async def callback_fill_ts(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("📝 Let's prep your timesheet. What is the **Task Name**?", parse_mode="Markdown")
    await state.set_state(TimesheetState.waiting_for_task_name)
    await callback.answer()

@router.callback_query(F.data == "force_checkout")
async def callback_force_checkout(callback: CallbackQuery):
    await callback.message.edit_text("⚠️ Forcing raw check-out pipeline...")
    asyncio.create_task(execute_main_script("check-out"))
    await callback.answer()

# --- HELPER: ASYNC SUBPROCESS EXECUTION ---
async def execute_main_script(action: str):
    """Runs main.py as a separate OS process to utilize your existing architecture safely."""
    process = await asyncio.create_subprocess_exec(
        "/home/ubuntu/HRMS/.venv/bin/python", "main.py", "--action", action,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    await process.communicate()

# --- BOT ENTRY POINT ---
async def main():
    dp = Dispatcher()
    dp.include_router(router)
    logging.info("🤖 Telegram Listener Daemon Started...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())