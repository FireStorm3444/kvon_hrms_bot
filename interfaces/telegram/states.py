from aiogram.fsm.state import State, StatesGroup

class TimesheetState(StatesGroup):
    waiting_for_start = State()
    waiting_for_end = State()
    waiting_for_task_name = State()
    waiting_for_task_details = State()
    waiting_for_mentor = State()

class SkipState(StatesGroup):
    waiting_for_date = State()

class CheckoutState(StatesGroup):
    waiting_for_time = State()