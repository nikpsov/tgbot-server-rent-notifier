import datetime as dt
import json
import os
import threading
import time
from pathlib import Path
from typing import Any

import schedule
import telebot
from telebot import types


BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID_ENV = os.getenv("ADMIN_CHAT_ID")
TZ = os.getenv("TZ", "Europe/Moscow")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is required")
if not ADMIN_CHAT_ID_ENV:
    raise RuntimeError("ADMIN_CHAT_ID is required")

try:
    ADMIN_CHAT_ID = int(ADMIN_CHAT_ID_ENV)
except ValueError as exc:
    raise RuntimeError("ADMIN_CHAT_ID must be integer") from exc

DATA_DIR = Path("data")
DATA_FILE = DATA_DIR / "servers.json"
DATE_FMT = "%Y-%m-%d"
DISPLAY_DATE_FMT = "%d.%m.%Y"
DEFAULT_REMINDER_DAYS = 5

bot = telebot.TeleBot(BOT_TOKEN)
temp_data: dict[int, dict[str, Any]] = {}


def ensure_storage() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not DATA_FILE.exists():
        DATA_FILE.write_text("{}", encoding="utf-8")


def load_servers() -> dict[str, dict[str, Any]]:
    ensure_storage()
    try:
        with DATA_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        data = {}
    if not isinstance(data, dict):
        return {}
    return data


def save_servers(data: dict[str, dict[str, Any]]) -> None:
    ensure_storage()
    tmp_path = DATA_FILE.with_suffix(".json.tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp_path.replace(DATA_FILE)


def next_server_id(data: dict[str, dict[str, Any]]) -> str:
    max_idx = 0
    for key in data:
        if key.startswith("server_"):
            suffix = key.split("_", 1)[1]
            if suffix.isdigit():
                max_idx = max(max_idx, int(suffix))
    return f"server_{max_idx + 1}"


def parse_date(date_str: str) -> dt.date | None:
    try:
        return dt.datetime.strptime(date_str, DATE_FMT).date()
    except ValueError:
        return None


def format_date(date_str: str) -> str:
    parsed = parse_date(date_str)
    if not parsed:
        return date_str
    return parsed.strftime(DISPLAY_DATE_FMT)


def is_admin(message_or_call: Any) -> bool:
    chat_id = message_or_call.chat.id if hasattr(message_or_call, "chat") else message_or_call.message.chat.id
    return chat_id == ADMIN_CHAT_ID


def reject_non_admin(message_or_call: Any) -> bool:
    if is_admin(message_or_call):
        return False
    if hasattr(message_or_call, "message"):
        bot.answer_callback_query(message_or_call.id, "Недостаточно прав")
    else:
        bot.reply_to(message_or_call, "Бот доступен только администратору.")
    return True


def build_server_keyboard(server_id: str) -> types.InlineKeyboardMarkup:
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(
        types.InlineKeyboardButton("✅ Отметить как оплаченный", callback_data=f"pay_{server_id}"),
        types.InlineKeyboardButton("🗑 Удалить", callback_data=f"del_{server_id}"),
    )
    return keyboard


def calculate_next_date(server: dict[str, Any]) -> str:
    base_date = parse_date(server["next_payment_date"])
    if not base_date:
        raise ValueError("Invalid next_payment_date")
    if server["period_type"] == "monthly":
        new_date = base_date + dt.timedelta(days=30)
    else:
        custom_days = int(server.get("custom_days") or 0)
        if custom_days <= 0:
            raise ValueError("custom_days must be > 0")
        new_date = base_date + dt.timedelta(days=custom_days)
    return new_date.strftime(DATE_FMT)


def server_text(server_id: str, server: dict[str, Any]) -> str:
    period = "monthly" if server["period_type"] == "monthly" else f"custom ({server['custom_days']} дн.)"
    ip = server.get("ip_address") or "—"
    return (
        f"ID: `{server_id}`\n"
        f"Имя: *{server['name']}*\n"
        f"IP: `{ip}`\n"
        f"Следующая оплата: *{format_date(server['next_payment_date'])}*\n"
        f"Период: `{period}`\n"
        f"Напомнить за: `{server['reminder_days']}` дн."
    )


def run_daily_check() -> None:
    servers = load_servers()
    today = dt.date.today()
    for server_id, server in servers.items():
        due_date = parse_date(server.get("next_payment_date", ""))
        reminder_days = int(server.get("reminder_days") or DEFAULT_REMINDER_DAYS)
        if not due_date:
            continue
        if today + dt.timedelta(days=reminder_days) >= due_date:
            text = (
                "⚠️ *Скоро оплата!*\n\n"
                f"{server_text(server_id, server)}"
            )
            bot.send_message(
                ADMIN_CHAT_ID,
                text,
                parse_mode="Markdown",
                reply_markup=build_server_keyboard(server_id),
            )


def scheduler_worker() -> None:
    schedule.every().day.at("09:00").do(run_daily_check)
    while True:
        schedule.run_pending()
        time.sleep(1)


@bot.message_handler(commands=["start"])
def start_cmd(message: types.Message) -> None:
    if reject_non_admin(message):
        return
    bot.send_message(
        message.chat.id,
        (
            "Доступные команды:\n"
            "/add - добавить сервер\n"
            "/list - показать сервера\n"
            "/delete <id> - удалить сервер"
        ),
    )


@bot.message_handler(commands=["list"])
def list_cmd(message: types.Message) -> None:
    if reject_non_admin(message):
        return
    servers = load_servers()
    if not servers:
        bot.send_message(message.chat.id, "Список пуст.")
        return
    for server_id, server in servers.items():
        bot.send_message(
            message.chat.id,
            server_text(server_id, server),
            parse_mode="Markdown",
            reply_markup=build_server_keyboard(server_id),
        )


@bot.message_handler(commands=["delete"])
def delete_cmd(message: types.Message) -> None:
    if reject_non_admin(message):
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "Использование: /delete <server_id>")
        return
    server_id = parts[1].strip()
    servers = load_servers()
    if server_id not in servers:
        bot.reply_to(message, f"Сервер `{server_id}` не найден.", parse_mode="Markdown")
        return
    deleted = servers.pop(server_id)
    save_servers(servers)
    bot.reply_to(message, f"Удален сервер: *{deleted['name']}* (`{server_id}`)", parse_mode="Markdown")


def set_add_state(chat_id: int, step: str, payload: dict[str, Any] | None = None) -> None:
    temp_data[chat_id] = {"step": step, "payload": payload or {}}


@bot.message_handler(commands=["add"])
def add_cmd(message: types.Message) -> None:
    if reject_non_admin(message):
        return
    set_add_state(message.chat.id, "name")
    bot.send_message(message.chat.id, "Введите имя сервера:")


@bot.message_handler(func=lambda m: m.chat.id in temp_data)
def add_flow_handler(message: types.Message) -> None:
    if reject_non_admin(message):
        return
    state = temp_data.get(message.chat.id)
    if not state:
        return
    step = state["step"]
    payload = state["payload"]
    text = (message.text or "").strip()

    if step == "name":
        if not text:
            bot.reply_to(message, "Имя не может быть пустым. Повторите ввод:")
            return
        payload["name"] = text
        state["step"] = "ip"
        bot.send_message(message.chat.id, "Введите IP-адрес (или '-' чтобы пропустить):")
        return

    if step == "ip":
        payload["ip_address"] = "" if text in {"", "-"} else text
        state["step"] = "next_payment_date"
        bot.send_message(message.chat.id, "Введите дату следующей оплаты в формате YYYY-MM-DD:")
        return

    if step == "next_payment_date":
        parsed = parse_date(text)
        if not parsed:
            bot.reply_to(message, "Неверный формат даты. Пример: 2026-12-15")
            return
        payload["next_payment_date"] = parsed.strftime(DATE_FMT)
        state["step"] = "period_type"
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        keyboard.add("monthly", "custom")
        bot.send_message(message.chat.id, "Выберите тип периода:", reply_markup=keyboard)
        return

    if step == "period_type":
        if text not in {"monthly", "custom"}:
            bot.reply_to(message, "Введите `monthly` или `custom`.", parse_mode="Markdown")
            return
        payload["period_type"] = text
        if text == "custom":
            state["step"] = "custom_days"
            bot.send_message(
                message.chat.id,
                "Введите количество дней для custom периода:",
                reply_markup=types.ReplyKeyboardRemove(),
            )
            return
        payload["custom_days"] = None
        state["step"] = "reminder_days"
        bot.send_message(
            message.chat.id,
            f"Введите reminder_days (Enter или '-' для значения по умолчанию {DEFAULT_REMINDER_DAYS}):",
            reply_markup=types.ReplyKeyboardRemove(),
        )
        return

    if step == "custom_days":
        if not text.isdigit() or int(text) <= 0:
            bot.reply_to(message, "Введите целое число больше 0.")
            return
        payload["custom_days"] = int(text)
        state["step"] = "reminder_days"
        bot.send_message(
            message.chat.id,
            f"Введите reminder_days (Enter или '-' для значения по умолчанию {DEFAULT_REMINDER_DAYS}):",
        )
        return

    if step == "reminder_days":
        if text in {"", "-"}:
            reminder_days = DEFAULT_REMINDER_DAYS
        elif text.isdigit() and int(text) >= 0:
            reminder_days = int(text)
        else:
            bot.reply_to(message, "Введите неотрицательное целое число или '-'.")
            return
        payload["reminder_days"] = reminder_days

        servers = load_servers()
        server_id = next_server_id(servers)
        servers[server_id] = {
            "name": payload["name"],
            "ip_address": payload["ip_address"],
            "next_payment_date": payload["next_payment_date"],
            "period_type": payload["period_type"],
            "custom_days": payload["custom_days"],
            "reminder_days": payload["reminder_days"],
        }
        save_servers(servers)
        temp_data.pop(message.chat.id, None)
        bot.send_message(
            message.chat.id,
            f"Сервер добавлен:\n\n{server_text(server_id, servers[server_id])}",
            parse_mode="Markdown",
            reply_markup=types.ReplyKeyboardRemove(),
        )


@bot.callback_query_handler(func=lambda call: call.data.startswith("pay_"))
def mark_paid(call: types.CallbackQuery) -> None:
    if reject_non_admin(call):
        return
    server_id = call.data.removeprefix("pay_")
    servers = load_servers()
    server = servers.get(server_id)
    if not server:
        bot.answer_callback_query(call.id, "Сервер не найден")
        return
    try:
        new_date = calculate_next_date(server)
    except ValueError:
        bot.answer_callback_query(call.id, "Ошибка в данных сервера")
        return
    server["next_payment_date"] = new_date
    save_servers(servers)

    bot.answer_callback_query(call.id, "Оплата отмечена")
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=(
            "✅ Продлено до "
            f"*{format_date(new_date)}*\n\n"
            f"{server_text(server_id, server)}"
        ),
        parse_mode="Markdown",
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("del_"))
def delete_inline(call: types.CallbackQuery) -> None:
    if reject_non_admin(call):
        return
    server_id = call.data.removeprefix("del_")
    servers = load_servers()
    server = servers.get(server_id)
    if not server:
        bot.answer_callback_query(call.id, "Сервер не найден")
        return
    servers.pop(server_id)
    save_servers(servers)
    bot.answer_callback_query(call.id, "Удалено")
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"🗑 Удален сервер: *{server['name']}* (`{server_id}`)",
        parse_mode="Markdown",
    )


def main() -> None:
    ensure_storage()
    os.environ["TZ"] = TZ
    try:
        time.tzset()  # type: ignore[attr-defined]
    except AttributeError:
        pass

    scheduler_thread = threading.Thread(target=scheduler_worker, daemon=True)
    scheduler_thread.start()

    run_daily_check()
    bot.infinity_polling(timeout=60, long_polling_timeout=30)


if __name__ == "__main__":
    main()
