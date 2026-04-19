import json
from pathlib import Path
from typing import Any

from app.services import DEFAULT_REMINDER_DAYS, apply_periodic_balance_charge_with_time, balance_coverage_until_str


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
        if period_type not in {"monthly", "daily"}:
            period_type = "monthly"

        normalized = {
            "name": str(server.get("name") or "Unnamed server"),
            "hosting_name": str(server.get("hosting_name") or "").strip(),
            "ip_address": str(server.get("ip_address") or ""),
            "period_type": period_type,
            "payment_amount": str(server.get("payment_amount") or "").strip(),
            "next_payment_date": str(server.get("next_payment_date") or ""),
            "covered_until": str(server.get("covered_until") or "").strip(),
            "lk_balance": str(server.get("lk_balance") or "").strip(),
            "balance_updated_on": str(server.get("balance_updated_on") or "").strip(),
            "lk_topup_url": str(server.get("lk_topup_url") or "").strip(),
            "last_notified_on": str(server.get("last_notified_on") or ""),
        }
        apply_periodic_balance_charge_with_time(normalized, self._balance_charge_time)
        normalized["covered_until"] = balance_coverage_until_str(normalized)
        return normalized

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

        try:
            reminder_days = int(raw.get("reminder_days", DEFAULT_REMINDER_DAYS))
            if reminder_days < 0:
                reminder_days = DEFAULT_REMINDER_DAYS
        except (TypeError, ValueError):
            reminder_days = DEFAULT_REMINDER_DAYS
        reminder_time = str(raw.get("reminder_time") or "09:00").strip() or "09:00"
        reminder_timezone = str(raw.get("reminder_timezone") or "Europe/Moscow").strip() or "Europe/Moscow"
        balance_charge_time = str(raw.get("balance_charge_time") or "00:00").strip() or "00:00"
        self._balance_charge_time = balance_charge_time

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
            "reminder_days": reminder_days,
            "reminder_time": reminder_time,
            "reminder_timezone": reminder_timezone,
            "balance_charge_time": balance_charge_time,
            "servers": servers,
        }
