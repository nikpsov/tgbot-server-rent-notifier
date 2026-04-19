from html import escape
from typing import Any

from telebot import types

from app.services import format_date


ADD_EMOJI = '<tg-emoji emoji-id="5242329690135356589">➕</tg-emoji>'
EDIT_EMOJI = '<tg-emoji emoji-id="5276314275994954605">✏️</tg-emoji>'
WARN_EMOJI = '<tg-emoji emoji-id="5276240711795107620">⚠️</tg-emoji>'
NOTIFY_EMOJI = '<tg-emoji emoji-id="5206222720416643915">🔔</tg-emoji>'
PERSON_EMOJI = '<tg-emoji emoji-id="5275979556308674886">👤</tg-emoji>'
PEOPLE_EMOJI = '<tg-emoji emoji-id="5298668674532538341">👥</tg-emoji>'
LINK_EMOJI = '<tg-emoji emoji-id="5278305362703835500">🔗</tg-emoji>'
DELETE_EMOJI = '<tg-emoji emoji-id="5276384644739129761">🗑</tg-emoji>'
PERIOD_EMOJI = '<tg-emoji emoji-id="5276412364458059956">⏱️</tg-emoji>'
BANK_EMOJI = '<tg-emoji emoji-id="5276398496008663230">🏦</tg-emoji>'
MONEY_EMOJI = '<tg-emoji emoji-id="5255806447106679302">💰</tg-emoji>'
HOME_EMOJI = '<tg-emoji emoji-id="5278413853577734640">🏠</tg-emoji>'
GLOBE_EMOJI = '<tg-emoji emoji-id="5276381204470329471">🌐</tg-emoji>'
BUILDING_EMOJI = '<tg-emoji emoji-id="5278528159837348960">🏢</tg-emoji>'
NO_ENTRY_EMOJI = '<tg-emoji emoji-id="5278578973595427038">⛔</tg-emoji>'
WORLD_EMOJI = '<tg-emoji emoji-id="5206202791768393003">🌍</tg-emoji>'
CHECK_EMOJI = '<tg-emoji emoji-id="5276220667182736079">✅</tg-emoji>'


MAIN_MENU_BUTTONS = [
    "➕ Добавить сервер",
    "📋 Список серверов",
    "🔍 Проверить оплаты",
    "🔔 Получатели",
    "👥 Админы",
    "⚙️ Настройки",
    "❓ Помощь",
]

CANCEL_BUTTON = "❌ Отмена"
BACK_BUTTON = "⬅️ Назад"
SKIP_BUTTON = "⏭️ Пропустить"


def main_menu_keyboard() -> types.ReplyKeyboardMarkup:
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("➕ Добавить сервер", "📋 Список серверов")
    kb.row("🔍 Проверить оплаты")
    kb.row("🔔 Получатели", "👥 Админы")
    kb.row("⚙️ Настройки", "❓ Помощь")
    return kb


def cancel_keyboard() -> types.ReplyKeyboardMarkup:
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.row(BACK_BUTTON, CANCEL_BUTTON)
    return kb


def skip_keyboard() -> types.ReplyKeyboardMarkup:
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.row(SKIP_BUTTON)
    kb.row(BACK_BUTTON, CANCEL_BUTTON)
    return kb


def period_keyboard() -> types.ReplyKeyboardMarkup:
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.row("📅 Ежемесячно", "📆 Ежедневно")
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


def server_list_keyboard(servers: list[tuple[str, dict[str, Any]]]) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup()
    for server_id, server in servers:
        name = str(server.get("name") or server_id).strip() or server_id
        period_type = str(server.get("period_type") or "monthly")
        due_raw = str(server.get("covered_until") if period_type == "daily" else server.get("next_payment_date") or "").strip()
        suffix = f" • {format_date(due_raw)}" if due_raw else ""
        text = f"{name}{suffix}"
        if len(text) > 60:
            text = text[:57] + "..."
        kb.add(types.InlineKeyboardButton(text, callback_data=f"server_show_{server_id}"))
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
    kb.row(f"✏️ Имя ({server_id})", f"🏢 Хостинг ({server_id})")
    kb.row(f"🌐 IP ({server_id})")
    kb.row(f"📆 Дата оплаты ({server_id})", f"⏱ Период ({server_id})")
    kb.row(f"💰 Сумма списания ({server_id})", f"🏦 Баланс ЛК ({server_id})")
    kb.row(f"🔗 Ссылка ЛК ({server_id})")
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
        "<code>/delete &lt;id&gt;</code> <code>/register</code> "
        "<code>/register &lt;chat_id|@username&gt;</code>\n\n"
        "Чтобы подключить группу или канал для уведомлений:\n"
        "1. Добавьте бота в чат или канал\n"
        "2. Отправьте там <code>/register</code>\n"
        "3. Либо добавьте получателя из лички через <code>/register &lt;chat_id|@username&gt;</code>"
    )


def settings_keyboard() -> types.ReplyKeyboardMarkup:
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.row("🔔 Настройки напоминаний")
    kb.row(BACK_BUTTON, CANCEL_BUTTON)
    return kb


def settings_text(
    owner_id: int, reminder_days: int, reminder_time: str, reminder_timezone: str, balance_charge_time: str
) -> str:
    return (
        "⚙️ <b>Настройки</b>\n\n"
        f"Owner ID: <code>{owner_id}</code>\n"
        f"Общее напоминание: <code>{reminder_days}</code> дн.\n"
        f"Время уведомлений: <code>{escape(reminder_time)}</code>\n"
        f"Таймзона уведомлений: <code>{escape(reminder_timezone)}</code>\n"
        f"Время списания баланса: <code>{escape(balance_charge_time)}</code>\n"
        "Доступ к управлению есть у owner и администраторов."
    )


def recipient_link_href(chat_id: int, chat_type: str) -> str | None:
    """Ссылка для открытия чата в клиенте Telegram по числовому ID (без username)."""
    ct = chat_type
    if ct == "unknown":
        if chat_id > 0:
            ct = "private"
        elif str(chat_id).startswith("-100"):
            ct = "supergroup"
        else:
            return None
    if ct == "private":
        return f"tg://user?id={chat_id}"
    if ct in ("channel", "supergroup"):
        s = str(chat_id)
        if s.startswith("-100") and len(s) > 4:
            return f"https://t.me/c/{s[4:]}/1"
    return None


def recipient_title(item: dict[str, Any]) -> str:
    raw_title = str(item.get("title") or item.get("chat_id"))
    try:
        chat_id = int(item["chat_id"])
    except (TypeError, ValueError, KeyError):
        chat_id = 0
    chat_type = str(item.get("type") or "unknown")
    icon = PERSON_EMOJI if chat_type == "private" else PEOPLE_EMOJI
    href = recipient_link_href(chat_id, chat_type)
    if href:
        name_html = f'<a href="{href}">{escape(raw_title)}</a>'
    else:
        name_html = escape(raw_title)
    return f"{icon} {name_html} (<code>{item.get('chat_id')}</code>)"


def server_text(server_id: str, server: dict[str, Any]) -> str:
    lines: list[str] = [f"🖥 <b>Сервер</b> <code>{escape(server_id)}</code>"]

    name_raw = str(server.get("name") or "").strip()
    if name_raw:
        lines.append(f"• Имя: <b>{escape(name_raw)}</b>")

    hosting_raw = str(server.get("hosting_name") or "").strip()
    if hosting_raw:
        lines.append(f"• {BUILDING_EMOJI} Хостинг: <b>{escape(hosting_raw)}</b>")

    ip_raw = str(server.get("ip_address") or "").strip()
    if ip_raw:
        lines.append(f"• {GLOBE_EMOJI} IP: <code>{escape(ip_raw)}</code>")

    pt = server.get("period_type")
    if pt == "monthly":
        lines.append(f"• {PERIOD_EMOJI} Период: <code>{escape('ежемесячно (30 дней)')}</code>")
    elif pt == "daily":
        lines.append(f"• {PERIOD_EMOJI} Период: <code>{escape('ежедневно')}</code>")

    amount_raw = str(server.get("payment_amount") or "").strip()
    if amount_raw:
        lines.append(f"• {MONEY_EMOJI} Сумма списания: <b>{escape(amount_raw)}</b>")

    npd_raw = str(server.get("next_payment_date") or "").strip()
    if npd_raw:
        lines.append(f"• Следующая оплата: <b>{format_date(npd_raw)}</b>")

    covered_until = str(server.get("covered_until") or "").strip()
    if covered_until:
        lines.append(f"• Хватает до: <b>{format_date(covered_until)}</b>")

    lk_balance_raw = str(server.get("lk_balance") or "").strip()
    if lk_balance_raw:
        balance_updated_on = str(server.get("balance_updated_on") or "").strip()
        if balance_updated_on:
            lines.append(f"• {BANK_EMOJI} Баланс ЛК ({format_date(balance_updated_on)}): <b>{escape(lk_balance_raw)}</b>")
        else:
            lines.append(f"• {BANK_EMOJI} Баланс ЛК: <b>{escape(lk_balance_raw)}</b>")

    lk_topup_url = str(server.get("lk_topup_url") or "").strip()
    if lk_topup_url:
        lines.append(f'• Пополнение ЛК: <a href="{escape(lk_topup_url)}">открыть</a>')

    return "\n".join(lines)
