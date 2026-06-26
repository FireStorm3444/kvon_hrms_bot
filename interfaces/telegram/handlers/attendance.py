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

logger = logging.getLogger(__name__)
router = Router()
db = DatabaseManager()
config = get_config()

@router.message(Command("check_in"))
async def handle_checkin(message: Message):
    logger.info("Received /check_in command.")
    await message.answer("🔄 Initiating manual check-in sequence...")
    asyncio.create_task(execute_main_script("check-in"))

@router.message(Command("check_out"))
async def handle_checkout(message: Message):
    logger.info("Received /check_out command.")
    if db.get_pending_timesheets():
        await message.answer("🔄 Timesheets found in memory. Initiating check-out sequence...")
        asyncio.create_task(execute_main_script("check-out"))
    else:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📝 Fill Timesheet Now", callback_data="fill_ts")],
            [InlineKeyboardButton(text="⚠️ Force Raw Check-Out", callback_data="force_checkout")]
        ])
        await message.answer(
            "⚠️ **Timesheet Required**\n\nYou haven't staged any timesheets yet.", 
            reply_markup=keyboard, parse_mode="Markdown"
        )

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