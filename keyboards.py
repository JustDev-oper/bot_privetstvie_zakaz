from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


# ---------------------------------------------------------------------- #
#  Главное админ-меню
# ---------------------------------------------------------------------- #
def admin_main_menu() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="📡 Каналы сети", callback_data="adm:channels")
    kb.button(text="➕ Добавить канал вручную", callback_data="adm:add_channel")
    kb.button(text="✉️ Приветственные цепочки", callback_data="adm:chains")
    kb.button(text="🔒 Замок-доступ (быстрый вход)", callback_data="adm:chains")
    kb.button(text="ℹ️ Помощь", callback_data="adm:help")
    kb.adjust(1)
    return kb.as_markup()


def back_to_menu() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ В меню", callback_data="adm:menu")
    return kb.as_markup()


# ---------------------------------------------------------------------- #
#  Управление каналами
# ---------------------------------------------------------------------- #
def channels_list_menu(channels) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Добавить канал вручную", callback_data="adm:add_channel")
    for ch in channels:
        icon = "🔗" if ch["invite_link"] else "⚠️"
        kb.button(text=f"{icon} {ch['title']}", callback_data=f"adm:channel:{ch['chat_id']}")
    kb.button(text="⬅️ В меню", callback_data="adm:menu")
    kb.adjust(1)
    return kb.as_markup()


def channel_card_menu(chat_id: int, has_link: bool, has_chain: bool = False) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if has_link:
        kb.button(text="🔄 Перевыпустить реф-ссылку", callback_data=f"adm:genlink:{chat_id}")
    else:
        kb.button(text="🔗 Создать реф-ссылку", callback_data=f"adm:genlink:{chat_id}")
    kb.button(text="✉️ Настроить приветствие", callback_data=f"adm:chain_edit:{chat_id}")
    if has_chain:
        kb.button(text="👀 Посмотреть пост", callback_data=f"adm:chain_preview:{chat_id}")
    kb.button(text="🗑 Отключить канал", callback_data=f"adm:delchannel:{chat_id}")
    kb.button(text="⬅️ К списку каналов", callback_data="adm:channels")
    kb.adjust(1)
    return kb.as_markup()


def delchannel_confirm_menu(chat_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Да, отключить", callback_data=f"adm:delchannel_yes:{chat_id}")
    kb.button(text="❌ Отмена", callback_data=f"adm:channel:{chat_id}")
    kb.adjust(1)
    return kb.as_markup()


# ---------------------------------------------------------------------- #
#  Ручное подключение канала
# ---------------------------------------------------------------------- #
def add_channel_menu() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="📨 Переслать пост из канала", callback_data="adm:add_by_forward")
    kb.button(text="🆔 Ввести ID канала", callback_data="adm:add_by_id")
    kb.button(text="⬅️ В меню", callback_data="adm:menu")
    kb.adjust(1)
    return kb.as_markup()


# ---------------------------------------------------------------------- #
#  Конструктор цепочки приветствий
# ---------------------------------------------------------------------- #
def chain_builder_menu(has_steps: bool, chat_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Добавить сообщение в цепочку", callback_data="chain:add_step")
    if has_steps:
        kb.button(text="👀 Посмотреть пост", callback_data=f"adm:chain_preview:{chat_id}")
        kb.button(text="🗑 Удалить пост из цепочки", callback_data=f"chain:manage_steps:{chat_id}")
        kb.button(text="🔒 Настроить обязательную подписку", callback_data="chain:lock_setup")
        kb.button(text="✅ Сохранить и включить", callback_data="chain:save")
    kb.button(text="🚫 Отмена", callback_data="adm:channels")
    kb.adjust(1)
    return kb.as_markup()


def chain_steps_list_menu(steps, chat_id: int) -> InlineKeyboardMarkup:
    """Показывает список шагов цепочки с кнопками удаления."""
    kb = InlineKeyboardBuilder()
    content_icons = {
        "text": "📝",
        "photo": "🖼",
        "video": "🎥",
        "video_note": "⭕",
        "voice": "🎙",
        "document": "📎",
        "animation": "🎞",
    }
    for step in steps:
        icon = content_icons.get(step["content_type"], "📨")
        delay_str = ""
        if step["delay_seconds"] > 0:
            m, s = divmod(step["delay_seconds"], 60)
            h, m = divmod(m, 60)
            if h:
                delay_str = f" (+{h}ч{m}м)"
            elif m:
                delay_str = f" (+{m}м)"
            else:
                delay_str = f" (+{s}с)"
        label = (step["text"] or "")[:30].replace("\n", " ")
        label_str = f" «{label}»" if label else ""
        kb.button(
            text=f"🗑 #{step['step_order'] + 1} {icon}{label_str}{delay_str}",
            callback_data=f"chain:delete_step:{step['id']}:{chat_id}",
        )
    kb.button(text="⬅️ Назад к цепочке", callback_data=f"adm:chain_edit:{chat_id}")
    kb.adjust(1)
    return kb.as_markup()


def ask_delay_menu() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="⚡ Без задержки", callback_data="delay:0")
    kb.button(text="⏱ 1 минута", callback_data="delay:60")
    kb.button(text="⏱ 5 минут", callback_data="delay:300")
    kb.button(text="⏱ 30 минут", callback_data="delay:1800")
    kb.button(text="⏱ 1 час", callback_data="delay:3600")
    kb.adjust(2)
    return kb.as_markup()


def delete_step_confirm_menu(step_id: int, chat_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Да, удалить", callback_data=f"chain:delete_step_yes:{step_id}:{chat_id}")
    kb.button(text="❌ Отмена", callback_data=f"chain:manage_steps:{chat_id}")
    kb.adjust(1)
    return kb.as_markup()


def lock_toggle_menu(channels, selected: set[int]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for ch in channels:
        mark = "☑️" if ch["chat_id"] in selected else "⬜️"
        kb.button(text=f"{mark} {ch['title']}", callback_data=f"lock:toggle:{ch['chat_id']}")
    kb.button(text="➡️ Далее: канал-награда", callback_data="lock:next_reward")
    kb.adjust(1)
    return kb.as_markup()


def lock_reward_menu(channels) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for ch in channels:
        kb.button(text=f"🏆 {ch['title']}", callback_data=f"lock:reward:{ch['chat_id']}")
    kb.button(text="🚫 Без замка (просто цепочка)", callback_data="lock:disable")
    kb.adjust(1)
    return kb.as_markup()


# ---------------------------------------------------------------------- #
#  Пользовательская клавиатура под приветственным постом
# ---------------------------------------------------------------------- #
def user_lock_keyboard(required_channels, invite_links: dict[int, str]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for ch in required_channels:
        link = invite_links.get(ch["chat_id"])
        if link:
            kb.button(text=f"📢 {ch['title']}", url=link)
    kb.button(text="✅ Проверить подписку / Получить доступ", callback_data="user:check")
    kb.adjust(1)
    return kb.as_markup()


def user_get_link_button(url: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🎁 Забрать доступ", url=url)
    return kb.as_markup()
