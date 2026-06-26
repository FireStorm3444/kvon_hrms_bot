import re
import logging
import asyncio
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from config import get_config
from core.database import DatabaseManager
from core.api_client import APIClient
from services.hrms_service import HRMSService
from interfaces.telegram.states import TimesheetState

logger = logging.getLogger(__name__)
router = Router()
db = DatabaseManager()
config = get_config()

# Strict 24-hour time format validator (HH:MM)
TIME_REGEX = re.compile(r"^(0[0-9]|1[0-9]|2[0-3]):[0-5][0-9]$")

def get_timesheet_menu() -> InlineKeyboardMarkup:
    """Generates the interactive dashboard for the timesheet module."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⚡ Standard (9 to 6)", callback_data="ts_standard"),
            InlineKeyboardButton(text="⚙️ Manual Shift", callback_data="ts_manual")
        ],
        [
            InlineKeyboardButton(text="📊 Status", callback_data="ts_status"),
            InlineKeyboardButton(text="🗑️ Reset", callback_data="ts_reset")
        ],
        [
            InlineKeyboardButton(text="📤 Send to KvonTech", callback_data="ts_send")
        ]
    ])

# --- COMMAND ENTRY ---

@router.message(Command("timesheet"))
async def start_timesheet(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "📋 **Timesheet Command Center**\n\nSelect an operation to park or manage your daily tasks:",
        reply_markup=get_timesheet_menu(),
        parse_mode="Markdown"
    )

# --- MENU ROUTERS (CALLBACKS) ---

@router.callback_query(F.data == "ts_standard")
async def callback_ts_standard(callback: CallbackQuery, state: FSMContext):
    # Pre-fill times and skip directly to task name
    await state.update_data(start_time="09:00", end_time="18:00")
    await callback.message.edit_text("⚡ **Standard Shift**\nWhat is the **Task Name**?", parse_mode="Markdown")
    await state.set_state(TimesheetState.waiting_for_task_name)
    await callback.answer()

@router.callback_query(F.data == "ts_manual")
async def callback_ts_manual(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("⚙️ **Manual Shift**\nEnter Start Time (`HH:MM` in 24-hour format, e.g., `09:30`):", parse_mode="Markdown")
    await state.set_state(TimesheetState.waiting_for_start)
    await callback.answer()

@router.callback_query(F.data == "ts_status")
async def callback_ts_status(callback: CallbackQuery):
    rows = db.get_pending_timesheets()
    if not rows:
        msg = "⚠️ **No timesheets currently parked in memory.**"
    else:
        msg = "📊 **Parked Timesheets (Pending Upload):**\n\n"
        for row in rows:
            msg += f"🔸 `{row['start_time']} - {row['end_time']}`: {row['task_name']}\n"
    
    await callback.message.edit_text(msg, parse_mode="Markdown", reply_markup=get_timesheet_menu())
    await callback.answer()

@router.callback_query(F.data == "ts_reset")
async def callback_ts_reset(callback: CallbackQuery):
    if db.clear_pending_timesheets():
        await callback.message.edit_text("🗑️ All parked timesheets for today have been cleared.", reply_markup=get_timesheet_menu())
    else:
        await callback.message.edit_text("❌ Database error during reset.", reply_markup=get_timesheet_menu())
    await callback.answer()

@router.callback_query(F.data == "ts_send")
async def callback_ts_send(callback: CallbackQuery):
    rows = db.get_pending_timesheets()
    if not rows:
        await callback.answer("⚠️ No parked timesheets to send!", show_alert=True)
        return

    await callback.message.edit_text("📤 Pushing batched payload to KvonTech...", parse_mode="Markdown")

    def push_sync():
        api_client = APIClient(config.api_url)
        hrms = HRMSService(config, api_client)
        success, _ = hrms.login(silent=True)
        if success:
            return hrms.submit_timesheet(rows)
        return False

    # Dispatch to background thread to prevent blocking
    success = await asyncio.to_thread(push_sync)
    
    if success:
        db.clear_pending_timesheets()
        await callback.message.edit_text("✅ **Success:** All timesheets successfully submitted to KvonTech.", parse_mode="Markdown")
    else:
        await callback.message.edit_text("❌ **Network Error:** Failed to submit payload to KvonTech. Your timesheets are still safely parked in memory.", parse_mode="Markdown")
    await callback.answer()

# --- FINITE STATE MACHINE (FSM) LOGIC ---

@router.message(TimesheetState.waiting_for_start)
async def process_start_time(message: Message, state: FSMContext):
    if not TIME_REGEX.match(message.text.strip()):
        await message.answer("❌ Invalid format. Please use HH:MM (e.g., `09:30`).", parse_mode="Markdown")
        return
    await state.update_data(start_time=message.text.strip())
    await message.answer("Got it. Enter End Time (`HH:MM`):", parse_mode="Markdown")
    await state.set_state(TimesheetState.waiting_for_end)

@router.message(TimesheetState.waiting_for_end)
async def process_end_time(message: Message, state: FSMContext):
    if not TIME_REGEX.match(message.text.strip()):
        await message.answer("❌ Invalid format. Please use HH:MM (e.g., `18:00`).", parse_mode="Markdown")
        return
    await state.update_data(end_time=message.text.strip())
    await message.answer("Great. What is the **Task Name**?", parse_mode="Markdown")
    await state.set_state(TimesheetState.waiting_for_task_name)

@router.message(TimesheetState.waiting_for_task_name)
async def process_task_name(message: Message, state: FSMContext):
    await state.update_data(task_name=message.text)
    await message.answer("Got it. What are the **Task Details**?", parse_mode="Markdown")
    await state.set_state(TimesheetState.waiting_for_task_details)

@router.message(TimesheetState.waiting_for_task_details)
async def process_task_details(message: Message, state: FSMContext):
    await state.update_data(task_details=message.text)
    await message.answer("Finally, who is your **Mentor**?", parse_mode="Markdown")
    await state.set_state(TimesheetState.waiting_for_mentor)

@router.message(TimesheetState.waiting_for_mentor)
async def process_mentor_name(message: Message, state: FSMContext):
    data = await state.get_data()
    
    # Attempt to write to the SQLite ledger
    success, return_msg = db.save_pending_timesheet(
        task=data['task_name'], 
        details=data['task_details'], 
        mentor=message.text, 
        start=data['start_time'], 
        end=data['end_time']
    )
    
    if success:
        await message.answer(
            f"✅ **Timesheet Parked Successfully**\n"
            f"🔸 **Time:** `{data['start_time']} - {data['end_time']}`\n"
            f"🔸 **Task:** {data['task_name']}\n\n"
            f"Use `/timesheet` to view status or push to the server.", 
            parse_mode="Markdown"
        )
    else:
        # Gracefully handle the Time Overlap rejection from Phase 1
        await message.answer(f"❌ **Action Rejected:** {return_msg}", parse_mode="Markdown")
        
    await state.clear()