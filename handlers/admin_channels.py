import logging
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery

from config import Config
from database import Database
import keyboards as kb
from handlers.admin_common import is_admin

logger = logging.getLogger(__name__)
router = Router(name="admin_channels")


@router.callback_query(F.data == "adm:channels")
async def list_channels(call: CallbackQuery, db: Database, config: Config):
    if not await is_admin(call.from_user.id, config, db):
        await call.answer("⛔️ Только для админов", show_alert=True)
        return
    channels = await db.list_channels()
    if not channels:
        await call.message.edit_text(
            "📡 Каналов пока нет.\n\n"
            "Добавьте бота в канал администратором с правами на управление "
            "заявками и создание инвайт-ссылок — канал появится здесь автоматически.",
            reply_markup=kb.back_to_menu(),
        )
        await call.answer()
        return
    await call.message.edit_text(
        f"📡 <b>Каналы сети</b> ({len(channels)})\n"
        f"🔗 — реф-ссылка создана · ⚠️ — ссылки ещё нет",
        parse_mode="HTML",
        reply_markup=kb.channels_list_menu(channels),
    )
    await call.answer()


@router.callback_query(F.data == "adm:chains")
async def list_chains(call: CallbackQuery, db: Database, config: Config):
    if not await is_admin(call.from_user.id, config, db):
        await call.answer("⛔️ Только для админов", show_alert=True)
        return
    chains = await db.list_chains_with_channel_titles()
    if not chains:
        await call.message.edit_text(
            "✉️ Приветственных цепочек пока нет.\nОткройте канал в разделе «📡 Каналы сети», "
            "чтобы настроить приветствие.",
            reply_markup=kb.back_to_menu(),
        )
        await call.answer()
        return

    lines = ["✉️ <b>Приветственные цепочки</b>\n"]
    for chain in chains:
        status = "✅ включена" if chain["is_active"] else "⏸ выключена"
        lock = "🔒 с замком" if chain["lock_enabled"] else "🔓 без замка"
        lines.append(f"📢 {chain['source_title']} — {status}, {lock}")
    await call.message.edit_text(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=kb.channels_list_menu(await db.list_channels()),
    )
    await call.answer()


@router.callback_query(F.data.startswith("adm:channel:"))
async def channel_card(call: CallbackQuery, db: Database):
    chat_id = int(call.data.split(":")[2])
    ch = await db.get_channel(chat_id)
    if not ch:
        await call.answer("Канал не найден", show_alert=True)
        return
    chain = await db.get_chain_by_source(chat_id)
    has_chain = bool(chain) and bool(await db.get_chain_steps(chain["id"]))
    link_line = f"🔗 <code>{ch['invite_link']}</code>" if ch["invite_link"] else "⚠️ Реф-ссылка ещё не создана"
    await call.message.edit_text(
        f"📢 <b>{ch['title']}</b>\nID: <code>{ch['chat_id']}</code>\n{link_line}",
        parse_mode="HTML",
        reply_markup=kb.channel_card_menu(chat_id, bool(ch["invite_link"]), has_chain),
    )
    await call.answer()


@router.callback_query(F.data.startswith("adm:genlink:"))
async def generate_link(call: CallbackQuery, db: Database, bot: Bot):
    chat_id = int(call.data.split(":")[2])
    ch = await db.get_channel(chat_id)
    if not ch:
        await call.answer("Канал не найден", show_alert=True)
        return
    try:
        link_obj = await bot.create_chat_invite_link(
            chat_id=chat_id,
            creates_join_request=True,  # ссылка всегда "с заявкой", как требует ТЗ
            name="referral-main",
        )
    except Exception:
        logger.exception("Не удалось создать реф-ссылку для %s", chat_id)
        await call.answer("⚠️ Не удалось создать ссылку — проверьте права бота", show_alert=True)
        return

    await db.set_channel_invite_link(chat_id, link_obj.invite_link)
    ch = await db.get_channel(chat_id)
    chain = await db.get_chain_by_source(chat_id)
    has_chain = bool(chain) and bool(await db.get_chain_steps(chain["id"]))
    await call.message.edit_text(
        f"✅ Реф-ссылка создана для «{ch['title']}»:\n🔗 <code>{ch['invite_link']}</code>",
        parse_mode="HTML",
        reply_markup=kb.channel_card_menu(chat_id, True, has_chain),
    )
    await call.answer("Готово!")


@router.callback_query(F.data.startswith("adm:delchannel:"))
async def ask_delete_channel(call: CallbackQuery, db: Database):
    chat_id = int(call.data.split(":")[2])
    ch = await db.get_channel(chat_id)
    if not ch:
        await call.answer("Канал не найден", show_alert=True)
        return
    await call.message.edit_text(
        f"⚠️ Отключить канал «{ch['title']}» от сети?\n\n"
        "Вместе с ним удалятся его реф-ссылка, приветственная цепочка, настройки "
        "замка (если он был условием или наградой в других цепочках — там замок "
        "просто выключится) и история заявок по этому каналу. Отменить нельзя.",
        reply_markup=kb.delchannel_confirm_menu(chat_id),
    )
    await call.answer()


@router.callback_query(F.data.startswith("adm:delchannel_yes:"))
async def confirm_delete_channel(call: CallbackQuery, db: Database):
    chat_id = int(call.data.split(":")[2])
    ch = await db.get_channel(chat_id)
    title = ch["title"] if ch else str(chat_id)

    await db.delete_channel_cascade(chat_id)

    channels = await db.list_channels()
    if channels:
        await call.message.edit_text(
            f"🗑 Канал «{title}» отключён от сети.",
            reply_markup=kb.channels_list_menu(channels),
        )
    else:
        await call.message.edit_text(
            f"🗑 Канал «{title}» отключён от сети.\n\nКаналов в сети больше нет.",
            reply_markup=kb.back_to_menu(),
        )
    await call.answer("Удалено")
