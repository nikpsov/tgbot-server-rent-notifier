from html import escape
from typing import Any

from telebot import types

from app.services import format_date


MAIN_MENU_BUTTONS = [
    "➕ Добавить сервер",
    "📋 Список серверов",
    "🔔 Получатели",
    "👥 Админы",
    "⚙️ Настройки",
    "❓ Помощь",
]

CANCEL_BUTTON = "❌ Отмена"
BACK_BUTTON = "⬅️ Назад"


def main_menu_keyboard() -> types.ReplyKeyboardMarkup:
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("➕ Добавить сервер", "📋 Список серверов")
    kb.row("🔔 Получатели", "👥 Админы")
    kb.row("⚙️ Настройки", "❓ Помощь")
    return kb


def cancel_keyboard() -> types.ReplyKeyboardMarkup:
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.row(BACK_BUTTON, CANCEL_BUTTON)
    return kb


def period_keyboard() -> types.ReplyKeyboardMarkup:
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.row("📅 Ежемесячно", "🧮 Кастом")
    kb.row(BACK_BUTTON, CANCEL_BUTTON)
    return kb


def recipients_manage_keyboard(chat_id: int) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🗑 Удалить", callback_data=f"recipient_del_{chat_id}"))
    return kb


def admins_manage_keyboard(admin_id: int, owner_id: int) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup()
    if admin_id != owner_id:
        kb.add(types.InlineKeyboardButton("🗑 Удалить админа", callback_data=f"admin_del_{admin_id}"))
    return kb


def server_keyboard(server_id: str) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup()
    kb.row(
        types.InlineKeyboardButton("✅ Оплачено", callback_data=f"pay_{server_id}"),
        types.InlineKeyboardButton("✏️ Редактировать", callback_data=f"edit_{server_id}"),
    )
    kb.row(types.InlineKeyboardButton("🗑 Удалить", callback_data=f"del_{server_id}"))
    return kb


def delete_confirm_keyboard(server_id: str) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup()
    kb.row(
        types.InlineKeyboardButton("✅ Подтвердить", callback_data=f"del_confirm_{server_id}"),
        types.InlineKeyboardButton("↩️ Отмена", callback_data=f"del_cancel_{server_id}"),
    )
    return kb


def server_edit_keyboard(server_id: str) -> types.ReplyKeyboardMarkup:
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.row(f"✏️ Имя ({server_id})", f"🌐 IP ({server_id})")
    kb.row(f"📆 Дата оплаты ({server_id})", f"⏱ Период ({server_id})")
    kb.row(f"🔔 Напоминание ({server_id})")
    kb.row(BACK_BUTTON, CANCEL_BUTTON)
    return kb


def admins_keyboard() -> types.ReplyKeyboardMarkup:
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.row("➕ Добавить администратора")
    kb.row(BACK_BUTTON, CANCEL_BUTTON)
    return kb


def recipients_keyboard() -> types.ReplyKeyboardMarkup:
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.row("➕ Как подключить чат")
    kb.row(BACK_BUTTON, CANCEL_BUTTON)
    return kb


def help_text() -> str:
    return (
        "❓ <b>Помощь</b>\n\n"
        "Используйте кнопки главного меню для управления ботом.\n"
        "Команды для совместимости:\n"
        "<code>/start</code> <code>/list</code> <code>/add</code> "
        "<code>/delete &lt;id&gt;</code> <code>/register</code>\n\n"
        "Чтобы подключить группу или канал для уведомлений:\n"
        "1. Добавьте бота в чат или канал\n"
        "2. Отправьте там <code>/register</code>"
    )


def settings_text(owner_id: int) -> str:
    return (
        "⚙️ <b>Настройки</b>\n\n"
        f"Owner ID: <code>{owner_id}</code>\n"
        "Доступ к управлению есть у owner и администраторов."
    )


def recipient_title(item: dict[str, Any]) -> str:
    title = escape(str(item.get("title") or item.get("chat_id")))
    chat_type = str(item.get("type") or "unknown")
    icon = "👤" if chat_type == "private" else "👥"
    return f"{icon} {title} (<code>{item.get('chat_id')}</code>)"


def server_text(server_id: str, server: dict[str, Any]) -> str:
    if server.get("period_type") == "monthly":
        period = "ежемесячно (30 дней)"
    else:
        period = f"кастом ({server.get('custom_days')} дн.)"

    ip = escape(str(server.get("ip_address") or "—"))
    name = escape(str(server.get("name", "Unnamed")))
    return (
        f"🖥 <b>Сервер</b> <code>{escape(server_id)}</code>\n"
        f"• Имя: <b>{name}</b>\n"
        f"• IP: <code>{ip}</code>\n"
        f"• Следующая оплата: <b>{format_date(str(server.get('next_payment_date', '')))}</b>\n"
        f"• Период: <code>{escape(period)}</code>\n"
        f"• Напомнить за: <code>{server.get('reminder_days')}</code> дн."
    )
