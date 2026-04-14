import json
from pathlib import Path
from typing import Any

from app.services import DEFAULT_REMINDER_DAYS


class Storage:
    def __init__(self, data_dir: Path, owner_chat_id: int) -> None:
        self._data_dir = data_dir
        self._data_file = data_dir / "servers.json"
        self._owner_chat_id = owner_chat_id

    def ensure_storage(self) -> None:
        self._data_dir.mkdir(parents=True, exist_ok=True)
        if not self._data_file.exists():
            self._data_file.write_text("{}", encoding="utf-8")

    def load_state(self) -> dict[str, Any]:
        self.ensure_storage()
        try:
            with self._data_file.open("r", encoding="utf-8") as f:
                raw = json.load(f)
        except (json.JSONDecodeError, OSError):
            raw = {}
        return self._normalize_state(raw)

    def save_state(self, state: dict[str, Any]) -> None:
        self.ensure_storage()
        normalized = self._normalize_state(state)
        tmp_path = self._data_file.with_suffix(".json.tmp")
        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump(normalized, f, ensure_ascii=False, indent=2)
        tmp_path.replace(self._data_file)

    def _normalize_server(self, server: dict[str, Any]) -> dict[str, Any]:
        period_type = server.get("period_type")
        if period_type not in {"monthly", "custom"}:
            period_type = "monthly"

        custom_days = server.get("custom_days")
        if period_type == "custom":
            try:
                custom_days_int = int(custom_days)
                if custom_days_int <= 0:
                    custom_days_int = 30
            except (TypeError, ValueError):
                custom_days_int = 30
            custom_days = custom_days_int
        else:
            custom_days = None

        try:
            reminder_days = int(server.get("reminder_days", DEFAULT_REMINDER_DAYS))
            if reminder_days < 0:
                reminder_days = DEFAULT_REMINDER_DAYS
        except (TypeError, ValueError):
            reminder_days = DEFAULT_REMINDER_DAYS

        return {
            "name": str(server.get("name") or "Unnamed server"),
            "ip_address": str(server.get("ip_address") or ""),
            "payment_amount": str(server.get("payment_amount") or "").strip(),
            "next_payment_date": str(server.get("next_payment_date") or ""),
            "period_type": period_type,
            "custom_days": custom_days,
            "reminder_days": reminder_days,
            "last_notified_on": str(server.get("last_notified_on") or ""),
        }

    def _normalize_recipients(self, recipients: Any) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        seen: set[int] = set()
        if not isinstance(recipients, list):
            return normalized

        for item in recipients:
            if not isinstance(item, dict):
                continue
            try:
                chat_id = int(item.get("chat_id"))
            except (TypeError, ValueError):
                continue
            if chat_id in seen:
                continue
            seen.add(chat_id)
            normalized.append(
                {
                    "chat_id": chat_id,
                    "type": str(item.get("type") or "private"),
                    "title": str(item.get("title") or str(chat_id)),
                }
            )
        return normalized

    def _normalize_admins(self, admins: Any) -> list[int]:
        normalized = {self._owner_chat_id}
        if isinstance(admins, list):
            for value in admins:
                try:
                    normalized.add(int(value))
                except (TypeError, ValueError):
                    continue
        return sorted(normalized)

    def _normalize_state(self, raw: Any) -> dict[str, Any]:
        if not isinstance(raw, dict):
            raw = {}

        servers: dict[str, Any] = {}
        raw_servers = raw.get("servers")
        if isinstance(raw_servers, dict):
            for key, value in raw_servers.items():
                if not isinstance(key, str) or not key.startswith("server_") or not isinstance(value, dict):
                    continue
                servers[key] = self._normalize_server(value)

        return {
            "admins": self._normalize_admins(raw.get("admins")),
            "recipients": self._normalize_recipients(raw.get("recipients")),
            "servers": servers,
        }
