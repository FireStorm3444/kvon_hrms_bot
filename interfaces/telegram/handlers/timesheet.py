import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from core.database import DatabaseManager
from interfaces.telegram.states import TimesheetState

logger = logging.getLogger(__name__)
router = Router()
db = DatabaseManager()

@router.message(Command("timesheet"))
async def start_timesheet(message: Message, state: FSMContext):
    await message.answer("📝 Let's prep your timesheet. What is the **Task Name**?", parse_mode="Markdown")
    await state.set_state(TimesheetState.waiting_for_task_name)

@router.callback_query(F.data == "fill_ts")
async def callback_fill_ts(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("📝 Let's prep your timesheet. What is the **Task Name**?", parse_mode="Markdown")
    await state.set_state(TimesheetState.waiting_for_task_name)
    await callback.answer()

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
    success = db.save_pending_timesheet(data['task_name'], data['task_details'], message.text, "09:00", "18:00")
    
    if success:
        await message.answer(
            f"✅ **Timesheet Staged**\n**Task:** {data['task_name']}\n**Mentor:** {message.text}\n"
            f"Send `/check_out` when you are ready to end your day.", parse_mode="Markdown"
        )
    else:
        await message.answer("❌ Failed to save timesheet to the database.")
    await state.clear()