import logging
from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from core.database import DatabaseManager
from interfaces.telegram.states import SkipState

logger = logging.getLogger(__name__)
router = Router()
db = DatabaseManager()

@router.message(Command("skip_check_in"))
async def handle_skip_init(message: Message, state: FSMContext):
    args = message.text.split(maxsplit=1)
    
    if len(args) < 2:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⏭️ Tomorrow", callback_data="skip_tomorrow"),
             InlineKeyboardButton(text="🔄 Reset Skip", callback_data="skip_reset")],
            [InlineKeyboardButton(text="📅 Custom Date", callback_data="skip_custom")]
        ])
        await message.answer("📅 **Skip Check-In**\n\nSelect an option below or type a specific date:", reply_markup=keyboard, parse_mode="Markdown")
        await state.set_state(SkipState.waiting_for_date)
        return
        
    await process_skip_date(message.answer, args[1], state)

@router.message(SkipState.waiting_for_date)
async def handle_skip_interactive(message: Message, state: FSMContext):
    await process_skip_date(message.answer, message.text, state)

@router.callback_query(F.data.in_(["skip_tomorrow", "skip_reset", "skip_custom"]))
async def callback_skip_options(callback: CallbackQuery, state: FSMContext):
    action = callback.data
    if action == "skip_tomorrow":
        await process_skip_date(callback.message.edit_text, "tomorrow", state)
    elif action == "skip_reset":
        await process_skip_date(callback.message.edit_text, "reset", state)
    elif action == "skip_custom":
        await callback.message.edit_text("📅 Please type the exact date you want to skip (`YYYY-MM-DD`):", parse_mode="Markdown")
        await state.set_state(SkipState.waiting_for_date)
    await callback.answer()

async def process_skip_date(send_function, target_input: str, state: FSMContext):
    target = target_input.lower().strip()
    target_date = (datetime.today() + timedelta(days=1)).strftime("%Y-%m-%d") if target == "tomorrow" else False if target == "reset" else target
    
    await send_function(f"⏳ Processing skip date: `{target_date}`...", parse_mode="Markdown")
        
    if not target_date:
        msg = "✅ Skip date reset. Automated check-ins will resume as normal." if db.clear_skip_dates() else "❌ Database error during reset."
    else:
        msg = f"✅ Noted. Check-in skipped on `{target_date}`." if db.add_skip_date(target_date) else "❌ Database error saving date."
        
    await send_function(msg, parse_mode="Markdown")
    await state.clear()