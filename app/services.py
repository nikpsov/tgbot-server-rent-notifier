import datetime as dt
from typing import Any

DATE_FMT = "%d.%m.%Y"
DISPLAY_DATE_FMT = "%d.%m.%Y"
DEFAULT_REMINDER_DAYS = 5


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


def next_server_id(servers: dict[str, dict[str, Any]]) -> str:
    max_idx = 0
    for key in servers:
        if key.startswith("server_"):
            suffix = key.split("_", 1)[1]
            if suffix.isdigit():
                max_idx = max(max_idx, int(suffix))
    return f"server_{max_idx + 1}"


def calculate_next_date(server: dict[str, Any]) -> str:
    base_date = parse_date(str(server.get("next_payment_date", "")))
    if not base_date:
        raise ValueError("Invalid next_payment_date")

    period_type = server.get("period_type")
    if period_type == "monthly":
        new_date = base_date + dt.timedelta(days=30)
    else:
        custom_days = int(server.get("custom_days") or 0)
        if custom_days <= 0:
            raise ValueError("custom_days must be > 0")
        new_date = base_date + dt.timedelta(days=custom_days)
    return new_date.strftime(DATE_FMT)


def normalize_server_payload(payload: dict[str, Any]) -> dict[str, Any]:
    period_type = payload.get("period_type", "monthly")
    if period_type not in {"monthly", "custom"}:
        period_type = "monthly"

    custom_days = payload.get("custom_days")
    if period_type == "custom":
        custom_days = int(custom_days)
        if custom_days <= 0:
            raise ValueError("custom_days must be > 0")
    else:
        custom_days = None

    reminder_days = int(payload.get("reminder_days", DEFAULT_REMINDER_DAYS))
    if reminder_days < 0:
        raise ValueError("reminder_days must be >= 0")

    next_payment_date = str(payload.get("next_payment_date", ""))
    if not parse_date(next_payment_date):
        raise ValueError("invalid date format")

    name = str(payload.get("name", "")).strip()
    if not name:
        raise ValueError("name is empty")

    payment_amount = str(payload.get("payment_amount") or "").strip()

    return {
        "name": name,
        "ip_address": str(payload.get("ip_address") or "").strip(),
        "payment_amount": payment_amount,
        "next_payment_date": next_payment_date,
        "period_type": period_type,
        "custom_days": custom_days,
        "reminder_days": reminder_days,
        "last_notified_on": str(payload.get("last_notified_on") or ""),
    }


def due_for_reminder(server: dict[str, Any], today: dt.date) -> bool:
    due_date = parse_date(str(server.get("next_payment_date", "")))
    if not due_date:
        return False
    reminder_days = int(server.get("reminder_days") or DEFAULT_REMINDER_DAYS)
    last_notified_on = parse_date(str(server.get("last_notified_on", "")))
    if last_notified_on == today:
        return False
    return today + dt.timedelta(days=reminder_days) >= due_date
