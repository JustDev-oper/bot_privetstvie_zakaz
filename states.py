from aiogram.fsm.state import State, StatesGroup


class ChainBuilder(StatesGroup):
    """Диалог создания/редактирования приветственной цепочки для канала."""
    waiting_step_content = State()   # ждём текст/медиа очередного сообщения цепочки
    waiting_step_delay = State()     # ждём выбор задержки перед этим сообщением
    lock_select_required = State()   # выбор каналов-условий для замка
    lock_select_reward = State()     # выбор канала-награды
