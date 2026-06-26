import re
import logging
import asyncio
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command

from config import get_config
from core.database import DatabaseManager
from core.api_client import APIClient
from services.hrms_service import HRMSService
from interfaces.telegram.helpers import execute_main_script
from aiogram.fsm.context import FSMContext
from interfaces.telegram.states import CheckoutState

logger = logging.getLogger(__name__)
router = Router()
db = DatabaseManager()
config = get_config()

@router.message(Command("check_in"))
async def handle_checkin(message: Message):
    logger.info("Received /check_in command.")
    await message.answer("🔄 Initiating manual check-in sequence...")
    asyncio.create_task(execute_main_script("check-in"))

# 12-hour time regex (Catches "06:30 PM", "6:15pm", "12:00 AM")
TIME_12H_REGEX = re.compile(r"^(1[0-2]|0?[1-9]):([0-5][0-9]) ?([AaPp][Mm])$")

@router.message(Command("check_out"))
async def handle_checkout(message: Message):
    logger.info("Received /check_out command.")
    
    # Check if a schedule already exists
    scheduled = db.get_scheduled_checkout()
    if scheduled:
        await message.answer(
            f"⏳ **Checkout is already scheduled for `{scheduled}` (24h).**\n"
            "Would you like to force an instant checkout right now instead?",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⚡ Force Instant Checkout", callback_data="co_instant")],
                [InlineKeyboardButton(text="❌ Cancel Schedule", callback_data="co_cancel_sched")]
            ]), parse_mode="Markdown"
        )
        return

    if db.get_pending_timesheets():
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="⚡ Instant", callback_data="co_instant"),
                InlineKeyboardButton(text="⏰ Automated", callback_data="co_automated")
            ]
        ])
        await message.answer(
            "✅ **Timesheets found in memory.**\n\nHow would you like to execute the check-out?", 
            reply_markup=keyboard, parse_mode="Markdown"
        )
    else:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📝 Fill Timesheet Now", callback_data="fill_ts")],
            [InlineKeyboardButton(text="⚠️ Force Raw Check-Out", callback_data="force_checkout")]
        ])
        await message.answer(
            "⚠️ **Timesheet Required**\n\nYou haven't staged any timesheets yet.", 
            reply_markup=keyboard, parse_mode="Markdown"
        )

# --- CHECKOUT CALLBACKS ---

@router.callback_query(F.data == "co_instant")
async def callback_co_instant(callback: CallbackQuery):
    db.clear_scheduled_checkout() # Clear any existing schedule just in case
    await callback.message.edit_text("🔄 Initiating instant check-out sequence...")
    asyncio.create_task(execute_main_script("check-out"))
    await callback.answer()

@router.callback_query(F.data == "co_automated")
async def callback_co_automated(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "⏰ **Automated Checkout**\n\n"
        "Enter your desired checkout time in 12-hour format.\n"
        "*(Example: `06:30 PM` or `6:15pm`)*", 
        parse_mode="Markdown"
    )
    await state.set_state(CheckoutState.waiting_for_time)
    await callback.answer()

@router.callback_query(F.data == "co_cancel_sched")
async def callback_co_cancel_sched(callback: CallbackQuery):
    db.clear_scheduled_checkout()
    await callback.message.edit_text("🚫 **Schedule Cancelled.** Your timesheets remain safely parked.")
    await callback.answer()

# --- CHECKOUT FSM LOGIC ---

@router.message(CheckoutState.waiting_for_time)
async def process_scheduled_time(message: Message, state: FSMContext):
    match = TIME_12H_REGEX.match(message.text.strip())
    
    if not match:
        await message.answer("❌ Invalid format. Please use 12-hour time like `06:30 PM`.", parse_mode="Markdown")
        return
        
    # Parse 12-hour to 24-hour for mathematical comparison
    hours = int(match.group(1))
    minutes = match.group(2)
    meridiem = match.group(3).upper()
    
    if meridiem == "PM" and hours != 12:
        hours += 12
    elif meridiem == "AM" and hours == 12:
        hours = 0
        
    time_24h = f"{hours:02d}:{minutes}"
    
    if db.set_scheduled_checkout(time_24h):
        await message.answer(
            f"✅ **Checkout Scheduled**\n\n"
            f"The system will automatically push your payload and check you out at `{time_24h}` (IST).\n"
            f"You can close Telegram safely.", parse_mode="Markdown"
        )
    else:
        await message.answer("❌ Database error occurred while saving the schedule.")
        
    await state.clear()

@router.callback_query(F.data == "fill_ts")
async def callback_fill_ts(callback: CallbackQuery):
    await callback.message.edit_text(
        "📝 **Timesheet Pre-Fill**\n\n"
        "Please use the `/timesheet` command to pre-fill your timesheet for today before checking out.", 
        parse_mode="Markdown"
    )
    await callback.answer()

@router.callback_query(F.data == "force_checkout")
async def callback_force_checkout(callback: CallbackQuery):
    await callback.message.edit_text("⚠️ Forcing raw check-out pipeline...")
    asyncio.create_task(execute_main_script("check-out"))
    await callback.answer()

@router.message(Command("status"))
async def handle_status(message: Message):
    logger.info("Received /status command.")
    status_msg = await message.answer("🔄 Connecting to KvonTech servers...", parse_mode="Markdown")

    def fetch_status_sync():
        api_client = APIClient(config.api_url)
        hrms = HRMSService(config, api_client)
        success, _ = hrms.login(silent=True)
        return hrms.get_status() if success else None

    data = await asyncio.to_thread(fetch_status_sync)

    if not data:
        await status_msg.edit_text("❌ Failed to pull telemetry from the server.")
        return

    record = data.get("record") or {}
    response_text = (
        f"📊 **KvonTech Status Console**\n"
        f"📅 **Date:** `{record.get('date', 'N/A')}`\n"
        f"🛡️ **Status:** `{data.get('status', 'Unknown')}` (Verified: {record.get('verified', 'No')})\n\n"
        f"🟢 **Check-In:** `{record.get('checkIn', 'N/A')}`\n"
        f"🔴 **Check-Out:** `{record.get('checkOut', 'N/A')}`\n"
        f"⏱️ **Total Hours:** `{record.get('hours', '0 hrs')}`\n\n"
        f"⚙️ **Local Infrastructure State:**\n"
    )

    pending_timesheets = db.get_pending_timesheets()
    if pending_timesheets:
        response_text += f"📝 `{len(pending_timesheets)}` timesheet(s) currently parked in memory."
    else:
        response_text += "⚠️ No timesheets currently parked in memory."
        
    await status_msg.edit_text(response_text, parse_mode="Markdown")