import datetime as dt
import logging
from dataclasses import dataclass, field
from html import escape
from pathlib import Path
from typing import Any

import telebot
from telebot import types

from app.config import Settings
from app.services import (
    DEFAULT_REMINDER_DAYS,
    DATE_FMT,
    calculate_next_date,
    due_for_reminder,
    next_server_id,
    normalize_server_payload,
    parse_date,
)
from app.storage import Storage
from app.ui import (
    BACK_BUTTON,
    CANCEL_BUTTON,
    MAIN_MENU_BUTTONS,
    admins_keyboard,
    admins_manage_keyboard,
    cancel_keyboard,
    delete_confirm_keyboard,
    help_text,
    main_menu_keyboard,
    period_keyboard,
    recipient_title,
    recipients_keyboard,
    recipients_manage_keyboard,
    server_edit_keyboard,
    server_keyboard,
    server_text,
    settings_text,
)


@dataclass
class SessionState:
    flow: str
    step: str
    payload: dict[str, Any] = field(default_factory=dict)
    history: list[tuple[str, dict[str, Any]]] = field(default_factory=list)


class RentNotifierBot:
    def __init__(self, settings: Settings, logger: logging.Logger) -> None:
        self.settings = settings
        self.logger = logger
        self.storage = Storage(Path("data"), settings.owner_chat_id)
        self.bot = telebot.TeleBot(settings.bot_token)
        self.sessions: dict[int, SessionState] = {}

    def register_handlers(self) -> None:
        @self.bot.message_handler(commands=["start"])
        def start_cmd(message: types.Message) -> None:
            self.handle_start(message)

        @self.bot.message_handler(commands=["help"])
        def help_cmd(message: types.Message) -> None:
            self.handle_help(message)

        @self.bot.message_handler(commands=["list"])
        def list_cmd(message: types.Message) -> None:
            self.handle_list(message)

        @self.bot.message_handler(commands=["add"])
        def add_cmd(message: types.Message) -> None:
            self.start_add_flow(message)

        @self.bot.message_handler(commands=["delete"])
        def delete_cmd(message: types.Message) -> None:
            self.handle_delete_command(message)

        @self.bot.message_handler(commands=["register"])
        def register_cmd(message: types.Message) -> None:
            self.handle_register_recipient(message)

        @self.bot.callback_query_handler(func=lambda call: call.data.startswith("pay_"))
        def pay_cb(call: types.CallbackQuery) -> None:
            self.handle_pay(call)

        @self.bot.callback_query_handler(func=lambda call: call.data.startswith("del_confirm_"))
        def delete_confirm_cb(call: types.CallbackQuery) -> None:
            self.handle_delete_confirm(call)

        @self.bot.callback_query_handler(func=lambda call: call.data.startswith("del_cancel_"))
        def delete_cancel_cb(call: types.CallbackQuery) -> None:
            self.handle_delete_cancel(call)

        @self.bot.callback_query_handler(
            func=lambda call: call.data.startswith("del_")
            and not call.data.startswith("del_confirm_")
            and not call.data.startswith("del_cancel_")
        )
        def delete_cb(call: types.CallbackQuery) -> None:
            self.handle_delete_action(call)

        @self.bot.callback_query_handler(func=lambda call: call.data.startswith("edit_"))
        def edit_cb(call: types.CallbackQuery) -> None:
            self.handle_edit_start(call)

        @self.bot.callback_query_handler(func=lambda call: call.data.startswith("recipient_del_"))
        def recipient_cb(call: types.CallbackQuery) -> None:
            self.handle_recipient_delete(call)

        @self.bot.callback_query_handler(func=lambda call: call.data.startswith("admin_del_"))
        def admin_cb(call: types.CallbackQuery) -> None:
            self.handle_admin_delete(call)

        @self.bot.message_handler(func=lambda message: True, content_types=["text"])
        def text_router(message: types.Message) -> None:
            self.route_text(message)

    def run(self) -> None:
        self.storage.ensure_storage()
        self.register_handlers()
        self.run_daily_check()
        self.bot.infinity_polling(timeout=60, long_polling_timeout=30)

    def state(self) -> dict[str, Any]:
        return self.storage.load_state()

    def save_state(self, state: dict[str, Any]) -> None:
        self.storage.save_state(state)

    def admins(self) -> set[int]:
        return set(self.state()["admins"])

    def is_owner(self, chat_id: int) -> bool:
        return chat_id == self.settings.owner_chat_id

    def extract_actor_chat_id(self, message_or_call: Any) -> int:
        if hasattr(message_or_call, "from_user") and message_or_call.from_user:
            return int(message_or_call.from_user.id)
        if hasattr(message_or_call, "message") and message_or_call.message and message_or_call.message.from_user:
            return int(message_or_call.message.from_user.id)
        if hasattr(message_or_call, "chat"):
            return int(message_or_call.chat.id)
        return int(message_or_call.message.chat.id)

    def is_admin_actor(self, message_or_call: Any) -> bool:
        return self.extract_actor_chat_id(message_or_call) in self.admins()

    def reject_non_admin(self, message_or_call: Any) -> bool:
        if self.is_admin_actor(message_or_call):
            return False
        if hasattr(message_or_call, "id") and hasattr(message_or_call, "message"):
            self.bot.answer_callback_query(message_or_call.id, "Недостаточно прав")
        else:
            self.bot.send_message(
                message_or_call.chat.id,
                "⛔ Доступ только для owner и администраторов.",
                reply_markup=main_menu_keyboard() if message_or_call.chat.type == "private" else None,
            )
        return True

    def send_html(self, chat_id: int, text: str, **kwargs: Any) -> None:
        self.bot.send_message(chat_id, text, parse_mode="HTML", **kwargs)

    def handle_start(self, message: types.Message) -> None:
        if message.chat.type != "private":
            self.send_html(message.chat.id, "👋 Бот активен. Для управления используйте личный чат с ботом.")
            return
        if self.reject_non_admin(message):
            return
        self.sessions.pop(message.chat.id, None)
        self.send_html(
            message.chat.id,
            "🏠 <b>Главное меню</b>\n\nВыберите действие кнопками ниже.",
            reply_markup=main_menu_keyboard(),
        )

    def handle_help(self, message: types.Message) -> None:
        if message.chat.type == "private" and self.reject_non_admin(message):
            return
        reply_markup = main_menu_keyboard() if message.chat.type == "private" else None
        self.send_html(message.chat.id, help_text(), reply_markup=reply_markup)

    def handle_list(self, message: types.Message) -> None:
        if self.reject_non_admin(message):
            return
        servers = self.state()["servers"]
        if not servers:
            self.send_html(message.chat.id, "📭 Список серверов пуст.", reply_markup=main_menu_keyboard())
            return
        self.send_html(message.chat.id, "📋 <b>Список серверов</b>", reply_markup=main_menu_keyboard())
        for server_id, server in servers.items():
            self.send_html(message.chat.id, server_text(server_id, server), reply_markup=server_keyboard(server_id))

    def handle_delete_command(self, message: types.Message) -> None:
        if self.reject_non_admin(message):
            return
        parts = (message.text or "").split(maxsplit=1)
        if len(parts) < 2:
            self.send_html(message.chat.id, "Использование: <code>/delete &lt;server_id&gt;</code>")
            return
        server_id = parts[1].strip()
        state = self.state()
        server = state["servers"].get(server_id)
        if not server:
            self.send_html(message.chat.id, f"⚠️ Сервер <code>{server_id}</code> не найден.")
            return
        self.send_html(
            message.chat.id,
            f"🗑 Подтвердите удаление сервера:\n\n{server_text(server_id, server)}",
            reply_markup=delete_confirm_keyboard(server_id),
        )

    def handle_register_recipient(self, message: types.Message) -> None:
        if self.reject_non_admin(message):
            return
        state = self.state()
        recipient = {
            "chat_id": int(message.chat.id),
            "type": str(message.chat.type),
            "title": self.chat_title(message.chat),
        }
        state["recipients"] = [item for item in state["recipients"] if int(item["chat_id"]) != recipient["chat_id"]]
        state["recipients"].append(recipient)
        self.save_state(state)
        self.send_html(
            message.chat.id,
            "🔔 Этот чат подключён к уведомлениям.\n\nНапоминания об оплате будут приходить сюда автоматически.",
        )

    def chat_title(self, chat: types.Chat) -> str:
        if chat.type == "private":
            full_name = " ".join(part for part in [chat.first_name, chat.last_name] if part)
            return full_name or chat.username or str(chat.id)
        return chat.title or chat.username or str(chat.id)

    def route_text(self, message: types.Message) -> None:
        if message.chat.type != "private":
            return
        text = (message.text or "").strip()

        if text == "❓ Помощь":
            self.handle_help(message)
            return
        if text == "📋 Список серверов":
            self.handle_list(message)
            return
        if text == "➕ Добавить сервер":
            self.start_add_flow(message)
            return
        if text == "🔔 Получатели":
            self.show_recipients(message)
            return
        if text == "👥 Админы":
            self.show_admins(message)
            return
        if text == "⚙️ Настройки":
            if self.reject_non_admin(message):
                return
            self.send_html(message.chat.id, settings_text(self.settings.owner_chat_id), reply_markup=main_menu_keyboard())
            return
        if text == "➕ Добавить администратора":
            if not self.is_owner(self.extract_actor_chat_id(message)):
                self.send_html(message.chat.id, "⛔ Только owner может добавлять администраторов.", reply_markup=main_menu_keyboard())
                return
            self.sessions[message.chat.id] = SessionState(flow="admin", step="chat_id")
            self.prompt_current_step(message.chat.id, self.sessions[message.chat.id])
            return
        if text == "➕ Как подключить чат":
            if self.reject_non_admin(message):
                return
            self.send_html(
                message.chat.id,
                "🔗 <b>Как подключить чат или канал</b>\n\n"
                "1. Добавьте бота в нужный чат или канал.\n"
                "2. Выдайте право писать сообщения, если это канал.\n"
                "3. Отправьте там <code>/register</code>.\n\n"
                "После этого чат появится в списке получателей.",
                reply_markup=recipients_keyboard(),
            )
            return

        session = self.sessions.get(message.chat.id)
        if not session:
            if text not in MAIN_MENU_BUTTONS and not text.startswith("/"):
                self.send_html(message.chat.id, "Выберите действие через кнопки меню.", reply_markup=main_menu_keyboard())
            return

        if text == CANCEL_BUTTON:
            self.sessions.pop(message.chat.id, None)
            self.send_html(message.chat.id, "Текущее действие отменено.", reply_markup=main_menu_keyboard())
            return

        if text == BACK_BUTTON:
            self.handle_back(message)
            return

        if session.flow == "add":
            self.handle_add_flow(message, session)
            return
        if session.flow == "edit":
            self.handle_edit_flow(message, session)
            return
        if session.flow == "admin":
            self.handle_admin_flow(message, session)

    def push_history(self, session: SessionState) -> None:
        session.history.append((session.step, dict(session.payload)))

    def handle_back(self, message: types.Message) -> None:
        session = self.sessions.get(message.chat.id)
        if not session or not session.history:
            self.sessions.pop(message.chat.id, None)
            self.send_html(message.chat.id, "Возвращаемся в главное меню.", reply_markup=main_menu_keyboard())
            return
        session.step, session.payload = session.history.pop()
        self.prompt_current_step(message.chat.id, session)

    def start_add_flow(self, message: types.Message) -> None:
        if self.reject_non_admin(message):
            return
        self.sessions[message.chat.id] = SessionState(flow="add", step="name")
        self.prompt_current_step(message.chat.id, self.sessions[message.chat.id])

    def prompt_current_step(self, chat_id: int, session: SessionState) -> None:
        if session.flow == "add":
            prompts = {
                "name": "➕ <b>Новый сервер</b>\n\nВведите имя сервера.",
                "ip_address": "🌐 Введите IP или <code>-</code>, чтобы пропустить.",
                "next_payment_date": "📆 Введите дату следующей оплаты в формате <code>dd.mm.yyyy</code>.",
                "custom_days": "🧮 Введите количество дней для кастомного периода.",
                "reminder_days": (
                    f"🔔 Введите количество дней напоминания или <code>-</code> для значения "
                    f"по умолчанию ({DEFAULT_REMINDER_DAYS})."
                ),
            }
            if session.step == "period_type":
                self.send_html(chat_id, "⏱ Выберите тип периода.", reply_markup=period_keyboard())
                return
            self.send_html(chat_id, prompts[session.step], reply_markup=cancel_keyboard())
            return

        if session.flow == "edit":
            server_id = str(session.payload["server_id"])
            if session.step == "field":
                self.send_html(chat_id, f"✏️ Что изменить у сервера <code>{server_id}</code>?", reply_markup=server_edit_keyboard(server_id))
                return
            prompts = {
                "name": "✏️ Введите новое имя сервера.",
                "ip_address": "🌐 Введите новый IP или <code>-</code>, чтобы очистить поле.",
                "next_payment_date": "📆 Введите новую дату в формате <code>dd.mm.yyyy</code>.",
                "custom_days": "🧮 Введите количество дней для кастомного периода.",
                "reminder_days": "🔔 Введите новое значение reminder days (0 и больше).",
            }
            if session.step == "period_type":
                self.send_html(chat_id, "⏱ Выберите новый тип периода.", reply_markup=period_keyboard())
                return
            self.send_html(chat_id, prompts[session.step], reply_markup=cancel_keyboard())
            return

        if session.flow == "admin":
            self.send_html(
                chat_id,
                "👥 Введите chat_id нового администратора.\n\nOwner добавляется из ENV автоматически.",
                reply_markup=cancel_keyboard(),
            )

    def handle_add_flow(self, message: types.Message, session: SessionState) -> None:
        text = (message.text or "").strip()
        if session.step == "name":
            if not text:
                self.send_html(message.chat.id, "Имя не может быть пустым.")
                return
            self.push_history(session)
            session.payload["name"] = text
            session.step = "ip_address"
            self.prompt_current_step(message.chat.id, session)
            return
        if session.step == "ip_address":
            self.push_history(session)
            session.payload["ip_address"] = "" if text in {"", "-"} else text
            session.step = "next_payment_date"
            self.prompt_current_step(message.chat.id, session)
            return
        if session.step == "next_payment_date":
            if not parse_date(text):
                self.send_html(message.chat.id, "Неверный формат даты. Пример: <code>14.04.2026</code>.")
                return
            self.push_history(session)
            session.payload["next_payment_date"] = text
            session.step = "period_type"
            self.prompt_current_step(message.chat.id, session)
            return
        if session.step == "period_type":
            if text not in {"📅 Ежемесячно", "🧮 Кастом"}:
                self.send_html(message.chat.id, "Выберите тип периода кнопками.")
                return
            self.push_history(session)
            session.payload["period_type"] = "monthly" if text == "📅 Ежемесячно" else "custom"
            session.step = "reminder_days" if session.payload["period_type"] == "monthly" else "custom_days"
            self.prompt_current_step(message.chat.id, session)
            return
        if session.step == "custom_days":
            if not text.isdigit() or int(text) <= 0:
                self.send_html(message.chat.id, "Нужно положительное целое число.")
                return
            self.push_history(session)
            session.payload["custom_days"] = int(text)
            session.step = "reminder_days"
            self.prompt_current_step(message.chat.id, session)
            return
        if session.step == "reminder_days":
            if text in {"", "-"}:
                reminder_days = DEFAULT_REMINDER_DAYS
            elif text.isdigit() and int(text) >= 0:
                reminder_days = int(text)
            else:
                self.send_html(message.chat.id, "Введите число 0 или больше, либо <code>-</code>.")
                return
            session.payload["reminder_days"] = reminder_days
            if session.payload.get("period_type") == "monthly":
                session.payload["custom_days"] = None
            try:
                server_data = normalize_server_payload(session.payload)
            except ValueError as exc:
                self.send_html(message.chat.id, f"Не удалось сохранить сервер: <code>{exc}</code>")
                return
            state = self.state()
            server_id = next_server_id(state["servers"])
            state["servers"][server_id] = server_data
            self.save_state(state)
            self.sessions.pop(message.chat.id, None)
            self.send_html(message.chat.id, f"✅ Сервер добавлен.\n\n{server_text(server_id, server_data)}", reply_markup=main_menu_keyboard())

    def handle_edit_start(self, call: types.CallbackQuery) -> None:
        if self.reject_non_admin(call):
            return
        server_id = call.data.removeprefix("edit_")
        state = self.state()
        if server_id not in state["servers"]:
            self.bot.answer_callback_query(call.id, "Сервер не найден")
            return
        actor_id = self.extract_actor_chat_id(call)
        self.sessions[actor_id] = SessionState(flow="edit", step="field", payload={"server_id": server_id})
        self.bot.answer_callback_query(call.id, "Открываю редактирование")
        self.prompt_current_step(actor_id, self.sessions[actor_id])

    def handle_edit_flow(self, message: types.Message, session: SessionState) -> None:
        text = (message.text or "").strip()
        server_id = str(session.payload["server_id"])
        state = self.state()
        server = state["servers"].get(server_id)
        if not server:
            self.sessions.pop(message.chat.id, None)
            self.send_html(message.chat.id, "⚠️ Сервер уже не существует.", reply_markup=main_menu_keyboard())
            return

        if session.step == "field":
            mapping = {
                f"✏️ Имя ({server_id})": "name",
                f"🌐 IP ({server_id})": "ip_address",
                f"📆 Дата оплаты ({server_id})": "next_payment_date",
                f"⏱ Период ({server_id})": "period_type",
                f"🔔 Напоминание ({server_id})": "reminder_days",
            }
            next_step = mapping.get(text)
            if not next_step:
                self.send_html(message.chat.id, "Выберите поле через кнопки.")
                return
            self.push_history(session)
            session.step = next_step
            self.prompt_current_step(message.chat.id, session)
            return

        if session.step == "name":
            if not text:
                self.send_html(message.chat.id, "Имя не может быть пустым.")
                return
            server["name"] = text
        elif session.step == "ip_address":
            server["ip_address"] = "" if text in {"", "-"} else text
        elif session.step == "next_payment_date":
            if not parse_date(text):
                self.send_html(message.chat.id, "Введите дату в формате <code>dd.mm.yyyy</code>.")
                return
            server["next_payment_date"] = text
        elif session.step == "period_type":
            if text not in {"📅 Ежемесячно", "🧮 Кастом"}:
                self.send_html(message.chat.id, "Выберите тип периода кнопками.")
                return
            if text == "📅 Ежемесячно":
                server["period_type"] = "monthly"
                server["custom_days"] = None
            else:
                self.push_history(session)
                session.step = "custom_days"
                self.prompt_current_step(message.chat.id, session)
                return
        elif session.step == "custom_days":
            if not text.isdigit() or int(text) <= 0:
                self.send_html(message.chat.id, "Нужно положительное целое число.")
                return
            server["period_type"] = "custom"
            server["custom_days"] = int(text)
        elif session.step == "reminder_days":
            if not text.isdigit() or int(text) < 0:
                self.send_html(message.chat.id, "Введите число 0 или больше.")
                return
            server["reminder_days"] = int(text)

        try:
            state["servers"][server_id] = normalize_server_payload(server)
        except ValueError as exc:
            self.send_html(message.chat.id, f"Не удалось сохранить изменения: <code>{exc}</code>")
            return
        state["servers"][server_id]["last_notified_on"] = ""

        self.save_state(state)
        self.sessions[message.chat.id] = SessionState(flow="edit", step="field", payload={"server_id": server_id})
        self.send_html(
            message.chat.id,
            f"✅ Изменения сохранены.\n\n{server_text(server_id, state['servers'][server_id])}",
            reply_markup=server_edit_keyboard(server_id),
        )

    def handle_pay(self, call: types.CallbackQuery) -> None:
        if self.reject_non_admin(call):
            return
        server_id = call.data.removeprefix("pay_")
        state = self.state()
        server = state["servers"].get(server_id)
        if not server:
            self.bot.answer_callback_query(call.id, "Сервер не найден")
            return
        try:
            server["next_payment_date"] = calculate_next_date(server)
            server["last_notified_on"] = ""
        except ValueError as exc:
            self.logger.warning("Failed to calculate next date for %s: %s", server_id, exc)
            self.bot.answer_callback_query(call.id, "Ошибка в данных сервера")
            return
        self.save_state(state)
        self.bot.answer_callback_query(call.id, "Оплата отмечена")
        self.bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"✅ Платёж отмечен.\n\n{server_text(server_id, server)}",
            parse_mode="HTML",
            reply_markup=server_keyboard(server_id),
        )

    def handle_delete_action(self, call: types.CallbackQuery) -> None:
        if self.reject_non_admin(call):
            return
        server_id = call.data.removeprefix("del_")
        state = self.state()
        server = state["servers"].get(server_id)
        if not server:
            self.bot.answer_callback_query(call.id, "Сервер не найден")
            return
        self.bot.answer_callback_query(call.id, "Нужно подтверждение")
        self.bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"🗑 Подтвердите удаление сервера:\n\n{server_text(server_id, server)}",
            parse_mode="HTML",
            reply_markup=delete_confirm_keyboard(server_id),
        )

    def handle_delete_confirm(self, call: types.CallbackQuery) -> None:
        if self.reject_non_admin(call):
            return
        server_id = call.data.removeprefix("del_confirm_")
        state = self.state()
        server = state["servers"].pop(server_id, None)
        if not server:
            self.bot.answer_callback_query(call.id, "Сервер не найден")
            return
        self.save_state(state)
        self.bot.answer_callback_query(call.id, "Сервер удалён")
        self.bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"🗑 Сервер удалён: <b>{escape(str(server['name']))}</b> (<code>{server_id}</code>)",
            parse_mode="HTML",
        )

    def handle_delete_cancel(self, call: types.CallbackQuery) -> None:
        if self.reject_non_admin(call):
            return
        server_id = call.data.removeprefix("del_cancel_")
        state = self.state()
        server = state["servers"].get(server_id)
        if not server:
            self.bot.answer_callback_query(call.id, "Сервер не найден")
            return
        self.bot.answer_callback_query(call.id, "Удаление отменено")
        self.bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=server_text(server_id, server),
            parse_mode="HTML",
            reply_markup=server_keyboard(server_id),
        )

    def show_recipients(self, message: types.Message) -> None:
        if self.reject_non_admin(message):
            return
        state = self.state()
        self.send_html(
            message.chat.id,
            "🔔 <b>Получатели уведомлений</b>\n\nДобавление делается командой <code>/register</code> в нужном чате или канале.",
            reply_markup=recipients_keyboard(),
        )
        if not state["recipients"]:
            self.send_html(message.chat.id, "Пока нет подключённых получателей.")
            return
        for item in state["recipients"]:
            self.send_html(message.chat.id, recipient_title(item), reply_markup=recipients_manage_keyboard(int(item["chat_id"])))

    def handle_recipient_delete(self, call: types.CallbackQuery) -> None:
        if self.reject_non_admin(call):
            return
        chat_id = int(call.data.removeprefix("recipient_del_"))
        state = self.state()
        before = len(state["recipients"])
        state["recipients"] = [item for item in state["recipients"] if int(item["chat_id"]) != chat_id]
        if len(state["recipients"]) == before:
            self.bot.answer_callback_query(call.id, "Получатель не найден")
            return
        self.save_state(state)
        self.bot.answer_callback_query(call.id, "Получатель удалён")
        self.bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"🗑 Получатель <code>{chat_id}</code> удалён.",
            parse_mode="HTML",
        )

    def show_admins(self, message: types.Message) -> None:
        if self.reject_non_admin(message):
            return
        state = self.state()
        keyboard = admins_keyboard() if self.is_owner(self.extract_actor_chat_id(message)) else main_menu_keyboard()
        self.send_html(message.chat.id, "👥 <b>Администраторы</b>", reply_markup=keyboard)
        for admin_id in state["admins"]:
            role = "owner" if admin_id == self.settings.owner_chat_id else "admin"
            self.send_html(
                message.chat.id,
                f"• <code>{admin_id}</code> — {role}",
                reply_markup=admins_manage_keyboard(admin_id, self.settings.owner_chat_id),
            )

    def handle_admin_delete(self, call: types.CallbackQuery) -> None:
        actor_id = self.extract_actor_chat_id(call)
        if not self.is_owner(actor_id):
            self.bot.answer_callback_query(call.id, "Только owner может удалять админов")
            return
        admin_id = int(call.data.removeprefix("admin_del_"))
        if admin_id == self.settings.owner_chat_id:
            self.bot.answer_callback_query(call.id, "Owner удалить нельзя")
            return
        state = self.state()
        before = len(state["admins"])
        state["admins"] = [item for item in state["admins"] if int(item) != admin_id]
        if len(state["admins"]) == before:
            self.bot.answer_callback_query(call.id, "Админ не найден")
            return
        self.save_state(state)
        self.bot.answer_callback_query(call.id, "Админ удалён")
        self.bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"🗑 Администратор <code>{admin_id}</code> удалён.",
            parse_mode="HTML",
        )

    def handle_admin_flow(self, message: types.Message, session: SessionState) -> None:
        if not self.is_owner(self.extract_actor_chat_id(message)):
            self.sessions.pop(message.chat.id, None)
            self.send_html(message.chat.id, "Только owner может управлять администраторами.", reply_markup=main_menu_keyboard())
            return
        text = (message.text or "").strip()
        try:
            admin_id = int(text)
        except ValueError:
            self.send_html(message.chat.id, "Нужен числовой chat_id.")
            return
        state = self.state()
        if admin_id not in state["admins"]:
            state["admins"].append(admin_id)
            state["admins"] = sorted({int(item) for item in state["admins"]})
            self.save_state(state)
        self.sessions.pop(message.chat.id, None)
        self.send_html(message.chat.id, f"✅ Администратор <code>{admin_id}</code> добавлен.", reply_markup=main_menu_keyboard())

    def run_daily_check(self) -> None:
        state = self.state()
        today = dt.date.today()
        today_str = today.strftime(DATE_FMT)
        due_servers: list[tuple[str, dict[str, Any]]] = []
        for server_id, server in state["servers"].items():
            try:
                if due_for_reminder(server, today):
                    due_servers.append((server_id, server))
            except Exception as exc:
                self.logger.warning("Skipping broken server %s: %s", server_id, exc)

        if not due_servers:
            return

        if not state["recipients"]:
            self.send_html(
                self.settings.owner_chat_id,
                "⚠️ Получатели уведомлений не настроены. Подключите чат или канал через <code>/register</code>.",
            )
            return

        for recipient in state["recipients"]:
            chat_id = int(recipient["chat_id"])
            for server_id, server in due_servers:
                try:
                    self.send_html(
                        chat_id,
                        f"⚠️ <b>Скоро оплата</b>\n\n{server_text(server_id, server)}",
                        reply_markup=server_keyboard(server_id),
                    )
                except Exception as exc:
                    self.logger.warning("Failed to send notification to %s: %s", chat_id, exc)
        for _, server in due_servers:
            server["last_notified_on"] = today_str
        self.save_state(state)
